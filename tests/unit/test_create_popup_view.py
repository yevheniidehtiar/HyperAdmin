"""Unit tests for the FK/M2M create-popup endpoint (H6, v0.5.5).

Mirrors the BDD scenarios in
``.meta/epics/epic-v055-htmx-autocomplete/stories/featviews-add-create-popup-view.md``.
"""

from __future__ import annotations

import json

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.main import Admin


class Supplier(SQLModel, table=True):
    __tablename__ = "test_popup_supplier"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    city: str | None = None


class SupplierAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client():
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(Supplier, SupplierAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET — initial popup form render
# ---------------------------------------------------------------------------


def test_popup_get_renders_form_fragment(client: TestClient):
    """The widget's "+" button issues `hx-get` to this endpoint to open the modal."""
    response = client.get("/admin/supplier/create-popup?target=supplier_id")

    assert response.status_code == 200
    body = response.text
    assert 'data-testid="popup-form"' in body
    # The form posts back to the same URL with `target` preserved.
    assert "supplier_id" in body


# ---------------------------------------------------------------------------
# POST — happy path
# ---------------------------------------------------------------------------


def test_popup_post_with_valid_data_returns_hx_trigger(client: TestClient):
    """
    Scenario: popup create with valid data returns HX-Trigger payload
      Given Supplier is registered
      When  POST /admin/supplier/create-popup with valid form data + target=supplier_id
      Then  response status is 200 and body is empty
      And   HX-Trigger header contains "hyperadminPopupCreated" with id=<new pk> and target="supplier_id"
    """
    # Given / When
    response = client.post(
        "/admin/supplier/create-popup",
        data={"name": "Acme", "city": "Paris", "target": "supplier_id"},
    )

    # Then
    assert response.status_code == 200
    assert response.text == ""
    trigger = response.headers.get("HX-Trigger")
    assert trigger is not None
    payload = json.loads(trigger)
    assert "hyperadminPopupCreated" in payload
    event = payload["hyperadminPopupCreated"]
    assert event["target"] == "supplier_id"
    assert isinstance(event["id"], int)
    assert event["id"] >= 1
    # Label falls back to str(instance) — SQLModel default is the repr.
    assert event["label"]


def test_popup_post_with_validation_error_re_renders_form(client: TestClient):
    """Pydantic validation error keeps the modal open with field-level errors."""
    # Given / When name is missing (required field)
    response = client.post(
        "/admin/supplier/create-popup",
        data={"target": "supplier_id"},
    )

    # Then the form re-renders (no HX-Trigger event yet).
    assert "HX-Trigger" not in response.headers or "hyperadminPopupCreated" not in (
        response.headers.get("HX-Trigger") or ""
    )
    assert 'data-testid="popup-form"' in response.text
    # The selected target is preserved through the re-render.
    assert "supplier_id" in response.text


def test_popup_post_without_target_returns_400(client: TestClient):
    """`target` is required — the modal cannot know which field to populate without it."""
    response = client.post(
        "/admin/supplier/create-popup",
        data={"name": "Acme"},
    )
    assert response.status_code == 400
    assert "target" in response.text.lower()


# ---------------------------------------------------------------------------
# Permission denied — `_check_permission` is the same gate used by `create_view`,
# already covered by the broader permission integration tests. We assert it is
# wired in by monkey-patching the view's permission_checker after mount.
# ---------------------------------------------------------------------------


def _iter_all_routes(routes):
    """Recursively yield all APIRoute objects, including those nested in _IncludedRouter."""
    for route in routes:
        yield route
        original_router = getattr(route, "original_router", None)
        if original_router:
            yield from _iter_all_routes(getattr(original_router, "routes", []))
        sub_routes = getattr(route, "routes", None)
        if sub_routes:
            yield from _iter_all_routes(sub_routes)


def test_popup_post_invokes_permission_check_with_add_codename(client: TestClient):
    """The view must call ``_check_permission(request, "add")`` before creating."""
    calls: list[str] = []

    class _AllowAddDenyOthers:
        async def has_permission(self, user, codename):
            calls.append(codename)
            return codename.startswith("add_")

    for route in _iter_all_routes(client.app.router.routes):
        endpoint = getattr(route, "endpoint", None)
        view = getattr(endpoint, "__self__", None) if endpoint else None
        if view is not None and hasattr(view, "permission_checker"):
            view.permission_checker = _AllowAddDenyOthers()

    # Authenticated request — middleware-set user required when a checker is wired.
    @client.app.middleware("http")
    async def _user(request, call_next):
        request.state.user = {"id": 1}
        return await call_next(request)

    response = client.post(
        "/admin/supplier/create-popup",
        data={"name": "Acme", "target": "supplier_id"},
    )

    assert response.status_code == 200
    assert "add_supplier" in calls
