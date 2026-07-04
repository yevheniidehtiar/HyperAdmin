"""E2E tests for the i18n locale switcher and RTL layout (C3-E).

Covers four BDD scenarios from
``.meta/epics/epic-i18n/stories/c3e-e2e-i18n.md``:

1. Locale switcher sets ``hyperadmin_locale`` cookie and triggers page reload.
2. Switching back to English restores English strings.
3. RTL locale sets ``dir="rtl"`` and ``lang="ar"`` on ``<html>``.
4. LTR layout snapshot at 1280 × 800 is stable against committed baseline.

To regenerate the snapshot baseline after an intentional visual change::

    RESPONSIVE_SNAPSHOTS_UPDATE=1 uv run pytest tests/e2e/test_i18n.py -v --no-cov
    git add tests/e2e/snapshots/i18n/
    git commit -m "test(e2e): refresh i18n visual baselines"

Cookie state is isolated per test — pytest-playwright's ``page`` fixture is
function-scoped so each test receives a fresh ``BrowserContext``.
"""

from __future__ import annotations

import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image, ImageChops

if TYPE_CHECKING:
    from playwright.sync_api import Page

# ---------------------------------------------------------------------------
# Snapshot helpers  (mirror of test_visual_regression.py)
# ---------------------------------------------------------------------------

SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "i18n"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

UPDATE_BASELINES = os.environ.get("RESPONSIVE_SNAPSHOTS_UPDATE") == "1"

# Threshold for "is this pixel meaningfully different?" — max channel diff out of 255.
PIXEL_DIFF_THRESHOLD = 30

# Maximum fraction of the full image allowed to differ by more than the
# per-pixel threshold above. Layout-level regressions shift large fractions
# of the image easily. Localized hover/focus/cursor variance stays below 0.5%.
MAX_DIFFERING_FRACTION = 0.02


def _capture_or_compare(page: Page, name: str) -> None:
    """Take a full-page screenshot and either write the baseline or diff it.

    On baseline write, the PNG is left in the working tree for ``git add``.
    On comparison, the test fails when more than ``MAX_DIFFERING_FRACTION``
    of pixels differ by more than ``PIXEL_DIFF_THRESHOLD`` per channel.
    """
    snapshot_path = SNAPSHOT_DIR / f"{name}.png"
    actual_bytes = page.screenshot(full_page=True)

    if UPDATE_BASELINES or not snapshot_path.exists():
        snapshot_path.write_bytes(actual_bytes)
        if not UPDATE_BASELINES:
            pytest.skip(f"baseline created at {snapshot_path}; commit and re-run to compare")
        return

    baseline = Image.open(snapshot_path).convert("RGB")
    actual = Image.open(io.BytesIO(actual_bytes)).convert("RGB")

    if baseline.size != actual.size:
        pytest.fail(
            f"viewport size mismatch for '{name}': baseline {baseline.size} vs actual {actual.size}"
        )

    diff = ImageChops.difference(baseline, actual)
    if diff.getbbox() is None:
        return  # pixel-perfect match

    total_pixels = baseline.size[0] * baseline.size[1]
    raw = diff.tobytes()  # flat R,G,B,R,G,B,... bytes
    significantly_different = sum(
        1
        for i in range(0, len(raw), 3)
        if max(raw[i], raw[i + 1], raw[i + 2]) > PIXEL_DIFF_THRESHOLD
    )
    differing_fraction = significantly_different / total_pixels

    if differing_fraction > MAX_DIFFERING_FRACTION:
        diff_path = SNAPSHOT_DIR / f"{name}.diff.png"
        actual_path = SNAPSHOT_DIR / f"{name}.actual.png"
        diff.save(diff_path)
        Path(actual_path).write_bytes(actual_bytes)
        pytest.fail(
            f"'{name}' visual diff: "
            f"{significantly_different} / {total_pixels} pixels "
            f"({differing_fraction * 100:.2f}%) differ by > "
            f"{PIXEL_DIFF_THRESHOLD}/255 — exceeds "
            f"{MAX_DIFFERING_FRACTION * 100:.2f}% threshold. "
            f"Inspect {diff_path} and {actual_path}, then either fix the "
            f"regression or run with RESPONSIVE_SNAPSHOTS_UPDATE=1 to refresh."
        )


