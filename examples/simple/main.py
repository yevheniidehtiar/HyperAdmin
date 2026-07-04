import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from examples.simple.models import City, Country, User, upload_storage
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

# 1. Create a database engine
DB_URL = (
    "sqlite+aiosqlite:///:memory:"
    if os.environ.get("E2E_TESTING")
    else "sqlite+aiosqlite:///simple_app.db"
)
engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        result = await session.execute(select(User))
        if not result.first():
            session.add(User(name="Alice", email="alice@example.com"))
            session.add(User(name="Bob", email="bob@example.com"))
            session.add(User(name="Charlie", email="charlie@example.com"))
            await session.commit()

    async with AsyncSession(engine) as session:
        result = await session.execute(select(Country))
        if not result.first():
            uk = Country(name="United Kingdom")
            fr = Country(name="France")
            session.add_all([uk, fr])
            await session.commit()
            await session.refresh(uk)
            await session.refresh(fr)
            session.add_all(
                [
                    City(name="London", country_id=uk.id),
                    City(name="Manchester", country_id=uk.id),
                    City(name="Paris", country_id=fr.id),
                ]
            )
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


# 2. Configure HyperAdmin via settings (reads HYPERADMIN_* env vars and .env)
settings = HyperAdminSettings(
    discover_apps=["examples.simple"],
)

# 3. Create a FastAPI app and an Admin instance
app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/hyperadmin/static"), name="static")
admin = Admin(app, engine=engine, settings=settings, storage=upload_storage)

# 4. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
