"""Tests for inline cell editing in the list view.

Covers:
- Domain: AdminOptions.list_editable + ModelAdmin class-attribute merge
- Routing: per-model inline edit/save routes appear iff list_editable is non-empty
- Views: GET form, POST save, validation errors, permission gate (403)

See ``docs/specs/inline-cell-editing.md`` for the BDD scenarios.
"""

from __future__ import annotations

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class WidgetThing(SQLModel, table=True):
    __tablename__ = "test_widget_thing_inline"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    description: str = ""
    price: float = 0.0
    is_active: bool = True


class WidgetThingAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_editable = ["name", "is_active"]


class ReadOnlyThing(SQLModel, table=True):
    __tablename__ = "test_readonly_thing_inline"
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


class ReadOnlyThingAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    # No list_editable — feature should be dormant


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _make_client(register_readonly: bool = False) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(WidgetThing(name="Alice", description="hello", price=1.0))
            if register_readonly:
                session.add(ReadOnlyThing(name="ro"))
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine)
    site.register(WidgetThing, WidgetThingAdmin)
    if register_readonly:
        site.register(ReadOnlyThing, ReadOnlyThingAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


def test_admin_options_default_list_editable_is_empty() -> None:
    """Scenario: feature is dormant by default."""
    opts = AdminOptions()
    assert opts.list_editable == []


def test_admin_options_accepts_list_editable() -> None:
    opts = AdminOptions(list_editable=["name", "price"])
    assert opts.list_editable == ["name", "price"]


def test_modeladmin_class_attribute_is_merged_into_options() -> None:
    """The registry merges ``ModelAdmin.list_editable`` into options."""
    site._registry = {}
    site.register(WidgetThing, WidgetThingAdmin)
    admin_class = site._registry[WidgetThing]
    assert admin_class.options.list_editable == ["name", "is_active"]


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_inline_routes_present_when_list_editable_non_empty() -> None:
    client = _make_client()
    response = client.get("/admin/widgetthing/1/inline/name")
    assert response.status_code == 200


def test_inline_routes_absent_when_list_editable_empty() -> None:
    client = _make_client(register_readonly=True)
    # WidgetThing routes exist
    assert client.get("/admin/widgetthing/1/inline/name").status_code == 200
    # ReadOnlyThing does not register inline routes at all
    response = client.get("/admin/readonlything/1/inline/name")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Views: GET inline edit form
# ---------------------------------------------------------------------------


def test_get_inline_edit_form_renders_editor_with_current_value() -> None:
    """Scenario: opening the editor swaps the cell to an inline input."""
    client = _make_client()
    response = client.get("/admin/widgetthing/1/inline/name")
    assert response.status_code == 200
    body = response.text
    assert 'value="Alice"' in body
    assert 'data-testid="cell-editor-name-1"' in body
    assert 'data-testid="cell-save-name-1"' in body
    assert 'data-testid="cell-cancel-name-1"' in body


def test_get_inline_edit_form_for_non_editable_field_returns_403() -> None:
    """Scenario: non-editable field cannot be edited inline."""
    client = _make_client()
    # description is not in list_editable
    response = client.get("/admin/widgetthing/1/inline/description")
    assert response.status_code == 403


def test_get_inline_edit_form_for_id_returns_403() -> None:
    """Primary key is never inline-editable."""
    client = _make_client()
    response = client.get("/admin/widgetthing/1/inline/id")
    assert response.status_code == 403


def test_get_inline_edit_form_for_unknown_field_returns_403() -> None:
    client = _make_client()
    response = client.get("/admin/widgetthing/1/inline/does_not_exist")
    assert response.status_code == 403


def test_get_inline_edit_form_with_cancel_returns_static_cell() -> None:
    """Scenario: cancelling restores the static cell."""
    client = _make_client()
    response = client.get("/admin/widgetthing/1/inline/name?cancel=1")
    assert response.status_code == 200
    body = response.text
    # The static cell should contain the value and an edit affordance,
    # but not a form / save button.
    assert "Alice" in body
    assert 'data-testid="cell-edit-name-1"' in body
    assert 'data-testid="cell-save-name-1"' not in body


def test_get_inline_edit_form_for_missing_item_returns_404() -> None:
    client = _make_client()
    response = client.get("/admin/widgetthing/9999/inline/name")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Views: POST inline save
# ---------------------------------------------------------------------------


def test_post_inline_save_persists_and_returns_cell_fragment() -> None:
    """Scenario: saving a valid value persists and re-renders the cell."""
    client = _make_client()
    response = client.post("/admin/widgetthing/1/inline/name", data={"name": "Alicia"})
    assert response.status_code == 200
    body = response.text
    assert "Alicia" in body
    assert 'data-testid="cell-edit-name-1"' in body
    assert 'data-testid="cell-saved-flag-name-1"' in body

    # Persisted: re-fetch the static cell
    static = client.get("/admin/widgetthing/1/inline/name?cancel=1")
    assert "Alicia" in static.text


def test_post_inline_save_invalid_value_returns_422_with_errors() -> None:
    """Scenario: invalid input shows an error fragment without persisting."""
    client = _make_client()
    response = client.post("/admin/widgetthing/1/inline/name", data={"name": ""})
    assert response.status_code == 422
    body = response.text
    assert 'data-testid="name-errors"' in body
    # Original value is preserved server-side
    static = client.get("/admin/widgetthing/1/inline/name?cancel=1")
    assert "Alice" in static.text


def test_post_inline_save_for_non_editable_field_returns_403() -> None:
    """Scenario: non-editable field cannot be POSTed inline."""
    client = _make_client()
    response = client.post("/admin/widgetthing/1/inline/description", data={"description": "x"})
    assert response.status_code == 403
    # Unchanged
    static = client.get("/admin/widgetthing/1/inline/name?cancel=1")
    # name still Alice; description not exposed via inline GET, but the row's
    # description field was not touched
    assert "Alice" in static.text


def test_post_inline_save_unchecked_boolean_persists_false() -> None:
    """Unchecked checkbox semantics for a bool field in list_editable."""
    client = _make_client()
    # Submitting without the field name → False
    response = client.post("/admin/widgetthing/1/inline/is_active", data={})
    assert response.status_code == 200
    body = response.text
    # Static cell shows False
    assert "False" in body or "false" in body.lower()


def test_post_inline_save_for_missing_item_returns_404() -> None:
    client = _make_client()
    response = client.post("/admin/widgetthing/9999/inline/name", data={"name": "x"})
    assert response.status_code == 404
