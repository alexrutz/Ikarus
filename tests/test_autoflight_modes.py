"""M2 mode logic: FCU actions drive correct mode transitions and FMA."""


def af(sim):
    return sim.systems.get("autoflight")


def test_cruise_initial_modes(sim):
    sim.run_for(1)
    m = af(sim).modes
    assert m.lat_active == "HDG"
    assert m.vert_active == "ALT"
    assert m.athr_mode == "SPEED"
    fma = sim.state.fma
    assert fma.ap == "AP1"
    assert fma.vertical == "ALT"
    assert fma.athr_active


def test_open_climb_sequence(sim):
    """OP CLB -> ALT* -> ALT with THR CLB during climb, SPEED after."""
    sim.cmd("fcu.alt.set", 35000)
    sim.cmd("fcu.alt.pull")
    sim.run_for(2)
    m = af(sim).modes
    assert m.vert_active == "OP CLB"
    assert m.vert_armed == "ALT"
    assert m.athr_mode == "THR CLB"
    assert sim.state.fma.vertical_armed == "ALT"

    seen_alt_star = False
    for _ in range(120):
        sim.run_for(5)
        if af(sim).modes.vert_active == "ALT*":
            seen_alt_star = True
        if af(sim).modes.vert_active == "ALT":
            break
    assert seen_alt_star, "never entered ALT* capture"
    assert af(sim).modes.vert_active == "ALT"
    assert abs(sim.state.fdm.alt_ft - 35000) < 120
    sim.run_for(10)
    assert af(sim).modes.athr_mode == "SPEED"


def test_open_descent_thr_idle(sim):
    sim.cmd("fcu.alt.set", 29000)
    sim.cmd("fcu.alt.pull")
    sim.run_for(2)
    m = af(sim).modes
    assert m.vert_active == "OP DES"
    assert m.athr_mode == "THR IDLE"
    sim.run_for(60)
    assert sim.state.fdm.vs_fpm < -500, "not descending in OP DES"
    # speed on elevator: CAS held near target while thrust is idle
    assert abs(sim.state.fdm.cas_kts - sim.state.guidance.target_cas_kts) < 15


def test_vs_mode_holds_selected_vs(sim):
    sim.cmd("fcu.alt.set", 35000)
    sim.cmd("fcu.vs.set", 1200)
    sim.cmd("fcu.vs.pull")
    sim.run_for(45)
    assert af(sim).modes.vert_active == "V/S"
    assert abs(sim.state.fdm.vs_fpm - 1200) < 150
    assert sim.state.fma.vertical == "V/S +1200"
    assert af(sim).modes.athr_mode == "SPEED"  # speed on thrust in V/S


def test_vs_push_levels_off(sim):
    sim.cmd("fcu.alt.set", 35000)
    sim.cmd("fcu.vs.set", 1500)
    sim.cmd("fcu.vs.pull")
    sim.run_for(30)
    sim.cmd("fcu.vs.push")
    sim.run_for(30)
    assert abs(sim.state.fdm.vs_fpm) < 150


def test_alt_capture_no_overshoot(sim):
    """ALT* from a 2400 fpm climb must not overshoot more than 100 ft."""
    sim.cmd("fcu.alt.set", 35000)
    sim.cmd("fcu.vs.set", 2400)
    sim.cmd("fcu.vs.pull")
    max_alt = 0.0
    for _ in range(90):
        sim.run_for(2)
        max_alt = max(max_alt, sim.state.fdm.alt_ft)
        if af(sim).modes.vert_active == "ALT" and abs(sim.state.fdm.vs_fpm) < 100:
            break
    assert max_alt < 35100, f"overshoot to {max_alt:.0f}"
    assert abs(sim.state.fdm.alt_ft - 35000) < 100


def test_heading_capture(sim):
    sim.cmd("fcu.hdg.set", 180)
    sim.cmd("fcu.hdg.pull")
    sim.run_for(120)
    from ikarus.autoflight.autopilot import angle_diff_deg
    err = angle_diff_deg(180, sim.state.fdm.hdg_true_deg)
    assert abs(err) < 2.0
    assert abs(sim.state.fdm.roll_deg) < 3.0


def test_ap_disconnect_clears_fma_and_holds_attitude(sim):
    sim.cmd("fcu.fd.toggle", False)
    sim.cmd("fcu.ap1.toggle", False)
    sim.run_for(1)
    assert sim.state.fma.ap == ""
    assert sim.state.fma.vertical == ""
    roll0 = sim.state.fdm.roll_deg
    sim.run_for(20)
    # FBW attitude hold keeps flying wings-level without guidance
    assert abs(sim.state.fdm.roll_deg - roll0) < 5


def test_manual_thrust_levers(sim):
    """A/THR off: levers command thrust directly through Autothrust."""
    sim.cmd("fcu.athr.toggle", False)
    sim.cmd("ctl.thrust.detent", "IDLE")
    sim.run_for(15)
    assert sim.adapter.get("fcs/throttle-pos-norm") < 0.05
    assert af(sim).modes.athr_mode == ""


def test_toga_levers_override_athr(sim):
    sim.cmd("ctl.thrust.detent", "TOGA")
    sim.run_for(10)
    assert sim.state.fma.thrust == "MAN TOGA"
    assert sim.state.fma.thrust_man
    assert sim.adapter.get("fcs/throttle-pos-norm") > 0.95
