"""Tests that IntegrityError on create/update re-renders form with field errors."""

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


class UniqueUser(SQLModel, table=True):
    __tablename__ = "test_unique_user"
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    email: str


class UniqueUserAdmin(ModelAdmin):
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

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(UniqueUser, UniqueUserAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_create_duplicate_shows_field_error(client: TestClient):
    """Creating a record that violates a UNIQUE constraint shows a form error."""
    form_data = {"username": "alice", "email": "alice@example.com"}
    headers = {"HX-Request": "true"}

    # First create succeeds
    response = client.post("/admin/uniqueuser", data=form_data, headers=headers)
    assert response.status_code == 200
    assert "HX-Redirect" in response.headers

    # Second create with same username returns 422 with field error
    form_data["email"] = "alice2@example.com"
    response = client.post("/admin/uniqueuser", data=form_data, headers=headers)
    assert response.status_code == 422
    assert "already exists" in response.text.lower()


def test_update_duplicate_shows_field_error(client: TestClient):
    """Updating a record to violate a UNIQUE constraint shows a form error."""
    headers = {"HX-Request": "true"}

    # Create two records
    client.post(
        "/admin/uniqueuser", data={"username": "alice", "email": "a@e.com"}, headers=headers
    )
    client.post("/admin/uniqueuser", data={"username": "bob", "email": "b@e.com"}, headers=headers)

    # Update bob's username to alice (conflict)
    response = client.put(
        "/admin/uniqueuser/2",
        data={"username": "alice", "email": "b@e.com"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "already exists" in response.text.lower()
