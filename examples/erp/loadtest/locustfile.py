"""Locust load test for the HyperAdmin ERP example.

Run against a seeded instance::

    locust -f examples/erp/loadtest/locustfile.py --host http://localhost:8000

Two user classes model the traffic mix from epic #247:

* ``ReadUser``  — list (40%), search (15%), sort (10%), detail (15%), choices (10%)
* ``WriteUser`` — create (5%), update (3%), delete (2%)

All URL/weight/payload logic lives in :mod:`examples.erp.loadtest.endpoints` (locust-free and
unit-tested). Detail/update/delete on a random id may legitimately 404 — those are treated as
successes so the error rate reflects real failures, not "row not found".
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

from examples.erp.loadtest import endpoints as ep
from examples.erp.loadtest.auth_mixin import HyperAdminAuthMixin

# Status codes that mean "the request was handled" for each verb.
_READ_OK = (200, 404)
_WRITE_OK = (200, 201, 302, 404)


class ReadUser(HyperAdminAuthMixin, HttpUser):
    """Simulates a user browsing the admin: lists, searches, sorts, details, FK choices."""

    weight = 9  # 90% of the population reads (matches the 90/10 read/write split)
    wait_time = between(0.5, 2.0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rng = random.Random()  # noqa: S311 - per-user load-shape RNG, not security

    @task(ep.READ_TASK_WEIGHTS["list"])
    def list_view(self) -> None:
        model = ep.random_read_model(self._rng)
        url = ep.list_url(
            model, page=ep.random_page(self._rng), page_size=ep.random_page_size(self._rng)
        )
        self.client.get(url, name=ep.list_name(model))

    @task(ep.READ_TASK_WEIGHTS["search"])
    def search_view(self) -> None:
        model = ep.random_read_model(self._rng)
        url = ep.search_url(model, ep.random_search_term(self._rng), page=ep.random_page(self._rng))
        self.client.get(url, name=ep.search_name(model))

    @task(ep.READ_TASK_WEIGHTS["sort"])
    def sort_view(self) -> None:
        model = ep.random_read_model(self._rng)
        url = ep.sort_url(
            model,
            ep.random_sort_field(model, self._rng),
            ep.random_direction(self._rng),
            page=ep.random_page(self._rng),
        )
        self.client.get(url, name=ep.sort_name(model))

    @task(ep.READ_TASK_WEIGHTS["detail"])
    def detail_view(self) -> None:
        model = ep.random_read_model(self._rng)
        url = ep.detail_url(model, ep.random_item_id(self._rng))
        with self.client.get(url, name=ep.detail_name(model), catch_response=True) as resp:
            self._accept(resp, _READ_OK)

    @task(ep.READ_TASK_WEIGHTS["choices"])
    def choices_view(self) -> None:
        model = ep.random_choice_model(self._rng)
        relation = ep.random_choice_field(model, self._rng)
        url = ep.choices_url(model, relation, q=ep.random_search_term(self._rng))
        self.client.get(url, name=ep.choices_name(model))

    @staticmethod
    def _accept(response, allowed) -> None:
        if response.status_code in allowed:
            response.success()
        else:
            response.failure(f"unexpected status {response.status_code}")


class WriteUser(HyperAdminAuthMixin, HttpUser):
    """Simulates CRUD writes against the FK-free Contact model so payloads stay valid."""

    weight = 1  # 10% of the population writes
    wait_time = between(1.0, 3.0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rng = random.Random()  # noqa: S311 - per-user load-shape RNG, not security

    @task(ep.WRITE_TASK_WEIGHTS["create"])
    def create(self) -> None:
        payload = ep.contact_payload(self._rng)
        with self.client.post(
            ep.create_url(ep.WRITE_MODEL),
            data=payload,
            name=f"POST {ep.model_path(ep.WRITE_MODEL)} [create]",
            catch_response=True,
        ) as resp:
            self._accept(resp, _WRITE_OK)

    @task(ep.WRITE_TASK_WEIGHTS["update"])
    def update(self) -> None:
        item_id = ep.random_item_id(self._rng)
        payload = ep.contact_payload(self._rng)
        with self.client.put(
            ep.update_url(ep.WRITE_MODEL, item_id),
            data=payload,
            name=f"PUT {ep.model_path(ep.WRITE_MODEL)}/[id] [update]",
            catch_response=True,
        ) as resp:
            self._accept(resp, _WRITE_OK)

    @task(ep.WRITE_TASK_WEIGHTS["delete"])
    def delete(self) -> None:
        item_id = ep.random_item_id(self._rng)
        with self.client.delete(
            ep.delete_url(ep.WRITE_MODEL, item_id),
            name=f"DELETE {ep.model_path(ep.WRITE_MODEL)}/[id] [delete]",
            catch_response=True,
        ) as resp:
            self._accept(resp, _WRITE_OK)

    @staticmethod
    def _accept(response, allowed) -> None:
        if response.status_code in allowed:
            response.success()
        else:
            response.failure(f"unexpected status {response.status_code}")
