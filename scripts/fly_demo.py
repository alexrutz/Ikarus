#!/usr/bin/env python3
"""Headless fast-time showcase: cold & dark start, then EDDF -> EDDM
with NAV guidance, managed descent and an ILS approach to short final.

Runs entirely through the command API (what the UI uses), printing a
flight log. No server, no browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ikarus.core.simloop import Sim   # noqa: E402


def log(sim: Sim, msg: str) -> None:
    t = sim.state.sim.time_s
    print(f"[{int(t) // 60:02d}:{int(t) % 60:02d}] {msg}")


def demo_cold_dark() -> None:
    print("=" * 64)
    print("PART 1 — cold & dark to engines running (EDDF stand)")
    print("=" * 64)
    sim = Sim(situation="cold_dark")
    log(sim, "aircraft cold & dark")
    sim.cmd("ovhd.elec.bat1", True)
    sim.cmd("ovhd.elec.bat2", True)
    sim.run_for(2)
    log(sim, f"batteries on, DC BAT powered: {sim.state.elec.dc_bat}")
    sim.cmd("ovhd.apu.master", True)
    sim.run_for(2)
    sim.cmd("ovhd.apu.start", True)
    while not sim.state.apu.avail:
        sim.run_for(5)
    log(sim, f"APU available, AC1 source: {sim.state.elec.ac1_source}")
    sim.cmd("ovhd.bleed.apu", True)
    for pump in ("l1", "l2", "r1", "r2"):
        sim.cmd(f"ovhd.fuel.pump_{pump}", True)
    sim.run_for(5)
    sim.cmd("eng.mode", "IGN_START")
    sim.cmd("eng.master2", True)
    while not sim.state.eng.running[1]:
        sim.run_for(5)
    log(sim, f"engine 2 running, N2 {sim.state.eng.n2[1]:.0f}%")
    sim.cmd("eng.master1", True)
    while not sim.state.eng.running[0]:
        sim.run_for(5)
    sim.cmd("eng.mode", "NORM")
    sim.run_for(5)
    log(sim, f"both engines running; AC1 <- {sim.state.elec.ac1_source}, "
        f"green hyd {sim.state.hyd.green_press_psi:.0f} psi")
    log(sim, f"ECAM memos: {[m[0] for m in sim.state.ecam.memos]}")


def demo_flight() -> None:
    print()
    print("=" * 64)
    print("PART 2 — EDDF -> EDDM: NAV, managed descent, ILS 26L")
    print("=" * 64)
    sim = Sim(situation="cruise")
    fms = sim.systems.get("fms")
    plan = fms.plan
    plan.set_route("EDDF", "EDDM")
    plan.set_dep_runway("25C")
    plan.set_sid("RIDAR7S")
    plan.set_approach("ILS26L")
    plan.set_star("DKB26L")
    fms.plan_changed()
    fms.cruise_alt_ft = 15000.0
    sim.cmd("fcu.alt.set", 15000)
    sim.cmd("fcu.alt.pull")
    plan.direct_to("RID", sim.state.fdm.lat_deg, sim.state.fdm.lon_deg)
    fms.plan_changed()
    sim.run_for(1)
    sim.cmd("fcu.hdg.push")
    sim.cmd("fcu.spd.push")
    log(sim, "cruise over EDDF, direct RID, NAV + managed speed")

    last_wpt = ""
    while True:
        sim.run_for(10)
        st = sim.state
        idx = st.fms.active_idx
        wpt = st.fms.legs[idx].ident if 0 <= idx < len(st.fms.legs) else "?"
        if wpt != last_wpt:
            last_wpt = wpt
            log(sim, f"-> {wpt}  (FL{st.fdm.alt_ft / 100:.0f}, "
                f"{st.fdm.cas_kts:.0f} kts, XTK {st.fms.xtk_nm:+.2f} nm, "
                f"FMA {st.fma.thrust}|{st.fma.vertical}|{st.fma.lateral})")
        if st.fms.dist_to_dest_nm and st.fms.dist_to_dest_nm < 60:
            break
    sim.cmd("fcu.alt.set", 4000)
    sim.cmd("fcu.alt.push")
    sim.cmd("fcu.appr.toggle")
    log(sim, "60 nm out: descent to 4000, APPR armed")

    announced = set()
    while sim.state.fdm.alt_ft > 2200:
        sim.run_for(5)
        fma = sim.state.fma
        for mode in (fma.lateral, fma.vertical):
            if mode in ("LOC*", "LOC", "G/S*", "G/S") and mode not in announced:
                announced.add(mode)
                log(sim, f"{mode} captured "
                    f"(LOC {sim.state.radio.ils_loc_dots:+.2f} dots, "
                    f"G/S {sim.state.radio.ils_gs_dots:+.2f} dots)")
        if sim.state.sim.time_s > 3000:
            log(sim, "timeout")
            break

    st = sim.state
    log(sim, f"short final RWY 26L: {st.fdm.agl_ft:.0f} ft AGL, "
        f"{st.fdm.cas_kts:.0f} kts, LOC {st.radio.ils_loc_dots:+.2f}, "
        f"G/S {st.radio.ils_gs_dots:+.2f}, {st.radio.ils_dme_nm} nm DME")
    print()
    print("demo complete — run `python -m ikarus` to fly it yourself.")


if __name__ == "__main__":
    demo_cold_dark()
    demo_flight()
