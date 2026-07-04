<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="https://yevheniidehtiar.github.io/hyper-admin/assets/logo.svg" alt="HyperAdmin Logo" width="140"/>
  </a>
  <h1>HyperAdmin</h1>
  <p><strong>The Django-admin experience for FastAPI — generated straight from your Pydantic models.</strong></p>

  <p>
    <a href="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml">
      <img src="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml/badge.svg?branch=develop" alt="CI">
    </a>
    <a href="https://yevheniidehtiar.github.io/hyper-admin/">
      <img src="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/pages.yml/badge.svg?branch=develop" alt="Docs">
    </a>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
    </a>
    <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha">
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
    </a>
    <a href="https://codespaces.new/yevheniidehtiar/hyper-admin?devcontainer_path=.devcontainer%2Fdevcontainer.json">
      <img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" height="20">
    </a>
  </p>

  <sub><strong>Alpha</strong> — under active development; APIs may change between releases.</sub>

  <br/><br/>
  <img src="docs/assets/demo/list.png" alt="HyperAdmin list view" width="820"/>
</div>

---

## The story

FastAPI gives you a fast API — but no batteries-included admin, the way Django has. So
every team rebuilds the same CRUD screens by hand, and they drift out of sync with the
models behind them.

HyperAdmin closes that gap. Point it at the Pydantic / SQLModel models you **already**
have and it generates a full admin — list, detail, create, update, search, filters,
auth — at a mount point in your existing app. No second schema to maintain, no JavaScript
build step. The models are the single source of truth; the UI can't drift from them
because it's derived from them.

It's built model-first (domain → logic → views → UI) and developed with an AI-assisted
[agentic workflow](https://yevheniidehtiar.github.io/hyper-admin/agentic-workflow/).

## Why the Pydantic stack

| Choice | Why |
|---|---|
| **Pydantic v2 / SQLModel** | Your models already encode types, validation, and field metadata. HyperAdmin reads them directly, so forms, filters and detail views are *generated*, never hand-written — and stay correct by construction. |
| **FastAPI** | Same async runtime, same dependency injection, same app. HyperAdmin mounts in; it doesn't take over. |
| **HTMX + Jinja2** | Server-rendered HTML with interactivity sent over the wire. A rich admin with a tiny JS surface — no SPA, no node build, progressive enhancement by default. |
| **SQLAlchemy 2.0 (async)** | A mature, async data layer underneath SQLModel — works with the databases you already run. |

## Quickstart

Not on PyPI yet — install from source:

```bash
pip install "git+https://github.com/yevheniidehtiar/hyper-admin.git"
```

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, Field
from hyperadmin import Admin
from hyperadmin.core.registry import site

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

engine = create_async_engine("sqlite+aiosqlite:///app.db")
app = FastAPI()
admin = Admin(app, engine=engine)
site.register(Product)
admin.mount("/admin")        # full CRUD admin now live at /admin
```

Prefer to click around first? **[Open the demo in Codespaces](https://codespaces.new/yevheniidehtiar/hyper-admin?devcontainer_path=.devcontainer%2Fdevcontainer.json)** or browse the [screenshot tour](https://yevheniidehtiar.github.io/hyper-admin/demo/).

## Resource map

| | |
|---|---|
| 📖 **Documentation** | <https://yevheniidehtiar.github.io/hyper-admin/> |
| ▶️ **Live demo & tour** | [docs › Live Demo](https://yevheniidehtiar.github.io/hyper-admin/demo/) · [Open in Codespaces](https://codespaces.new/yevheniidehtiar/hyper-admin?devcontainer_path=.devcontainer%2Fdevcontainer.json) |
| 🚀 **Getting started** | [docs › Getting Started](https://yevheniidehtiar.github.io/hyper-admin/getting-started/) |
| 🧩 **Example app (ERP)** | [`examples/erp/`](examples/erp) · [docs › ERP](https://yevheniidehtiar.github.io/hyper-admin/examples/erp/) |
| 🗺️ **Roadmap** | [docs › Roadmap](https://yevheniidehtiar.github.io/hyper-admin/roadmap/) · [`ROADMAP.md`](ROADMAP.md) |
| 🏛️ **Architecture** | [`CONSTITUTION.md`](CONSTITUTION.md) — principles, module boundaries, dependency rules |
| 🤝 **Contributing** | [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| 🔒 **Security** | [`SECURITY.md`](SECURITY.md) |
| 📓 **Changelog** | [docs › Changelog](https://yevheniidehtiar.github.io/hyper-admin/changelog/) |

## Tech stack

**[FastAPI](https://fastapi.tiangolo.com/)** ·
**[Pydantic v2](https://docs.pydantic.dev/)** ·
**[SQLModel](https://sqlmodel.tiangolo.com/)** / **[SQLAlchemy 2.0](https://www.sqlalchemy.org/)** ·
**[HTMX](https://htmx.org/)** ·
**[Jinja2](https://jinja.palletsprojects.com/)** ·
[Starlette](https://www.starlette.io/) sessions ·
[Argon2](https://argon2-cffi.readthedocs.io/) ·
[Babel](https://babel.pocoo.org/) i18n ·
[Typer](https://typer.tiangolo.com/) CLI ·
[uv](https://docs.astral.sh/uv/) + [Ruff](https://docs.astral.sh/ruff/)

## Development

```bash
just bootstrap   # set up the dev environment (uv sync --all-extras)
just lint        # ruff + mypy + commitizen
just test        # unit tests (just test-e2e for Playwright e2e)
just run-erp     # run the example ERP admin locally
just docs        # serve docs locally on :8080
```

## Acknowledgements

Standing on the shoulders of [Django](https://www.djangoproject.com/) (the original
batteries-included admin), [FastAPI](https://fastapi.tiangolo.com/),
[Pydantic](https://docs.pydantic.dev/), [HTMX](https://htmx.org/), and
[SQLModel](https://sqlmodel.tiangolo.com/) / [SQLAlchemy](https://www.sqlalchemy.org/) —
and built with AI-assisted development via [Claude](https://www.anthropic.com/).

## License

MIT — see [LICENSE](LICENSE).
