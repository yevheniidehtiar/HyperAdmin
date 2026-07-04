"""Tests for the detail view."""

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


class ProductTestDetail(SQLModel, table=True):
    __tablename__ = "test_product_detail"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float


class ProductTestDetailAdmin(ModelAdmin):
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
            product = ProductTestDetail(
                name="Detail Product", description="Detail description", price=30.0
            )
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(ProductTestDetail, ProductTestDetailAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_detail_view_renders_correctly(client: TestClient):
    response = client.get("/admin/producttestdetail/1")
    assert response.status_code == 200
    assert "Detail Product" in response.text
    assert "Detail description" in response.text
    assert "30.0" in response.text
    assert "Name" in response.text
    assert "Description" in response.text
    assert "Price" in response.text


def test_detail_view_not_found(client: TestClient):
    response = client.get("/admin/producttestdetail/999")
    assert response.status_code == 404
