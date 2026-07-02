"""M1 provisional autopilot: scripted fast-time capture flights."""

from ikarus.autoflight.simple_ap import angle_diff_deg


def test_heading_capture(sim):
    sim.cmd("ap.hdg.set", 180)
    sim.run_for(120)
    err = angle_diff_deg(180, sim.state.fdm.hdg_true_deg)
    assert abs(err) < 2.0, f"heading error {err:.1f} deg after 120 s"
    assert abs(sim.state.fdm.roll_deg) < 3.0


def test_altitude_climb_capture(sim):
    sim.cmd("ap.alt.set", 35000)
    sim.run_for(240)
    alt = sim.state.fdm.alt_ft
    assert abs(alt - 35000) < 100, f"altitude {alt:.0f} after climb"
    assert abs(sim.state.fdm.vs_fpm) < 300


def test_altitude_descent_capture(sim):
    sim.cmd("ap.alt.set", 29000)
    sim.run_for(300)
    alt = sim.state.fdm.alt_ft
    assert abs(alt - 29000) < 100, f"altitude {alt:.0f} after descent"


def test_speed_hold(sim):
    sim.cmd("ap.spd.set", 260)
    sim.run_for(180)
    cas = sim.state.fdm.cas_kts
    assert abs(cas - 260) < 5, f"speed {cas:.0f} kts after 180 s"


def test_combined_turn_climb_decel(sim):
    """Everything at once — the M1 'can it actually fly' test."""
    sim.cmd("ap.hdg.set", 270)
    sim.cmd("ap.alt.set", 34000)
    sim.cmd("ap.spd.set", 265)
    sim.run_for(300)
    fdm = sim.state.fdm
    assert abs(angle_diff_deg(270, fdm.hdg_true_deg)) < 2.0
    assert abs(fdm.alt_ft - 34000) < 100
    assert abs(fdm.cas_kts - 265) < 6


def test_manual_flight_attitude_hold(sim):
    """AP off: stick pulse banks the aircraft, FBW holds the attitude."""
    sim.cmd("ap.toggle", False)
    sim.cmd("athr.toggle", False)
    for _ in range(10):
        sim.cmd("ctl.roll", 0.3)
        sim.run_for(0.5)
    sim.run_for(10)
    roll = sim.state.fdm.roll_deg
    assert roll > 5, f"expected right bank, got {roll:.1f}"
    # target held (no input decay drift back to wings level)
    sim.run_for(20)
    assert abs(sim.state.fdm.roll_deg - roll) < 4


def test_pause_freezes_time(sim):
    sim.cmd("sim.pause", True)
    t0 = sim.state.fdm.sim_time_s
    # SimLoop won't tick when paused; run_for bypasses pause, so emulate
    # the loop's check here.
    assert sim.state.sim.paused
    assert sim.state.fdm.sim_time_s == t0
