"""View-layer object-level permission checks (C2-C, #481).

Each test maps 1:1 to a BDD scenario from
``.meta/epics/.../stories/featviews-add-object-level-permission-checks-to-detailupdate.md``.

Exercises ``DynamicModelView`` end-to-end against a real SQLite engine and a
custom-middleware-backed ``request.state.user``, so the helper's wiring through
``options.object_permission_checker`` is fully covered.
"""

from __future__ import annotations

from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class OrderObjectPerm(SQLModel, table=True):
    """Test model used for object-level permission scenarios."""

    __tablename__ = "test_order_object_perm"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    owner_id: int = Field(default=0, index=True)


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Wipe the global model registry between tests."""
    site._registry = {}
    yield
    site._registry = {}


def _seed_orders(engine: Any) -> None:
    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(OrderObjectPerm(id=1, title="bob-order-1", owner_id=1))
            session.add(OrderObjectPerm(id=2, title="alice-order-1", owner_id=2))
            await session.commit()

    anyio.run(_setup)


class _DenyAllChecker:
    """ObjectPermissionChecker that denies every action."""

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return False


class _ViewOnlyChecker:
    """Allows view but denies change/delete (object-level)."""

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return action == "view"


class _SuperuserBypassChecker:
    """Denies non-superusers but lets a flagged ``is_superuser`` user through.

    Models the SDD requirement that the superuser bypass lives in the checker
    implementation, not in the view-layer helper.
    """

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return bool(getattr(user, "is_superuser", False))


class _Bob:
    """Stand-in for a non-superuser ``request.state.user``."""

    is_superuser = False


class _Admin:
    """Stand-in for a superuser ``request.state.user``."""

    is_superuser = True


class _DefaultAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _client_with_checker(checker: Any, user: Any | None = None) -> TestClient:
    """Build a TestClient whose admin uses ``checker`` for object permissions.

    Adds an ASGI middleware that pins ``request.state.user`` to a stand-in
    object — required by ``_check_object_permission`` to resolve the user.
    """
    app = FastAPI()
    pinned_user = user if user is not None else _Bob()

    @app.middleware("http")
    async def _attach_user(request: Request, call_next: Any) -> Any:
        request.state.user = pinned_user
        return await call_next(request)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed_orders(engine)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    options = AdminOptions(object_permission_checker=checker)
    site.register(OrderObjectPerm, _DefaultAdmin, options=options)
    admin.mount(path="/admin")

    return TestClient(app)


def test_detail_view_returns_403_when_object_permission_denied() -> None:
    """
    Scenario: staff user cannot view another user's record when checker denies
      Given an ObjectPermissionChecker that denies every action
      When  GET /admin/orderobjectperm/1
      Then  the response is 403 Forbidden
    """
    # Given
    client = _client_with_checker(_DenyAllChecker())

    # When
    response = client.get("/admin/orderobjectperm/1")

    # Then
    assert response.status_code == 403


def test_update_view_returns_403_when_change_denied() -> None:
    """
    Scenario: object permission check on update
      Given the checker denies "change" on order #1
      When  PUT /admin/orderobjectperm/1 with valid data
      Then  the response is 403 Forbidden
    """
    # Given
    client = _client_with_checker(_ViewOnlyChecker())

    # When
    response = client.put(
        "/admin/orderobjectperm/1",
        data={"title": "renamed", "owner_id": "1"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    # Then
    assert response.status_code == 403


def test_delete_action_returns_403_when_delete_denied() -> None:
    """
    Scenario: object permission check on delete
      Given the checker denies "delete" on order #1
      When  DELETE /admin/orderobjectperm/1
      Then  the response is 403 Forbidden
    """
    # Given
    client = _client_with_checker(_ViewOnlyChecker())

    # When
    response = client.delete(
        "/admin/orderobjectperm/1",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    # Then
    assert response.status_code == 403


def test_superuser_bypass_when_checker_allows_superusers() -> None:
    """
    Scenario: superuser bypasses object-level checks
      Given a checker that returns True for users with ``is_superuser=True``
      And   the request.state.user is a superuser
      When  GET /admin/orderobjectperm/1
      Then  the response is 200 OK (the bypass lives in the checker impl)
    """
    # Given
    client = _client_with_checker(_SuperuserBypassChecker(), user=_Admin())

    # When
    response = client.get("/admin/orderobjectperm/1")

    # Then
    assert response.status_code == 200
    assert "bob-order-1" in response.text


def test_detail_view_returns_403_when_user_not_authenticated() -> None:
    """
    Scenario: missing request.state.user under an active checker yields 403
      Given an ObjectPermissionChecker is configured but request.state.user is None
      When  GET /admin/orderobjectperm/1
      Then  the response is 403 (the helper refuses to authorize an anonymous request)
    """
    # Given a client whose middleware pins request.state.user to None
    app = FastAPI()

    @app.middleware("http")
    async def _attach_no_user(request: Request, call_next: Any) -> Any:
        request.state.user = None
        return await call_next(request)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed_orders(engine)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    options = AdminOptions(object_permission_checker=_ViewOnlyChecker())
    site.register(OrderObjectPerm, _DefaultAdmin, options=options)
    admin.mount(path="/admin")
    client = TestClient(app)

    # When
    response = client.get("/admin/orderobjectperm/1")

    # Then
    assert response.status_code == 403
