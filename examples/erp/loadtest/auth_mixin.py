"""Session-auth mixin for Locust users.

HyperAdmin uses cookie-session auth, so each simulated user logs in once in ``on_start`` and
relies on Locust's per-user ``requests.Session`` to carry the session cookie on every
subsequent request. A failed login stops that user rather than letting it hammer the login
wall with unauthenticated traffic that would skew the stats.
"""

from __future__ import annotations

import logging
import os
from http import HTTPStatus

from locust.exception import StopUser

from examples.erp.loadtest import endpoints

logger = logging.getLogger(__name__)

# Substring the login page renders on bad credentials (see auth/views.py).
_LOGIN_ERROR_MARKER = "Invalid username or password"


class HyperAdminAuthMixin:
    """Mix in before ``HttpUser`` to authenticate via ``POST {ADMIN_PREFIX}/login``."""

    login_path = f"{endpoints.ADMIN_PREFIX}/login"

    def on_start(self) -> None:
        username = os.environ.get("LOADTEST_USER", "admin")
        password = os.environ.get("LOADTEST_PASSWORD", "admin")
        with self.client.post(
            self.login_path,
            data={"username": username, "password": password},
            name="POST /admin/login",
            catch_response=True,
        ) as response:
            # On success the POST 302-redirects to /admin/ and is followed to a 200. On failure
            # the login form is re-rendered (still 200) with an error marker.
            if response.status_code == HTTPStatus.OK and _LOGIN_ERROR_MARKER not in response.text:
                response.success()
                return
            response.failure(f"login failed for {username!r}: status={response.status_code}")
            logger.error(
                "Locust user could not authenticate as %r (status %s) — stopping user",
                username,
                response.status_code,
            )
            raise StopUser