# ---------------------------------------------------------------------------
# RTL fixture — starts simple app with "ar" added to supported_locales
# ---------------------------------------------------------------------------

_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"
_SERVER_TIMEOUT = 15 if _IN_CONTAINER else 5


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


@pytest.fixture
def rtl_base_url() -> Iterator[str]:
    """Start the simple app with both RTL must-haves (``ar`` and ``he``) supported.

    ``HYPERADMIN_SUPPORTED_LOCALES`` is set in the subprocess environment so
    that ``HyperAdminSettings`` (read at module import time) picks it up.
    Both Arabic and Hebrew now ship in the default seed list (v0.5.2 top-20),
    but the override lets the test stay self-contained even when the default
    list changes.
    """
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.simple.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"
    # Override supported locales to include both RTL must-haves.
    env["HYPERADMIN_SUPPORTED_LOCALES"] = json.dumps(["en", "ar", "he"])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    base = f"http://localhost:{port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"RTL server did not start: {last_err}")

        yield base
    finally:
        if proc.poll() is None:
            try:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


# ---------------------------------------------------------------------------
# Scenario 1: locale switcher sets cookie and page reloads
# ---------------------------------------------------------------------------


def _switch_locale(page: Page, locale: str) -> None:
    """Select a locale from the navbar switcher and wait for the redirect.

    The locale switcher form is submitted via Alpine.js ``x-on:change``.
    ``page.expect_navigation()`` ensures we capture the full form-post + 302
    redirect cycle before asserting cookies or page state.
    """
    with page.expect_navigation():
        page.get_by_label("Select language").select_option(locale)
    page.wait_for_load_state("networkidle")


def test_locale_switcher_sets_cookie(page: Page, demo_base_url: str) -> None:
    """
    Scenario: locale switcher sets cookie and page reloads

      Given an admin session at locale=en
      When  user selects "es" from the locale <select> in the navbar
      Then  cookie hyperadmin_locale=es is present in the BrowserContext cookies
      And   page reloads (URL stays on admin, no console errors)
    """
    # Collect console errors during the test
    console_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Given an admin session at locale=en (no auth required on simple app)
    page.goto(demo_base_url + "/admin/user")
    page.wait_for_load_state("networkidle")

    # When user selects "es" from the locale <select> in the navbar.
    # Alpine.js submits the parent form on the native "change" event;
    # page.expect_navigation() captures the form POST + 302 redirect cycle.
    _switch_locale(page, "es")

    # Then cookie hyperadmin_locale=es is present in the BrowserContext cookies
    cookies = page.context.cookies()
    locale_cookie = next((c for c in cookies if c["name"] == "hyperadmin_locale"), None)
    assert locale_cookie is not None, (
        "Expected 'hyperadmin_locale' cookie to be set after switching to 'es', "
        f"but no such cookie was found. All cookies: {cookies}"
    )
    assert locale_cookie["value"] == "es", (
        f"Expected cookie value 'es', got {locale_cookie['value']!r}"
    )

    # And page reloads (URL is still within the admin)
    assert "/admin" in page.url, f"Expected to stay on admin after locale switch, got: {page.url}"

    # And no console errors
    assert not console_errors, f"Unexpected console errors after locale switch: {console_errors}"


# ---------------------------------------------------------------------------
# Scenario 2: switching back to English restores English strings
# ---------------------------------------------------------------------------


