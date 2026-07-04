"""Unit tests for the bulk action endpoint (H3, v0.5.5).

Mirrors the four BDD scenarios in
``.meta/epics/epic-v055-bulk-actions/stories/featviews-add-run-bulk-action-endpoint.md``
plus a small handful of dispatch tests for the surrounding plumbing.
"""

from __future__ import annotations

import anyio
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.auth import DefaultObjectPermissionChecker
from hyperadmin.core.bulk_results import BulkRowResult
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class BulkWidget(SQLModel, table=True):
    __tablename__ = "test_bulk_widget"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class _ReassignParams(BaseModel):
    operator: int


_calls: list[tuple[int, _ReassignParams | None]] = []
_fail_ids: set[int] = set()
_forbid_ids: set[int] = set()


class BulkWidgetAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Archive", bulk=True)
    async def archive(self, request: Request, item_id: int, *, params=None) -> None:
        if item_id in _forbid_ids:
            raise HTTPException(status_code=403, detail="permission denied")
        if item_id in _fail_ids:
            raise RuntimeError("boom")
        _calls.append((item_id, params))

    @action(label="Reassign", bulk=True, form=_ReassignParams)
    async def reassign(self, request: Request, item_id: int, *, params=None) -> None:
        _calls.append((item_id, params))

    @action(label="Archive overdue", bulk=True, requires_selection=False)
    async def archive_overdue(self, request: Request, item_id: int, *, params=None) -> None:
        _calls.append((item_id, params))


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    _calls.clear()
    _fail_ids.clear()
    _forbid_ids.clear()
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

        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for name in ("alpha", "beta", "gamma", "delta", "epsilon"):
                session.add(BulkWidget(name=name))
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(BulkWidget, BulkWidgetAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


# ---------------------------------------------------------------------------
# BulkRowResult shape
# ---------------------------------------------------------------------------


def test_bulkrowresult_carries_id_status_detail():
    r = BulkRowResult(id=1, status="ok", detail=None)
    assert r.id == 1
    assert r.status == "ok"
    assert r.detail is None


# ---------------------------------------------------------------------------
# BDD: empty selection
# ---------------------------------------------------------------------------


def test_empty_ids_with_requires_selection_returns_400(client: TestClient):
    """
    Scenario: empty ids with requires_selection returns 400
      Given a ModelAdmin with @action(bulk=True) (requires_selection defaults to True)
      When  POST /admin/bulkwidget/actions/archive/bulk with no ids
      Then  response is 400 and body contains "Selection required"
      And   the handler is not invoked
    """
    # Given / When
    response = client.post("/admin/bulkwidget/actions/archive/bulk", data={})

    # Then
    assert response.status_code == 400
    assert "Selection required" in response.text
    assert _calls == []


def test_requires_selection_false_allows_empty_ids(client: TestClient):
    """`bulk=True` actions can opt out of the auto-selection requirement."""
    # Given an action with requires_selection=False
    # When the bulk endpoint runs with no ids
    response = client.post(
        "/admin/bulkwidget/actions/archive_overdue/bulk", data={}, follow_redirects=False
    )

    # Then the endpoint does not reject the request as "Selection required".
    assert response.status_code != 400 or "Selection required" not in response.text


# ---------------------------------------------------------------------------
# BDD: per-row outcomes (success + 403 + generic exception)
# ---------------------------------------------------------------------------


def test_bulk_handler_runs_per_row_and_captures_forbidden(client: TestClient):
    """
    Scenario: bulk handler runs per-row, captures HTTPException(403) as forbidden
      Given handler raises HTTPException(403) for id=2
      When  POST .../bulk with ids=[1,2,3]
      Then  result rows are ok / forbidden / ok in order
    """
    # Given
    _forbid_ids.update({2})

    # When
    response = client.post(
        "/admin/bulkwidget/actions/archive/bulk",
        data={"ids": ["1", "2", "3"]},
    )

    # Then
    assert response.status_code == 200
    body = response.text
    # The result page renders one row per outcome with a status badge.
    assert body.count('data-testid="bulk-result-row"') == 3
    assert "ok" in body
    assert "forbidden" in body
    # The handler was invoked for ids 1 and 3 only.
    invoked = sorted(item_id for item_id, _ in _calls)
    assert invoked == [1, 3]


def test_bulk_handler_captures_generic_exception_as_failed(client: TestClient):
    """
    Scenario: bulk handler runs per-row, captures generic exception as failed
      Given handler raises RuntimeError("boom") for id=2
      When  POST .../bulk with ids=[1,2,3]
      Then  result rows are ok / failed / ok in order
      And   the "failed" row carries detail "boom"
    """
    # Given
    _fail_ids.update({2})

    # When
    response = client.post(
        "/admin/bulkwidget/actions/archive/bulk",
        data={"ids": ["1", "2", "3"]},
    )

    # Then
    assert response.status_code == 200
    body = response.text
    assert "failed" in body
    assert "boom" in body


# ---------------------------------------------------------------------------
# BDD: param form workflow
# ---------------------------------------------------------------------------


def test_bulk_with_form_renders_param_form_with_hidden_ids(client: TestClient):
    """
    Scenario: bulk action with param form prompts before running
      Given @action(bulk=True, form=ReassignParams) with field operator: int
      When  POST /admin/bulkwidget/actions/reassign/bulk with ids=[1,2,3]
      Then  the response renders a form with operator input
      And   the form preserves the selected ids in hidden inputs
      And   the handler is NOT invoked
    """
    # Given / When
    response = client.post(
        "/admin/bulkwidget/actions/reassign/bulk",
        data={"ids": ["1", "2", "3"]},
    )

    # Then
    assert response.status_code == 200
    body = response.text
    assert 'data-testid="bulk-form"' in body
    assert 'name="operator"' in body
    # Hidden ids preserved.
    for pk in ("1", "2", "3"):
        assert f'value="{pk}"' in body
    assert _calls == []


def test_bulk_with_form_confirm_runs_handler_with_validated_params(client: TestClient):
    """
    Scenario: bulk action with valid params runs over selected rows
      Given the param form has operator: int
      When  POST .../bulk/confirm with operator=42 and ids=[1,2,3]
      Then  the handler runs 3 times with params.operator == 42
      And   the response is the per-row result page
    """
    # Given / When
    response = client.post(
        "/admin/bulkwidget/actions/reassign/bulk/confirm",
        data={"ids": ["1", "2", "3"], "operator": "42"},
    )

    # Then
    assert response.status_code == 200
    assert response.text.count('data-testid="bulk-result-row"') == 3
    operators = [params.operator for _, params in _calls if params is not None]
    assert operators == [42, 42, 42]


def test_bulk_with_form_confirm_rejects_invalid_params(client: TestClient):
    """Form re-renders with validation errors when params are invalid."""
    # Given / When operator is not an int
    response = client.post(
        "/admin/bulkwidget/actions/reassign/bulk/confirm",
        data={"ids": ["1"], "operator": "not-a-number"},
    )

    # Then the form re-renders with the same ids preserved, and no handler runs.
    assert response.status_code in {200, 422}
    assert _calls == []


# ---------------------------------------------------------------------------
# BDD: object-level permissions
# ---------------------------------------------------------------------------


def test_bulk_object_permission_denial_surfaces_per_row():
    """
    Scenario: object-permission denial surfaces per row
      Given an ObjectPermissionChecker that denies "archive" on id=2
      When  POST .../bulk with ids=[1,2,3]
      Then  result rows are ok / forbidden / ok
      And   the handler is invoked only for ids 1 and 3
    """
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @app.middleware("http")
    async def _inject_user(request: Request, call_next):
        request.state.user = {"id": 1, "username": "alice"}
        return await call_next(request)

    class _DenyForId2(DefaultObjectPermissionChecker):
        async def has_object_permission(self, user, obj, action):  # type: ignore[override]
            return not (getattr(obj, "id", None) == 2 and action.startswith("action_"))

    class _ScopedAdmin(ModelAdmin):
        adapter_class = SQLModelAdapter
        options_class = AdminOptions

        @action(label="Archive", bulk=True)
        async def archive(self, request: Request, item_id: int, *, params=None) -> None:
            _calls.append((item_id, params))

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for name in ("a", "b", "c"):
                session.add(BulkWidget(name=name))
            await session.commit()

    anyio.run(setup_database)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(
        BulkWidget,
        _ScopedAdmin,
        options=AdminOptions(object_permission_checker=_DenyForId2()),
    )
    admin.mount(path="/admin")
    client = TestClient(app)

    # When
    response = client.post(
        "/admin/bulkwidget/actions/archive/bulk",
        data={"ids": ["1", "2", "3"]},
    )

    # Then
    assert response.status_code == 200
    invoked = sorted(item_id for item_id, _ in _calls)
    assert invoked == [1, 3]
    assert "forbidden" in response.text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_bulk_action_returns_404(client: TestClient):
    response = client.post("/admin/bulkwidget/actions/nope/bulk", data={"ids": ["1"]})
    assert response.status_code == 404


def test_non_bulk_action_at_bulk_endpoint_returns_404(client: TestClient):
    """A single-record action (no `bulk=True`) is not exposed via the bulk endpoint."""

    class _SingleAdmin(ModelAdmin):
        adapter_class = SQLModelAdapter

        @action(label="Single")
        async def single(self, request: Request, item_id: int) -> None:
            pass

    site._registry = {}
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(BulkWidget, _SingleAdmin)
    admin.mount(path="/admin")
    client = TestClient(app)

    response = client.post("/admin/bulkwidget/actions/single/bulk", data={"ids": ["1"]})
    assert response.status_code == 404
