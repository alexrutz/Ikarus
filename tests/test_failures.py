"""M5 failure injection and law degradation."""


def alert_ids(sim):
    return [a.id for a in sim.state.ecam.alerts]


def test_engine_flameout_and_relight(sim):
    sim.run_for(1)
    sim.cmd("failure.set", "ENG1_FLAMEOUT")
    sim.run_for(10)
    assert not sim.state.eng.running[0]
    assert "ENG_1_FAIL" in alert_ids(sim)
    assert sim.state.ecam.master_warning
    # aircraft keeps flying on one engine under AP
    sim.run_for(60)
    assert abs(sim.state.fdm.roll_deg) < 10
    assert sim.state.fdm.alt_ft > 25000
    # clear + crossbleed-assisted restart (real SOP: X-BLEED OPEN so the
    # live engine's bleed reaches the dead side's starter)
    sim.cmd("failure.clear", "ENG1_FLAMEOUT")
    sim.cmd("eng.master1", False)
    sim.cmd("ovhd.bleed.xbleed", "OPEN")
    sim.run_for(5)
    assert sim.state.bleed.duct1_psi > 20, "crossbleed not feeding duct 1"
    sim.cmd("eng.mode", "IGN_START")
    sim.cmd("eng.master1", True)
    sim.run_for(45)
    assert sim.state.eng.running[0]
    sim.cmd("ovhd.bleed.xbleed", "AUTO")
    sim.cmd("eng.mode", "NORM")


def test_dual_gen_failure_emer_elec(sim):
    """Both generators lost in flight: RAT deploys, ESS buses recover."""
    sim.run_for(1)
    sim.cmd("failure.set", "ELEC_GEN1")
    sim.cmd("failure.set", "ELEC_GEN2")
    sim.run_for(20)
    e = sim.state.elec
    assert not e.ac1 and not e.ac2
    assert sim.state.hyd.rat_deployed
    assert e.ac_ess and e.dc_ess, "essential buses not on emergency gen"
    assert "ELEC_EMER_CONFIG" in alert_ids(sim)
    # FBW degrades (ELAC2 unpowered, ELAC1 on ESS keeps normal law...
    # here both remain powered via ESS/emer gen or law degrades - either
    # way the aircraft must remain controllable under the AP
    sim.run_for(30)
    assert abs(sim.state.fdm.roll_deg) < 15


def test_dual_elac_failure_alternate_law(sim):
    sim.run_for(1)
    sim.cmd("failure.set", "ELAC1")
    sim.cmd("failure.set", "ELAC2")
    sim.run_for(2)
    assert sim.state.fctl.law == "alternate"
    assert sim.state.guidance.law == "alternate"
    assert "FCTL_ALTN_LAW" in alert_ids(sim)
    # gear down in alternate -> direct
    sim.cmd("ctl.gear", True)
    sim.run_for(2)
    assert sim.state.fctl.law == "direct"
    assert "FCTL_DIRECT_LAW" in alert_ids(sim)
    sim.cmd("ctl.gear", False)
    sim.cmd("failure.clear_all")
    sim.run_for(2)
    assert sim.state.fctl.law == "normal"


def test_hydraulic_leak_drains_and_alerts(sim):
    sim.run_for(1)
    sim.cmd("failure.set", "HYD_G_LEAK")
    sim.run_for(150)
    h = sim.state.hyd
    assert h.green_qty < 0.2
    assert h.green_press_psi < 1450
    assert "HYD_G_SYS_LO_PR" in alert_ids(sim)
    # PTU cannot help a drained reservoir's own pumps, but yellow holds
    assert h.yellow_press_psi > 2000


def test_pack_failures_cabin_climb(sim):
    sim.run_for(1)
    sim.cmd("failure.set", "PACK1")
    sim.cmd("failure.set", "PACK2")
    sim.run_for(240)
    assert sim.state.press.cabin_alt_ft > 9550
    assert "CAB_PR_EXCESS_CAB_ALT" in alert_ids(sim)


def test_unknown_failure_rejected(sim):
    import pytest
    from ikarus.net.commands import CommandError
    with pytest.raises(CommandError):
        sim.cmd("failure.set", "NO_SUCH_FAILURE")
