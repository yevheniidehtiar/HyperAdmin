"""View-layer wiring of ``ModelAdmin.get_queryset`` (C2-C, #480).

Each test maps 1:1 to a BDD scenario from
``.meta/epics/.../stories/featviews-wire-getqueryset-into-listview-detailview.md``.

These exercise ``DynamicModelView`` end-to-end against a real SQLite engine via
FastAPI's ``TestClient`` so that the adapter ↔ view wiring (C1-B + C2-B + C2-C) is
covered as a stack — the C1-B/C2-B hooks were proven in isolation already; here we
prove the view layer activates them per request.
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
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class OrderRLS(SQLModel, table=True):
    """Test model with ``owner_id`` for row-level security scenarios."""

    __tablename__ = "test_order_rls_qs"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    owner_id: int = Field(default=0, index=True)


# Module-level mutable used by ModelAdmins to simulate a per-request user.
# Tests reset this between cases via the autouse ``cleanup_registry`` fixture.
_active_user_id: dict[str, int | None] = {"value": None}


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Wipe the global model registry and active-user shim between tests."""
    site._registry = {}
    _active_user_id["value"] = None
    yield
    site._registry = {}
    _active_user_id["value"] = None


def _seed_orders(engine: Any) -> None:
    """Populate the test DB with three orders owned by users 1 and 2."""

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(OrderRLS(id=1, title="bob-order-1", owner_id=1))
            session.add(OrderRLS(id=2, title="bob-order-2", owner_id=1))
            session.add(OrderRLS(id=3, title="alice-order-1", owner_id=2))
            await session.commit()

    anyio.run(_setup)


def _build_app(admin_class: type[ModelAdmin]) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed_orders(engine)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(OrderRLS, admin_class)
    admin.mount(path="/admin")
    return TestClient(app)


class _OwnerScopedAdmin(ModelAdmin):
    """ModelAdmin that scopes queries to ``_active_user_id`` to simulate RLS."""

    adapter_class = SQLModelAdapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        uid = _active_user_id["value"]
        if uid is None:
            return {}
        return {"owner_id": uid}


class _DefaultAdmin(ModelAdmin):
    """ModelAdmin with the default no-op ``get_queryset`` (returns ``{}``)."""

    adapter_class = SQLModelAdapter


def test_list_view_filters_rows_excluded_by_get_queryset() -> None:
    """
    Scenario: list_view only shows records matching get_queryset filter
      Given user "bob" (id=1) owns orders [1, 2] and "alice" (id=2) owns [3]
      And   ModelAdmin.get_queryset returns {"owner_id": active_user.id}
      When  bob visits GET /admin/orderrls
      Then  only orders [1, 2] are listed (alice's order #3 is excluded)
    """
    # Given
    client = _build_app(_OwnerScopedAdmin)
    _active_user_id["value"] = 1

    # When
    response = client.get("/admin/orderrls")

    # Then
    assert response.status_code == 200
    assert "bob-order-1" in response.text
    assert "bob-order-2" in response.text
    assert "alice-order-1" not in response.text


def test_detail_view_returns_404_when_row_excluded_by_get_queryset() -> None:
    """
    Scenario: detail_view returns 404 for filtered-out record
      Given alice's order #3 is excluded by bob's get_queryset filter
      When  bob visits GET /admin/orderrls/3
      Then  the response is 404 Not Found
    """
    # Given
    client = _build_app(_OwnerScopedAdmin)
    _active_user_id["value"] = 1  # bob

    # When
    response = client.get("/admin/orderrls/3")

    # Then
    assert response.status_code == 404


def test_default_get_queryset_is_a_noop() -> None:
    """
    Scenario: default get_queryset returns no filters (backward compatible)
      Given a ModelAdmin with the default ``get_queryset`` returning {}
      When  GET /admin/orderrls
      Then  all three rows are visible
    """
    # Given
    client = _build_app(_DefaultAdmin)

    # When
    response = client.get("/admin/orderrls")

    # Then
    assert response.status_code == 200
    assert "bob-order-1" in response.text
    assert "bob-order-2" in response.text
    assert "alice-order-1" in response.text
