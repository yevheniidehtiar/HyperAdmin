"""Tests for the create view."""

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class ProductTest(SQLModel, table=True):
    __tablename__ = "test_product_create"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float


class ProductTestAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Ensures the site registry is clean before and after each test."""
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client():
    """Provides a TestClient with a clean database for each test."""
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(ProductTest, ProductTestAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_create_form_view_renders_form(client: TestClient):
    """Test that the create form view renders a form with the correct fields."""
    response = client.get("/admin/producttest/create")
    assert response.status_code == 200
    assert "<form" in response.text
    assert 'hx-post="http://testserver/admin/producttest"' in response.text
    assert '<label for="name"' in response.text
    assert '<input id="name" name="name"' in response.text
    assert '<label for="description"' in response.text
    assert '<textarea id="description" name="description"' in response.text
    assert '<label for="price"' in response.text
    assert '<input id="price" name="price" type="number"' in response.text
    assert 'id="id"' not in response.text  # ID should not be in the form


def test_create_view_successful_submission(client: TestClient):
    """Test successful form submission creates a new record and redirects."""
    form_data = {
        "name": "New Product",
        "description": "A shiny new product.",
        "price": "99.99",
    }
    headers = {"HX-Request": "true"}
    response = client.post(
        "/admin/producttest", data=form_data, headers=headers, follow_redirects=False
    )

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert response.headers["HX-Redirect"] == "http://testserver/admin/producttest/1"

    # Verify the item was created in the database
    get_response = client.get("/admin/producttest/1")
    assert get_response.status_code == 200
    assert "New Product" in get_response.text


def test_create_view_validation_error(client: TestClient):
    """Test that submitting invalid data returns only form body with errors for HTMX."""
    form_data = {
        "description": "A product with no name.",
        "price": "19.99",
    }
    headers = {"HX-Request": "true"}
    response = client.post(
        "/admin/producttest", data=form_data, headers=headers, follow_redirects=False
    )

    # HTMX fragment should be returned with 422 and include error text
    assert response.status_code == 422
    assert "Field required" in response.text

    # Should not include the full page or form wrapper when returning fragment
    assert "<html" not in response.text.lower()
    assert "<form" not in response.text.lower()

    # The inner inputs should still be present
    assert '<input id="name" name="name"' in response.text
