import pytest

# WIP: oauth backend test requires cryptography + providers/tokens modules not yet merged.
# Remove this entry once the oauth package is complete (issue #441).
collect_ignore = ["unit/test_oauth_backend.py"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
