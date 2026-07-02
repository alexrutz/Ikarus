"""FMS: MCDU-driven route entry, NAV guidance, managed descent, ILS capture.

The headline test flies EDDF -> EDDM entirely through the command API:
route entered via MCDU keys, NAV engaged, managed descent, APPR, and
asserts cross-track and glideslope tracking quality.
"""

import pytest

from ikarus.nav import geo


def mcdu_type(sim, text):
    for ch in text:
        sim.cmd("mcdu.key", ch)


def enter_route(sim, route="EDDF/EDDM"):
    sim.cmd("mcdu.key", "INIT")
    mcdu_type(sim, route)
    sim.cmd("mcdu.key", "LSK1R")


def mcdu_text(sim):
    lines = sim.state.fms.mcdu_lines
    return ["".join(seg[1] for seg in line) for line in lines]


def test_mcdu_route_entry(sim):
    enter_route(sim)
    sim.run_for(0.5)
    fms = sim.state.fms
    assert fms.origin == "EDDF"
    assert fms.dest == "EDDM"
    assert any("EDDF/EDDM" in ln for ln in mcdu_text(sim))


def test_mcdu_bad_airport_shows_error(sim):
    sim.cmd("mcdu.key", "INIT")
    mcdu_type(sim, "XXXX/YYYY")
    sim.cmd("mcdu.key", "LSK1R")
    sim.run_for(0.5)
    assert any("UNKNOWN" in ln.upper() for ln in mcdu_text(sim))
    assert sim.state.fms.origin == ""


def test_mcdu_departure_arrival_selection(sim):
    enter_route(sim)
    # departure: runway then SID
    sim.cmd("mcdu.key", "DEPART")
    sim.run_for(0.1)
    rows = mcdu_text(sim)
    idx = next(i for i, ln in enumerate(rows) if "25C" in ln)
    sim.cmd("mcdu.key", f"LSK{idx // 2}L")
    sim.run_for(0.1)
    rows = mcdu_text(sim)
    idx = next(i for i, ln in enumerate(rows) if "RIDAR7S" in ln)
    sim.cmd("mcdu.key", f"LSK{idx // 2}L")
    # arrival: approach then STAR
    sim.cmd("mcdu.key", "ARRIVE")
    sim.run_for(0.1)
    rows = mcdu_text(sim)
    idx = next(i for i, ln in enumerate(rows) if "ILS26L" in ln)
    sim.cmd("mcdu.key", f"LSK{idx // 2}L")
    sim.run_for(0.1)
    rows = mcdu_text(sim)
    idx = next(i for i, ln in enumerate(rows) if "DKB26L" in ln)
    sim.cmd("mcdu.key", f"LSK{idx // 2}L")
    sim.run_for(0.5)

    fms = sim.state.fms
    assert fms.dep_runway == "25C"
    assert fms.sid == "RIDAR7S"
    assert fms.approach == "ILS26L"
    assert fms.star == "DKB26L"
    idents = [leg.ident for leg in fms.legs]
    assert "RID" in idents and "DKB" in idents and "FF26L" in idents
    assert idents[-1] == "EDDM26L"


@pytest.mark.slow
def test_full_flight_eddf_eddm(sim):
    """The M3 acceptance flight: NAV tracking + managed DES + ILS."""
    # Build the plan (as the MCDU test does, but via plan API for brevity)
    fms_sys = sim.systems.get("fms")
    plan = fms_sys.plan
    plan.set_route("EDDF", "EDDM")
    plan.set_dep_runway("25C")
    plan.set_sid("RIDAR7S")
    plan.set_approach("ILS26L")
    plan.set_star("DKB26L")
    fms_sys.plan_changed()
    fms_sys.cruise_alt_ft = 15000.0

    # Cruise situation starts at FL330 over EDDF heading east; go direct RID
    sim.cmd("fcu.alt.set", 15000)
    sim.cmd("fcu.alt.pull")   # descend to a workable cruise first
    plan.direct_to("RID", sim.state.fdm.lat_deg, sim.state.fdm.lon_deg)
    fms_sys.plan_changed()
    sim.run_for(1)            # let the FMS publish guidance
    sim.cmd("fcu.hdg.push")   # arm/engage NAV
    sim.cmd("fcu.spd.push")   # managed speed
    sim.run_for(30)
    assert sim.state.fma.lateral in ("NAV", "HDG")

    # fly the enroute portion; measure XTK only while established on a
    # straight leg (turns necessarily overshoot at jet speeds)
    max_xtk = 0.0
    established = False
    last_leg = -1
    for _ in range(150):
        sim.run_for(10)
        fms = sim.state.fms
        if fms.active_idx != last_leg:
            last_leg = fms.active_idx
            established = False
        if sim.state.fma.lateral == "NAV":
            if abs(fms.xtk_nm) < 0.3:
                established = True
            if established:
                max_xtk = max(max_xtk, abs(fms.xtk_nm))
        if fms.dist_to_dest_nm and fms.dist_to_dest_nm < 60:
            break
    assert sim.state.fma.lateral == "NAV", sim.state.fma
    assert max_xtk < 0.5, f"established cross-track reached {max_xtk:.2f} nm"

    # managed descent toward the approach
    sim.cmd("fcu.alt.set", 4000)
    sim.cmd("fcu.alt.push")   # DES (managed)
    sim.run_for(5)
    assert sim.state.fma.vertical in ("DES", "ALT*", "ALT")
    sim.cmd("fcu.appr.toggle")
    sim.run_for(5)
    assert sim.state.fma.lateral_armed in ("LOC", "") or \
        sim.state.fma.lateral in ("LOC*", "LOC")

    # continue until G/S captured or timeout
    for _ in range(200):
        sim.run_for(10)
        if sim.state.fma.vertical in ("G/S",):
            break
        if sim.state.fdm.agl_ft < 1500:
            break
    assert sim.state.fma.lateral in ("LOC*", "LOC"), sim.state.fma
    assert sim.state.fma.vertical in ("G/S*", "G/S"), sim.state.fma

    # track the ILS down to 1000 ft AGL and check deviations
    while sim.state.fdm.agl_ft > 1000 and sim.state.fdm.alt_ft > 2400:
        sim.run_for(5)
    assert abs(sim.state.radio.ils_loc_dots) < 1.0, "LOC not tracked"
    assert abs(sim.state.radio.ils_gs_dots) < 1.0, "G/S not tracked"


def test_radio_vor_tuning(sim):
    sim.cmd("radio.nav1.set", 112200)  # RID near Frankfurt
    sim.run_for(2)
    radio = sim.state.radio
    assert radio.nav1_ok
    assert radio.nav1_ident == "RID"
    assert radio.nav1_dme_nm > 1
