<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="assets/logo.svg" alt="HyperAdmin Logo" width="150"/>
  </a>
  <h1>HyperAdmin</h1>
  <p>A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.</p>
</div>

---

```bash
pip install hyperadmin
```

**HyperAdmin** is a framework for building administrative interfaces on top of FastAPI. It uses **Pydantic** for data validation and **HTMX** for dynamic UIs with minimal JavaScript.

## Quick example

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
admin.mount("/admin")
```

## Where to go next

- [Getting Started](getting-started.md) — Install and build your first admin
- [Tutorial](tutorial.md) — Step-by-step walkthrough
- [Examples](examples.md) — Two runnable apps (simple CRUD + Bookkeeping ERP)
- [Frontend](frontend/overview.md) — Templates, CSS tokens, widgets, HTMX patterns
- [API Reference](api/index.md) — Full class and method documentation
- [Contributing](contributing.md) — Development setup and contribution workflow
- [Roadmap](roadmap.md) — What's shipped and what's coming next

## Key features

- **Pydantic-native** — define admin interfaces directly from your models
- **FastAPI integration** — mounts seamlessly into any FastAPI app
- **HTMX-powered** — rich interactive UI without complex JavaScript
- **SQLModel & SQLAlchemy** — works out of the box with both ORMs
- **Automatic CRUD** — list, detail, create, and update views generated automatically
- **Extensible** — override templates, customize views, and add custom actions

---

Next: [Getting Started](getting-started.md)
