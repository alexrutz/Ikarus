"""M4 aircraft systems: state-machine behavior and dependencies."""

import pytest

from ikarus.core.simloop import Sim


@pytest.fixture
def cold(scope="function") -> Sim:
    return Sim(situation="cold_dark")


def test_cold_dark_is_dark(cold):
    cold.run_for(1)
    e = cold.state.elec
    assert not e.ac1 and not e.ac2 and not e.dc_bat
    assert not any(cold.state.eng.running)
    assert cold.state.hyd.green_press_psi < 100
    assert cold.state.ecam.alerts == []       # FWC unpowered


def test_battery_then_ext_power(cold):
    cold.cmd("ovhd.elec.bat1", True)
    cold.cmd("ovhd.elec.bat2", True)
    cold.run_for(1)
    e = cold.state.elec
    assert e.dc_bat and e.dc_ess and not e.ac1
    cold.cmd("ovhd.elec.ext_pwr", True)
    cold.run_for(1)
    assert e.ac1 and e.ac2
    assert e.ac1_source == "EXT"


def test_apu_start_supplies_power_and_bleed(cold):
    cold.cmd("ovhd.elec.bat1", True)
    cold.cmd("ovhd.elec.bat2", True)
    cold.cmd("ovhd.apu.master", True)
    cold.run_for(1)
    cold.cmd("ovhd.apu.start", True)
    cold.run_for(45)
    apu = cold.state.apu
    assert apu.avail, f"APU state {apu.state} N={apu.n_pct}"
    assert cold.state.elec.ac1 and cold.state.elec.ac1_source == "APU"
    cold.cmd("ovhd.bleed.apu", True)
    cold.run_for(5)
    assert cold.state.bleed.duct1_psi > 25


def _power_up_with_apu(sim: Sim) -> None:
    sim.cmd("ovhd.elec.bat1", True)
    sim.cmd("ovhd.elec.bat2", True)
    sim.cmd("ovhd.apu.master", True)
    sim.run_for(1)
    sim.cmd("ovhd.apu.start", True)
    sim.run_for(40)
    sim.cmd("ovhd.bleed.apu", True)
    sim.cmd("ovhd.fuel.pump_l1", True)
    sim.cmd("ovhd.fuel.pump_l2", True)
    sim.cmd("ovhd.fuel.pump_r1", True)
    sim.cmd("ovhd.fuel.pump_r2", True)
    sim.run_for(5)


def test_full_cold_dark_engine_start(cold):
    """The M4 acceptance test: cold & dark to both engines running,
    entirely through the command API."""
    _power_up_with_apu(cold)
    assert cold.state.apu.avail
    assert cold.state.bleed.duct1_psi > 25

    # start engine 2 first (Airbus SOP), then engine 1
    cold.cmd("eng.mode", "IGN_START")
    cold.cmd("eng.master2", True)
    cold.run_for(35)
    assert cold.state.eng.running[1], \
        f"eng2 phase {cold.state.eng.phase[1]} n2={cold.state.eng.n2[1]:.0f}"
    cold.cmd("eng.master1", True)
    cold.run_for(35)
    assert cold.state.eng.running[0]
    cold.cmd("eng.mode", "NORM")
    cold.run_for(5)

    # generators took over, hydraulics up, APU no longer needed
    e = cold.state.elec
    assert e.ac1_source == "GEN1" and e.ac2_source == "GEN2"
    assert cold.state.hyd.green_press_psi > 2500
    assert cold.state.hyd.yellow_press_psi > 2500
    assert not cold.state.ecam.master_warning
    # engine display shows idle-ish parameters
    assert 15 < cold.state.eng.n1[0] <= 35
    assert cold.state.eng.egt_c[0] > 200


def test_engine_start_needs_bleed(cold):
    cold.cmd("ovhd.elec.bat1", True)
    cold.cmd("ovhd.elec.bat2", True)
    cold.cmd("ovhd.elec.ext_pwr", True)   # power but NO bleed source
    cold.run_for(2)
    cold.cmd("eng.mode", "IGN_START")
    cold.cmd("eng.master1", True)
    cold.run_for(15)
    assert cold.state.eng.phase[0] == "OFF"   # no duct pressure, no crank
    assert not cold.state.eng.running[0]


def test_gen_failure_transfers_bus(sim):
    """In cruise, failing GEN1 moves AC1 to the cross-tie."""
    sim.run_for(1)
    assert sim.state.elec.ac1_source == "GEN1"
    sim.state.elec.gen1_fault = True
    sim.run_for(1)
    e = sim.state.elec
    assert e.ac1 and e.ac1_source == "XTIE"
    ids = [a.id for a in sim.state.ecam.alerts]
    assert "ELEC_GEN_1_FAULT" in ids
    assert sim.state.ecam.master_caution


def test_hydraulic_ptu(sim):
    """Losing the yellow engine pump: PTU pressurizes yellow from green."""
    sim.run_for(1)
    sim.cmd("ovhd.hyd.eng2_pump", False)
    sim.run_for(30)
    h = sim.state.hyd
    assert h.ptu_running
    assert h.yellow_press_psi > 2000, f"yellow {h.yellow_press_psi:.0f}"


def test_pressurization_and_cabin_alert(sim):
    sim.run_for(5)
    p = sim.state.press
    assert p.cabin_alt_ft < 8000
    assert p.delta_p_psi > 5
    # fail both packs at altitude -> cabin climbs -> warning
    sim.cmd("ovhd.bleed.pack1", False)
    sim.cmd("ovhd.bleed.pack2", False)
    sim.run_for(240)
    assert sim.state.press.cabin_alt_ft > 9550
    ids = [a.id for a in sim.state.ecam.alerts]
    assert "CAB_PR_EXCESS_CAB_ALT" in ids
    assert sim.state.ecam.master_warning


def test_ecam_clear_and_recall(sim):
    sim.run_for(1)
    sim.state.elec.gen1_fault = True
    sim.run_for(1)
    assert sim.state.ecam.master_caution
    sim.cmd("ecam.clr")
    sim.run_for(1)
    assert not sim.state.ecam.master_caution
    sim.cmd("ecam.rcl")
    sim.run_for(1)
    assert sim.state.ecam.master_caution


def test_fuel_crossfeed_and_low_level(sim):
    sim.run_for(1)
    f = sim.state.fuel
    # drain the left inner tank to trigger low level
    f.inner_l = 500.0
    f.outer_l = 100.0
    sim.run_for(2)
    ids = [a.id for a in sim.state.ecam.alerts]
    assert "FUEL_WING_LO_LVL" in ids
    sim.cmd("ovhd.fuel.xfeed", True)
    sim.run_for(30)
    assert sim.state.fuel.feed_ok[0]  # fed from the right side


def test_sd_auto_page_follows_alert(sim):
    sim.run_for(1)
    sim.state.elec.gen1_fault = True
    sim.run_for(1)
    assert sim.state.ecam.sd_page == "ELEC"
    sim.cmd("ecam.page", "FUEL")   # manual selection wins
    sim.run_for(1)
    assert sim.state.ecam.sd_page == "FUEL"
    sim.cmd("ecam.page", "FUEL")   # second press back to auto
    sim.run_for(1)
    assert sim.state.ecam.sd_page == "ELEC"
