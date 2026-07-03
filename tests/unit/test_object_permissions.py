"""Integration-level unit tests for object-level permissions and RLS (C3-B, #482).

Spec: ``docs/specs/object-permissions-mfa.md`` — Track A.

These tests exercise the FULL Track A chain (request →
:meth:`hyperadmin.core.model.ModelAdmin.get_queryset` →
:meth:`hyperadmin.core.adapters.BaseAdapter.set_queryset_filter` → SQL) end-to-end
through ``DynamicModelView``, plus the combination of a queryset filter and an
:class:`hyperadmin.core.auth.ObjectPermissionChecker` on the same request to verify
denial precedence.

Existing C2-C unit tests already cover each layer in isolation
(``test_views_object_permissions.py``, ``test_views_get_queryset_wiring.py``,
``test_modeladmin_get_queryset.py``, ``test_adapter_get_queryset.py``); this file
intentionally targets the cross-layer integration paths the C3-B story calls out.
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


class OrderC3B(SQLModel, table=True):
    """Test model with ``owner_id`` for row-level scoping scenarios."""

    __tablename__ = "test_order_c3b"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    owner_id: int = Field(default=0, index=True)


class _User:
    """Stand-in for a non-superuser ``request.state.user`` with an ``id`` attribute."""

    def __init__(self, user_id: int, *, is_superuser: bool = False) -> None:
        self.id = user_id
        self.is_superuser = is_superuser


class _OwnerScopedAdmin(ModelAdmin):
    """ModelAdmin scoped to ``request.state.user.id`` — RLS at the admin layer."""

    adapter_class = SQLModelAdapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        if request is None:
            return {}
        user = getattr(request.state, "user", None)
        if user is None:
            return {}
        return {"owner_id": user.id}


class _BlockSpecificObjectChecker:
    """ObjectPermissionChecker that denies access to a specific object id.

    Used to compose with ``_OwnerScopedAdmin`` so we can test denial precedence:
    the queryset filter excludes rows the user does not own (yielding 404), but
    when a row IS owned by the user, the object-level checker can still deny
    (yielding 403). This is the exact precedence rule defined in the SDD's
    "Edge Cases & Error Handling" section.
    """

    def __init__(self, blocked_id: int) -> None:
        self.blocked_id = blocked_id

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return getattr(obj, "id", None) != self.blocked_id


@pytest.fixture(autouse=True)
def cleanup_registry() -> Any:
    """Wipe the global model registry between tests to avoid cross-pollution."""
    site._registry = {}
    yield
    site._registry = {}


def _seed_orders(engine: Any) -> None:
    """Seed three orders: two owned by user 1 (bob), one by user 2 (alice)."""

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(OrderC3B(id=10, title="bob-order-A", owner_id=1))
            session.add(OrderC3B(id=20, title="bob-order-B", owner_id=1))
            session.add(OrderC3B(id=40, title="alice-order-A", owner_id=2))
            await session.commit()

    anyio.run(_setup)


def _build_client(
    admin_class: type[ModelAdmin],
    *,
    pinned_user: Any | None = None,
    object_permission_checker: Any | None = None,
) -> TestClient:
    """Build a TestClient with ``pinned_user`` attached on every request.

    This mirrors how the live ``AuthenticationMiddleware`` would populate
    ``request.state.user`` after a successful session lookup.
    """
    app = FastAPI()

    @app.middleware("http")
    async def _attach_user(request: Request, call_next: Any) -> Any:
        request.state.user = pinned_user
        return await call_next(request)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed_orders(engine)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    options = AdminOptions(object_permission_checker=object_permission_checker)
    site.register(OrderC3B, admin_class, options=options)
    admin.mount(path="/admin")

    return TestClient(app)


# ---------------------------------------------------------------------------
# Story scenario: get_queryset composes ModelAdmin → adapter → SQL
# ---------------------------------------------------------------------------


def test_modeladmin_get_queryset_composes_through_adapter_to_sql() -> None:
    """
    Scenario: ModelAdmin.get_queryset(request) flows into the SQL WHERE clause
      Given a ModelAdmin returns ``{"owner_id": user.id}`` for the active request
      When  GET /admin/orderc3b is issued by user id=1 (owns 2 of 3 orders)
      Then  the list contains only that user's rows (other owners are excluded)
      And   the pagination total reflects the filtered count
    """
    # Given a ModelAdmin scoped to request.state.user.id and bob (id=1)
    client = _build_client(_OwnerScopedAdmin, pinned_user=_User(1))

    # When bob lists orders
    response = client.get("/admin/orderc3b")

    # Then only his two rows are visible — alice's order is filtered out before SQL
    assert response.status_code == 200
    assert "bob-order-A" in response.text
    assert "bob-order-B" in response.text
    assert "alice-order-A" not in response.text
    # And the pagination total reflects the filtered count (2 of 3)
    assert "of 2 results" in response.text


# ---------------------------------------------------------------------------
# Story scenario: detail view 404s for rows excluded by get_queryset (RLS)
# ---------------------------------------------------------------------------


def test_detail_view_returns_404_when_row_filtered_out_by_modeladmin() -> None:
    """
    Scenario: detail view treats rows excluded by get_queryset as nonexistent
      Given bob's ModelAdmin returns ``{"owner_id": 1}``
      And   order #40 is owned by alice (owner_id=2)
      When  bob visits GET /admin/orderc3b/40
      Then  the response is 404 Not Found (the row is invisible to bob, not just denied)
    """
    # Given a request scoped to bob (id=1)
    client = _build_client(_OwnerScopedAdmin, pinned_user=_User(1))

    # When bob requests alice's order #40 directly by URL
    response = client.get("/admin/orderc3b/40")

    # Then the row is reported as not found — RLS hides existence, not just access
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Story scenario: 404 (filter) precedes 403 (object permission denial)
# ---------------------------------------------------------------------------


def test_filter_excluded_row_returns_404_even_when_object_checker_would_deny() -> None:
    """
    Scenario: queryset filter precedes object-permission check (404 wins over 403)
      Given bob's ModelAdmin returns ``{"owner_id": 1}``
      And   the ObjectPermissionChecker would deny order #40 to everyone
      When  bob visits GET /admin/orderc3b/40 (alice's row)
      Then  the response is 404 — the row is filtered out before the checker runs
      (the object-level checker never sees an object it could deny)
    """
    # Given an admin filtered to bob and a checker that would deny order #40
    client = _build_client(
        _OwnerScopedAdmin,
        pinned_user=_User(1),
        object_permission_checker=_BlockSpecificObjectChecker(blocked_id=40),
    )

    # When bob requests alice's order
    response = client.get("/admin/orderc3b/40")

    # Then 404 wins — get_queryset hid the row before the checker could deny it
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Story scenario: object-permission 403 fires only on rows the filter let through
# ---------------------------------------------------------------------------


def test_object_permission_denial_returns_403_when_row_passes_queryset_filter() -> None:
    """
    Scenario: object-permission denial yields 403 only on rows the filter admits
      Given bob's ModelAdmin returns ``{"owner_id": 1}``
      And   the ObjectPermissionChecker would deny order #20 (which bob owns)
      When  bob visits GET /admin/orderc3b/20
      Then  the response is 403 — the row passed the filter, then the checker denied
    """
    # Given an admin filtered to bob and a checker that denies bob's own #20
    client = _build_client(
        _OwnerScopedAdmin,
        pinned_user=_User(1),
        object_permission_checker=_BlockSpecificObjectChecker(blocked_id=20),
    )

    # When bob requests his own (filter-admitted) order #20
    response = client.get("/admin/orderc3b/20")

    # Then the object-level checker is reached and denies — 403, not 404
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Story scenario: filter + checker both let an owned, allowed row through
# ---------------------------------------------------------------------------


def test_owned_and_allowed_row_is_visible_through_full_stack() -> None:
    """
    Scenario: row owned by user AND allowed by object checker is fully visible
      Given bob's ModelAdmin returns ``{"owner_id": 1}``
      And   the ObjectPermissionChecker only denies order #40
      When  bob visits GET /admin/orderc3b/10 (his row, allowed)
      Then  the response is 200 OK and the row's data is rendered
    """
    # Given an admin filtered to bob with a checker that only denies #40
    client = _build_client(
        _OwnerScopedAdmin,
        pinned_user=_User(1),
        object_permission_checker=_BlockSpecificObjectChecker(blocked_id=40),
    )

    # When bob requests his own order #10
    response = client.get("/admin/orderc3b/10")

    # Then the page renders successfully with the row's title
    assert response.status_code == 200
    assert "bob-order-A" in response.text
