"""Unit tests for the Locust task weights and URL/param generation (#260).

These import only ``examples.erp.loadtest.endpoints`` — never ``locust`` — so they run in the
plain unit environment without the load-test extra.
"""

import random
from collections import Counter

import pytest
from examples.erp.loadtest import endpoints as ep


def _rng(seed=42):
    return random.Random(seed)  # noqa: S311 - test RNG


class TestTaskWeights:
    def test_read_weights_match_spec(self):
        assert ep.READ_TASK_WEIGHTS == {
            "list": 40,
            "search": 15,
            "sort": 10,
            "detail": 15,
            "choices": 10,
        }
        # Read traffic sums to 90% of the 100% total (writes are the other 10%).
        assert sum(ep.READ_TASK_WEIGHTS.values()) == 90

    def test_write_weights_match_spec(self):
        assert ep.WRITE_TASK_WEIGHTS == {"create": 5, "update": 3, "delete": 2}
        assert sum(ep.WRITE_TASK_WEIGHTS.values()) == 10

    def test_full_distribution_sums_to_100(self):
        total = sum(ep.READ_TASK_WEIGHTS.values()) + sum(ep.WRITE_TASK_WEIGHTS.values())
        assert total == 100

    def test_weighted_sampling_approximates_declared_weights(self):
        # Simulate Locust's weighted task picking and confirm the empirical mix is close.
        rng = _rng()
        tasks = list(ep.READ_TASK_WEIGHTS) + list(ep.WRITE_TASK_WEIGHTS)
        weights = list(ep.READ_TASK_WEIGHTS.values()) + list(ep.WRITE_TASK_WEIGHTS.values())
        picks = Counter(rng.choices(tasks, weights=weights, k=20_000))
        assert 0.35 <= picks["list"] / 20_000 <= 0.45  # ~40%
        assert 0.02 <= picks["update"] / 20_000 <= 0.05  # ~3%


class TestModelCoverage:
    def test_read_models_cover_contact_invoice_journalline(self):
        assert set(ep.READ_MODELS) == {"contact", "invoice", "journalline"}

    def test_choice_models_only_have_to_one_relations(self):
        assert set(ep.CHOICE_MODELS) == {"invoice", "journalline"}
        assert "contact" not in ep.CHOICE_MODELS

    def test_random_read_model_eventually_covers_all(self):
        rng = _rng()
        seen = {ep.random_read_model(rng) for _ in range(200)}
        assert seen == set(ep.READ_MODELS)


class TestUrlGeneration:
    def test_list_url_shape(self):
        url = ep.list_url("contact", page=3, page_size=20)
        assert url == "/admin/contact?page=3&page_size=20"

    def test_search_url_escapes_term(self):
        url = ep.search_url("invoice", "acme & co", page=1)
        assert url.startswith("/admin/invoice?search=")
        assert "acme+%26+co" in url

    def test_sort_url_shape(self):
        assert ep.sort_url("journalline", "debit", "desc", page=2) == (
            "/admin/journalline?sort_by=debit&sort_direction=desc&page=2"
        )

    def test_detail_choices_crud_urls(self):
        assert ep.detail_url("contact", 7) == "/admin/contact/7"
        assert ep.choices_url("invoice", "customer").startswith("/admin/invoice/choices/customer?")
        assert ep.create_form_url("contact") == "/admin/contact/create"
        assert ep.create_url("contact") == "/admin/contact"
        assert ep.edit_form_url("contact", 5) == "/admin/contact/5/edit"
        assert ep.update_url("contact", 5) == "/admin/contact/5"
        assert ep.delete_url("contact", 5) == "/admin/contact/5"

    def test_admin_prefix_used_consistently(self):
        for url in (
            ep.list_url("contact"),
            ep.detail_url("invoice", 1),
            ep.create_url("journalline"),
        ):
            assert url.startswith("/admin/")

    def test_stat_names_collapse_params(self):
        # Names must not contain volatile ids/pages, or the Locust report explodes.
        assert ep.detail_name("contact") == "GET /admin/contact/[id]"
        assert "[id]" in ep.detail_name("invoice")


class TestRandomParams:
    def test_random_page_in_range(self):
        rng = _rng()
        for _ in range(500):
            assert ep.PAGE_MIN <= ep.random_page(rng) <= ep.PAGE_MAX

    def test_random_sort_field_valid_for_model(self):
        rng = _rng()
        for model in ep.READ_MODELS:
            for _ in range(50):
                assert ep.random_sort_field(model, rng) in ep.SORT_FIELDS[model]

    def test_random_choice_field_valid(self):
        rng = _rng()
        for model in ep.CHOICE_MODELS:
            for _ in range(50):
                assert ep.random_choice_field(model, rng) in ep.CHOICE_FIELDS[model]

    def test_random_item_id_positive_within_max(self):
        rng = _rng()
        for _ in range(500):
            assert 1 <= ep.random_item_id(rng, max_id=50) <= 50

    def test_random_item_id_handles_zero_max(self):
        # max_id floors at 1 so randint never gets an empty range.
        assert ep.random_item_id(_rng(), max_id=0) == 1

    def test_random_search_term_nonempty(self):
        rng = _rng()
        for _ in range(20):
            term = ep.random_search_term(rng)
            assert isinstance(term, str)
            assert term


class TestPayloads:
    def test_contact_payload_has_required_fields(self):
        payload = ep.contact_payload(_rng())
        assert set(payload) == {"name", "email", "phone", "contact_type"}
        assert payload["contact_type"] in ep.CONTACT_TYPES
        assert payload["name"]

    def test_contact_payloads_vary(self):
        rng = _rng()
        emails = {ep.contact_payload(rng)["email"] for _ in range(20)}
        assert len(emails) > 1


@pytest.mark.parametrize("model", ["contact", "invoice", "journalline"])
def test_every_read_model_has_sort_fields(model):
    assert ep.SORT_FIELDS[model]
