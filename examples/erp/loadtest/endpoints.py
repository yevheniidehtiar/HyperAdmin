"""URL builders, task weights, and payload generators for the Locust suite.

This module has **no** ``locust`` dependency: it is pure functions over a ``random.Random`` so
the weight distribution and URL generation can be unit-tested without the load-test extra.

The admin is mounted at ``/admin`` in ``examples/erp/main.py``. URL shapes mirror
``hyperadmin.routing``:

* list:    GET    ``/admin/{model}?page=&page_size=&search=&sort_by=&sort_direction=``
* detail:  GET    ``/admin/{model}/{id}``
* choices: GET    ``/admin/{model}/choices/{relation}``  (relation key, not the FK column)
* create:  POST   ``/admin/{model}``        (GET ``/admin/{model}/create`` for the form)
* update:  PUT    ``/admin/{model}/{id}``    (GET ``/admin/{model}/{id}/edit`` for the form)
* delete:  DELETE ``/admin/{model}/{id}``
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

if TYPE_CHECKING:
    import random

ADMIN_PREFIX = os.environ.get("LOADTEST_ADMIN_PREFIX", "/admin")

# Models exercised by read traffic (lower-cased class names = URL slugs).
READ_MODELS: tuple[str, ...] = ("contact", "invoice", "journalline")

# Read endpoint weights — must match the coverage table in epic #247.
READ_TASK_WEIGHTS: dict[str, int] = {
    "list": 40,
    "search": 15,
    "sort": 10,
    "detail": 15,
    "choices": 10,
}

# Write endpoint weights (create 5%, update 3%, delete 2% — 10% of total traffic).
WRITE_TASK_WEIGHTS: dict[str, int] = {
    "create": 5,
    "update": 3,
    "delete": 2,
}

# Sortable columns per model (valid sort_by values).
SORT_FIELDS: dict[str, tuple[str, ...]] = {
    "contact": ("name", "email", "contact_type"),
    "invoice": ("number", "date_issued", "date_due", "status"),
    "journalline": ("debit", "credit"),
}

# Relation keys usable with the choices endpoint (to-one relationships only).
CHOICE_FIELDS: dict[str, tuple[str, ...]] = {
    "invoice": ("customer",),
    "journalline": ("entry", "account"),
}
CHOICE_MODELS: tuple[str, ...] = tuple(CHOICE_FIELDS)

# Writes target the FK-free Contact model so generated payloads are always valid under load.
WRITE_MODEL = "contact"
CONTACT_TYPES: tuple[str, ...] = ("Customer", "Supplier", "Both")

PAGE_MIN, PAGE_MAX = 1, 1000
PAGE_SIZES: tuple[int, ...] = (10, 20, 50)
SORT_DIRECTIONS: tuple[str, ...] = ("asc", "desc")

# Default upper bound for random row IDs in detail/update/delete. Override with LOADTEST_MAX_ID
# to match the smallest seeded table so detail lookups rarely 404.
DEFAULT_MAX_ID = int(os.environ.get("LOADTEST_MAX_ID", "100"))

# Fallback search vocabulary when Faker is unavailable (e.g. in a minimal test env).
_FALLBACK_WORDS: tuple[str, ...] = (
    "acme",
    "global",
    "trading",
    "supply",
    "invoice",
    "services",
    "holdings",
    "logistics",
    "partners",
    "systems",
)


# -- URL builders --------------------------------------------------------------------------


def model_path(model: str) -> str:
    return f"{ADMIN_PREFIX}/{model}"


def list_url(model: str, *, page: int = 1, page_size: int = 20) -> str:
    return f"{model_path(model)}?page={page}&page_size={page_size}"


def search_url(model: str, term: str, *, page: int = 1) -> str:
    return f"{model_path(model)}?search={quote_plus(term)}&page={page}"


def sort_url(model: str, field: str, direction: str = "asc", *, page: int = 1) -> str:
    return f"{model_path(model)}?sort_by={field}&sort_direction={direction}&page={page}"


def detail_url(model: str, item_id: int) -> str:
    return f"{model_path(model)}/{item_id}"


def choices_url(model: str, relation: str, *, q: str = "", limit: int = 50) -> str:
    return f"{model_path(model)}/choices/{relation}?q={quote_plus(q)}&limit={limit}"


def create_form_url(model: str) -> str:
    return f"{model_path(model)}/create"


def create_url(model: str) -> str:
    return model_path(model)


def edit_form_url(model: str, item_id: int) -> str:
    return f"{model_path(model)}/{item_id}/edit"


def update_url(model: str, item_id: int) -> str:
    return f"{model_path(model)}/{item_id}"


def delete_url(model: str, item_id: int) -> str:
    return f"{model_path(model)}/{item_id}"


# Stable Locust stat names (collapse per-request params so the report stays readable).


def list_name(model: str) -> str:
    return f"GET {model_path(model)} [list]"


def search_name(model: str) -> str:
    return f"GET {model_path(model)} [search]"


def sort_name(model: str) -> str:
    return f"GET {model_path(model)} [sort]"


def detail_name(model: str) -> str:
    return f"GET {model_path(model)}/[id]"


def choices_name(model: str) -> str:
    return f"GET {model_path(model)}/choices/[rel]"


# -- random parameter generators -----------------------------------------------------------


def random_page(rng: random.Random) -> int:
    return rng.randint(PAGE_MIN, PAGE_MAX)


def random_page_size(rng: random.Random) -> int:
    return rng.choice(PAGE_SIZES)


def random_direction(rng: random.Random) -> str:
    return rng.choice(SORT_DIRECTIONS)


def random_read_model(rng: random.Random) -> str:
    return rng.choice(READ_MODELS)


def random_choice_model(rng: random.Random) -> str:
    return rng.choice(CHOICE_MODELS)


def random_sort_field(model: str, rng: random.Random) -> str:
    return rng.choice(SORT_FIELDS[model])


def random_choice_field(model: str, rng: random.Random) -> str:
    return rng.choice(CHOICE_FIELDS[model])


def random_item_id(rng: random.Random, max_id: int = DEFAULT_MAX_ID) -> int:
    return rng.randint(1, max(1, max_id))


def random_search_term(rng: random.Random) -> str:
    """Return a non-empty search term, preferring Faker when it is installed."""
    try:
        from faker import Faker  # noqa: PLC0415 - optional; fall back to a static vocabulary
    except ImportError:
        return rng.choice(_FALLBACK_WORDS)
    fake = Faker()
    fake.seed_instance(rng.randint(0, 2**31 - 1))
    return fake.word()


# -- write payloads ------------------------------------------------------------------------


def contact_payload(rng: random.Random) -> dict[str, str]:
    """Build a valid Contact create/update form payload (no foreign keys)."""
    suffix = rng.randint(0, 2**31 - 1)
    try:
        from faker import Faker  # noqa: PLC0415 - optional; fall back to synthetic values
    except ImportError:
        name = f"{rng.choice(_FALLBACK_WORDS).title()} Co {suffix}"
        return {
            "name": name,
            "email": f"contact{suffix}@example.com",
            "phone": f"+1-555-{suffix % 10000:04d}",
            "contact_type": rng.choice(CONTACT_TYPES),
        }
    fake = Faker()
    fake.seed_instance(suffix)
    return {
        "name": fake.company(),
        "email": f"loadtest{suffix}@{fake.domain_name()}",
        "phone": fake.phone_number()[:20],
        "contact_type": rng.choice(CONTACT_TYPES),
    }