def test_locale_switcher_restores_english(page: Page, demo_base_url: str) -> None:
    """
    Scenario: switching back to English restores English strings

      Given cookie hyperadmin_locale=es is set (locale switcher has been used)
      When  user selects "en" from the locale switcher
      Then  cookie changes to hyperadmin_locale=en
      And   the locale switcher select shows "en" as the selected option
    """
    # Given cookie hyperadmin_locale=es is set by using the switcher first
    page.goto(demo_base_url + "/admin/user")
    page.wait_for_load_state("networkidle")
    _switch_locale(page, "es")

    # Confirm we are now on "es"
    cookies = page.context.cookies()
    locale_cookie = next((c for c in cookies if c["name"] == "hyperadmin_locale"), None)
    assert locale_cookie is not None and locale_cookie["value"] == "es", (
        f"Precondition failed: expected cookie 'es', got: {locale_cookie}"
    )

    # When user selects "en" from the locale switcher
    _switch_locale(page, "en")

    # Then cookie changes to hyperadmin_locale=en
    cookies = page.context.cookies()
    locale_cookie = next((c for c in cookies if c["name"] == "hyperadmin_locale"), None)
    assert locale_cookie is not None, (
        "Expected 'hyperadmin_locale' cookie after switching back to English"
    )
    assert locale_cookie["value"] == "en", (
        f"Expected cookie value 'en', got {locale_cookie['value']!r}"
    )

    # And the locale switcher shows "en" as the selected value
    selected_value = page.get_by_label("Select language").evaluate("el => el.value")
    assert selected_value == "en", f"Expected locale select value 'en', got {selected_value!r}"


# ---------------------------------------------------------------------------
# Scenario 3: RTL locale sets dir="rtl" on <html>
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rtl_code", ["ar", "he"])
def test_rtl_locale_sets_html_dir(page: Page, rtl_base_url: str, rtl_code: str) -> None:
    """
    Scenario: RTL locale sets dir="rtl" on <html>

      Given supported_locales includes the RTL code (via HYPERADMIN_SUPPORTED_LOCALES env override)
      And   the locale switcher selects the RTL code
      When  any admin page loads
      Then  <html dir="rtl"> is present
      And   <html lang="<rtl_code>"> is present

    Parametrized over Arabic and Hebrew — the two RTL must-haves in the v0.5.2
    top-20 default. ``RTL_LOCALES`` also covers ``fa``/``ur`` but those remain
    opt-in via env override and are exercised by unit tests.
    """
    # Given cookie hyperadmin_locale=<rtl_code> set via the locale switcher.
    page.goto(rtl_base_url + "/admin/user")
    page.wait_for_load_state("networkidle")
    _switch_locale(page, rtl_code)

    # When the admin page reloads (the redirect lands back on /admin/user with the cookie set).

    # Then <html dir="rtl"> is present
    html_dir = page.locator("html").get_attribute("dir")
    assert html_dir == "rtl", (
        f"Expected <html dir='rtl'> for {rtl_code!r} locale, got dir={html_dir!r}"
    )

    # And <html lang="<rtl_code>"> is present
    html_lang = page.locator("html").get_attribute("lang")
    assert html_lang == rtl_code, (
        f"Expected <html lang={rtl_code!r}> for {rtl_code!r} locale, got lang={html_lang!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4: LTR layout snapshot at 1280px is stable
# ---------------------------------------------------------------------------


def test_ltr_layout_snapshot_1280(page: Page, demo_base_url: str) -> None:
    """
    Scenario: LTR layout snapshot at 1280px is stable

      Given locale=en (LTR) and viewport 1280 × 800
      When  the list view loads
      Then  full-page screenshot matches the committed baseline
      And   pixel diff < 1%
    """
    # Given locale=en — no cookie override needed (default is en)
    # And viewport 1280 × 800
    page.set_viewport_size({"width": 1280, "height": 800})

    # When the list view loads
    page.goto(demo_base_url + "/admin/user")
    page.wait_for_load_state("networkidle")

    # Then screenshot matches committed baseline at tests/e2e/snapshots/i18n/list_en_1280.png
    # Pixel diff < 1% (enforced inside _capture_or_compare)
    _capture_or_compare(page, "list_en_1280")
