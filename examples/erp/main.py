import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from examples.erp.db import engine
from examples.erp.reports.views import router as reports_router
from hyperadmin import Admin
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.settings import HyperAdminSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create tables
    await admin._create_db_and_tables()

    # 2. Sync permissions (required for auth)
    await admin._sync_permissions()

    # 3. Seed data
    from examples.erp.seed import seed_db  # noqa: PLC0415

    await seed_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/hyperadmin/static"), name="static")

# Custom reports router
app.include_router(reports_router)

# Auth setup
auth_backend = SessionAuthBackend(engine=engine)
permission_registry = PermissionSyncService(engine=engine)
permission_checker = ModelPermissionChecker(engine=engine)

# Path to custom templates for this ERP app
base_dir = os.path.dirname(__file__)
template_dir = os.path.join(base_dir, "templates")

# All scalar config lives in HyperAdminSettings.
# Set HYPERADMIN_SECRET_KEY in your environment or .env file.
settings = HyperAdminSettings(
    secret_key=os.environ.get("HYPERADMIN_SECRET_KEY", "super-secret-erp-key"),
    create_tables=False,
    discover_apps=[
        "examples.erp.contacts",
        "examples.erp.sales",
        "examples.erp.purchases",
        "examples.erp.accounting",
        "hyperadmin.auth",
    ],
    template_dirs=[template_dir],
    debug=bool(os.environ.get("HYPERADMIN_DEBUG", "")),
)

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=auth_backend,
    permission_checker=permission_checker,
    permission_registry=permission_registry,
)

# Store admin on app state so custom views can access it (e.g. for templates)
app.state.admin = admin

admin.mount(path="/admin")

# Optional: Add custom report to the navigation menu
assert "nav_items" in admin.templates.env.globals, "Call admin.mount() before adding nav items"
admin.templates.env.globals["nav_items"].append(
    {"name": "Profit & Loss Report", "url": "/reports/profit-loss", "icon": "ha-icon-chart"}
)


@app.get("/")
def read_root():
    return {"message": "Go to /admin to see the ERP admin interface."}
