"""Frontend display tests: server + Chromium, asserting on the debug
values each display publishes (data-to-display wiring, not pixels).

Requires the pre-installed Playwright Chromium; skipped when absent.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

CHROMIUM = "/opt/pw-browsers/chromium"

playwright = pytest.importorskip("playwright.sync_api")
if not Path(CHROMIUM).exists():
    pytest.skip("pre-installed Chromium not found", allow_module_level=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "ikarus", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://localhost:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def page(server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        pg = browser.new_page(viewport={"width": 1600, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(server)
        pg.wait_for_timeout(2500)
        pg._errors = errors
        yield pg
        browser.close()


def debug(page):
    return page.evaluate("window.__ikarusDebug") or {}


def test_no_js_errors_and_displays_alive(page):
    assert page._errors == [], page._errors
    d = debug(page)
    assert "pfd" in d and "nd" in d and "ewd" in d and "sd" in d


def test_pfd_shows_live_state(page):
    d = debug(page)["pfd"]
    assert 30000 < d["alt"] < 36000
    assert 200 < d["cas"] < 350


def test_fcu_command_reaches_pfd(page):
    page.fill("#fcu-alt", "35000")
    page.dispatch_event("#fcu-alt", "change")
    page.click('[data-cmd="fcu.alt.pull"]')
    page.click("#pfd")                  # blur the input so keys register
    page.keyboard.press("]")            # 2x time acceleration
    page.keyboard.press("]")            # 4x
    # poll: under parallel test load the paced loop may run slower
    alt = 0.0
    for _ in range(30):
        page.wait_for_timeout(1000)
        alt = debug(page)["pfd"]["alt"]
        if alt > 33300:
            break
    page.keyboard.press("[")
    page.keyboard.press("[")
    assert alt > 33300, f"no climb observed (alt {alt:.0f})"


def test_ecam_page_key_switches_sd(page):
    page.click('#ecam-keys button[data-page="HYD"]')
    page.wait_for_timeout(800)
    assert debug(page)["sd"]["page"] == "HYD"
    page.click('#ecam-keys button[data-page="HYD"]')  # back to auto
    page.wait_for_timeout(800)


def test_failure_injection_shows_alert(page):
    page.click("#tab-fail")
    page.click('.ovhd-btn:has-text("GEN 1 FAULT")')
    page.wait_for_timeout(1500)
    assert "ELEC_GEN_1_FAULT" in debug(page)["ewd"]["alerts"]
    page.click('.ovhd-btn:has-text("CLEAR ALL")')
    page.wait_for_timeout(1500)
    assert "ELEC_GEN_1_FAULT" not in debug(page)["ewd"]["alerts"]
