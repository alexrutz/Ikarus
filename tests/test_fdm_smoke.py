"""M0 smoke tests: the stock A320 model loads, flies, and is fast enough."""

import time

import pytest

from ikarus import config
from ikarus.core.fdm import JsbsimAdapter


@pytest.fixture(scope="module")
def adapter() -> JsbsimAdapter:
    return JsbsimAdapter()


def test_model_loads(adapter):
    assert adapter.n_engines == 2
    assert adapter.n_tanks >= 2


def test_cruise_ic_is_sane(adapter):
    adapter.init_cruise()
    s = adapter.state
    assert abs(s.alt_ft - config.CRUISE_ALT_FT) < 100
    assert abs(s.cas_kts - config.CRUISE_CAS_KTS) < 10
    assert not s.wow
    assert all(e.running for e in s.engines)
    assert s.total_fuel_lbs > 1000


def test_cruise_stability_60s(adapter):
    """Trimmed cruise must not diverge over 60 s without any control input.

    Tolerances are wide on purpose: they define the acceptable envelope of
    the stock model, which the FBW/AP loops will tighten later.
    """
    adapter.init_cruise()
    for _ in range(60 * config.FDM_HZ):
        adapter.step()
    s = adapter.state
    assert abs(s.alt_ft - config.CRUISE_ALT_FT) < 3000, f"altitude diverged: {s.alt_ft}"
    assert abs(s.cas_kts - config.CRUISE_CAS_KTS) < 60, f"speed diverged: {s.cas_kts}"
    assert abs(s.roll_deg) < 15, f"roll diverged: {s.roll_deg}"
    assert abs(s.pitch_deg) < 15, f"pitch diverged: {s.pitch_deg}"


def test_runway_ic_is_on_ground(adapter):
    adapter.init_runway()
    for _ in range(2 * config.FDM_HZ):  # let the gear settle
        adapter.step()
    s = adapter.state
    assert s.wow
    assert s.gs_kts < 5
    assert s.agl_ft < 20


def test_realtime_headroom(adapter):
    """One simulated second must cost well under 100 ms wall time (>=10x)."""
    adapter.init_cruise()
    t0 = time.perf_counter()
    for _ in range(config.FDM_HZ):
        adapter.step()
    wall = time.perf_counter() - t0
    assert wall < 0.1, f"1 sim-second took {wall*1000:.0f} ms (need <100 ms)"


def test_controls_have_effect(adapter):
    """Aileron input rolls the aircraft — commands reach the surfaces."""
    adapter.init_cruise()
    adapter.set_aileron(0.5)
    for _ in range(3 * config.FDM_HZ):
        adapter.step()
    assert adapter.state.roll_deg > 5
    adapter.set_aileron(0.0)
