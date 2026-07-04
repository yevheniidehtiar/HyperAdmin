from unittest.mock import MagicMock

import pytest

from hyperadmin.adapters.registry import AdapterNotFoundError, AdapterRegistry
from hyperadmin.core.adapters import BaseAdapter


def test_register_and_find_adapter():
    # Arrange
    registry = AdapterRegistry()
    orm_base = MagicMock()
    adapter_class = MagicMock(spec=BaseAdapter)
    model_class = MagicMock()
    model_class.__mro__ = (model_class, orm_base, object)

    # Act
    registry.register(orm_base, adapter_class)
    found_adapter = registry.find_adapter_for_model(model_class)

    # Assert
    assert found_adapter == adapter_class


def test_find_adapter_not_found():
    # Arrange
    registry = AdapterRegistry()
    model_class = MagicMock()
    model_class.__mro__ = (model_class, object)
    model_class.__name__ = "TestModel"

    # Act & Assert
    with pytest.raises(AdapterNotFoundError) as exc_info:
        registry.find_adapter_for_model(model_class)

    assert "No suitable adapter found for model TestModel" in str(exc_info.value)
