"""M2 FBW protections in normal law."""


def test_bank_protection_returns_to_33(sim):
    """Full lateral stick: bank clamps at 67, returns to 33 when released."""
    sim.cmd("fcu.ap1.toggle", False)
    for _ in range(40):
        sim.cmd("ctl.roll", 0.5)
        sim.run_for(0.5)
    assert sim.state.fdm.roll_deg < 68.5
    assert sim.state.fdm.roll_deg > 40  # actually got steep
    sim.run_for(30)  # stick released
    assert abs(sim.state.fdm.roll_deg - 33) < 4


def test_pitch_attitude_limit(sim):
    sim.cmd("fcu.ap1.toggle", False)
    sim.cmd("ctl.thrust.detent", "TOGA")
    for _ in range(60):
        sim.cmd("ctl.pitch", 0.5)
        sim.run_for(0.5)
    assert sim.state.fdm.pitch_deg < 31.5


def test_alpha_protection_prevents_stall(sim):
    """Idle thrust + full aft stick: alpha stays below stall region."""
    sim.cmd("fcu.ap1.toggle", False)
    sim.cmd("fcu.athr.toggle", False)
    sim.cmd("ctl.thrust.detent", "IDLE")
    max_alpha = 0.0
    for _ in range(120):
        sim.cmd("ctl.pitch", 0.5)
        sim.run_for(0.5)
        max_alpha = max(max_alpha, sim.state.fdm.alpha_deg)
    assert max_alpha < 12.0, f"alpha reached {max_alpha:.1f}"


def test_fd_guidance_without_ap(sim):
    """AP off, FD on: guidance targets still computed for the FD bars."""
    sim.cmd("fcu.ap1.toggle", False)
    sim.cmd("fcu.hdg.set", 120)
    sim.cmd("fcu.hdg.pull")
    sim.run_for(2)
    assert sim.state.guidance.roll_target_deg > 5  # commands right turn
    # but the aircraft doesn't follow (AP off, no stick input)
    assert abs(sim.state.fdm.roll_deg) < 5
