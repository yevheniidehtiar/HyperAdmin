"""Tests for the update view."""

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


class ProductTestUpdate(SQLModel, table=True):
    __tablename__ = "test_product_update"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float
    is_active: bool = Field(default=True)


class ProductTestUpdateAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
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

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            product = ProductTestUpdate(
                name="Old Product", description="Old description", price=10.0, is_active=True
            )
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(ProductTestUpdate, ProductTestUpdateAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_update_form_view_renders_form(client: TestClient):
    response = client.get("/admin/producttestupdate/1/edit")
    assert response.status_code == 200
    assert "<form" in response.text
    assert "/admin/producttestupdate/1" in response.text
    assert 'value="Old Product"' in response.text
    assert "Old description" in response.text
    assert 'value="10.0"' in response.text
    assert "checked" in response.text


def test_update_view_successful_submission(client: TestClient):
    form_data = {
        "name": "Updated Product",
        "description": "Updated description",
        "price": "20.0",
        "is_active": "on",
    }
    response = client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert response.headers["HX-Redirect"] == "http://testserver/admin/producttestupdate"

    get_response = client.get("/admin/producttestupdate/1")
    assert get_response.status_code == 200
    assert "Updated Product" in get_response.text


def test_update_view_validation_error(client: TestClient):
    form_data = {
        "name": "Updated",
        "description": "Updated description",
        "price": "not-a-number",
    }
    response = client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Input should be a valid number" in response.text
    assert "Updated description" in response.text


def test_update_view_uncheck_boolean(client: TestClient):
    form_data = {
        "name": "Unchecked Product",
        "description": "Desc",
        "price": "10.0",
        # is_active omitted — should become False
    }
    client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    get_response = client.get("/admin/producttestupdate/1")
    assert '"is_active": false' in get_response.text.lower() or "False" in get_response.text


def test_update_view_partial_update_preserves_missing_text_field(client: TestClient):
    form_data = {
        "name": "Partial Update",
        "price": "50.0",
        "is_active": "on",
        # description omitted
    }
    client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    get_response = client.get("/admin/producttestupdate/1")
    assert "Old description" in get_response.text
