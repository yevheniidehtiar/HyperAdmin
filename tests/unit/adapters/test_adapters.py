import builtins
from typing import Any

import pytest

from hyperadmin.core.adapters import BaseAdapter


def test_base_adapter_is_abstract():
    """
    Tests that BaseAdapter is an abstract class and cannot be instantiated.
    """
    with pytest.raises(TypeError):
        BaseAdapter(model=None, engine=None)


def test_concrete_adapter_must_implement_all_methods():
    """
    Tests that a concrete implementation of BaseAdapter must implement all abstract methods.
    """

    class ConcreteAdapter(BaseAdapter):
        async def get(self, pk: Any) -> Any:
            pass

        async def list(
            self,
            page: int = 1,
            page_size: int = 10,
            search: str | None = None,
            filters: dict[str, Any] | None = None,
            order_by: str | None = None,
            search_fields: list[str] | None = None,
        ) -> tuple[list[Any], int]:
            pass

        async def create(self, data: dict[str, Any]) -> Any:
            pass

        async def update(self, pk: Any, data: dict[str, Any]) -> Any:
            pass

        async def delete(self, pk: Any) -> None:
            pass

        async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
            pass

        async def get_schema(self) -> dict[str, Any]:
            pass

        async def get_choices(
            self,
            field: str,
            q: str = "",
            limit: int = 50,
            offset: int = 0,
            **filters: Any,
        ) -> builtins.list:
            pass

        async def save_inline_rows(self, spec: Any, rows: builtins.list, parent_pk: Any) -> None:
            pass

    # This should not raise an error
    ConcreteAdapter(model=None, engine=None)


def test_incomplete_adapter_raises_error():
    """
    Tests that a concrete implementation of BaseAdapter that misses some abstract methods
    raises a TypeError.
    """

    class IncompleteAdapter(BaseAdapter):
        async def get(self, pk: Any) -> Any:
            pass

    with pytest.raises(TypeError):
        IncompleteAdapter(model=None, engine=None)
