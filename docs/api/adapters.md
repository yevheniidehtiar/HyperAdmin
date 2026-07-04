# Adapters

Adapters translate between a data source (SQLModel, SQLAlchemy, or custom) and HyperAdmin's view layer.

## Built-in Adapters

| Adapter | Module | Works with |
|---------|--------|------------|
| `SQLModelAdapter` | `hyperadmin.adapters.sqlmodel` | SQLModel async models |
| `SQLAlchemyAdapter` | `hyperadmin.adapters.sqlalchemy` | SQLAlchemy async models |

HyperAdmin auto-selects the right adapter at registration time via the adapter registry.

## Writing a custom adapter

Subclass `BaseAdapter` and implement all abstract methods:

```python
from hyperadmin.core.adapters import BaseAdapter

class MyAdapter(BaseAdapter):
    async def get(self, pk):
        ...

    async def list(self, page=1, page_size=10, search=None, filters=None, order_by=None):
        # Return (items, total_count)
        ...

    async def create(self, data):
        ...

    async def update(self, pk, data):
        ...

    async def delete(self, pk):
        ...

    async def get_related(self, pk, field):
        ...

    async def get_schema(self):
        ...
```

Register it with the adapter registry so HyperAdmin can discover it automatically:

```python
from hyperadmin.adapters.registry import adapter_registry
adapter_registry.register(MyModel, MyAdapter)
```

## API Reference

::: hyperadmin.core.adapters.BaseAdapter

::: hyperadmin.adapters.sqlmodel.SQLModelAdapter

::: hyperadmin.adapters.sqlalchemy.SQLAlchemyAdapter