import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.db import create_db_and_tables


# 1. Define a SQLAlchemy model
class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


# 2. Define a ModelAdmin for it
class CategoryAdmin(ModelAdmin):
    pass


@pytest.mark.anyio
async def test_list_view_integration():
    """
    Tests that the list view for a registered model can be accessed.
    This validates the end-to-end integration of the adapter.
    """
    # Clear the registry before registering to ensure test isolation
    site._registry = {}
    site.register(Category, CategoryAdmin)

    # Manually create tables now that the Category model is defined
    await create_db_and_tables()

    # Setup the app inside the test function
    app = FastAPI()
    # Disable the automatic table creation in the Admin class
    admin = Admin(app, settings=HyperAdminSettings(create_tables=False))
    admin.mount("/admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/category")

    assert response.status_code == 200
    assert "Category" in response.text
