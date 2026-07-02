"""Declarative ECAM alert table.

Each alert: an id, a level (3 = red warning, 2 = amber caution), a
sensed condition over SimState, E/WD lines (with action lines), the SD
page it calls, and the flight phases it is inhibited in. Adding depth
to the warning system = adding rows here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ikarus.core.state import SimState

R, A, C, G, W = "r", "a", "c", "g", "w"   # colors


@dataclass(frozen=True)
class Alert:
    id: str
    level: int                       # 3 warning, 2 caution
    condition: Callable[[SimState], bool]
    lines: tuple                     # ((text, color), ...)
    sd_page: str = ""
    inhibit_phases: tuple = ()       # FWC phases where suppressed


def _airborne(s: SimState) -> bool:
    return not s.fdm.wow


ALERTS: list[Alert] = [
    # --- ENG ------------------------------------------------------------
    # master ON but engine not running outside a start sequence = failed
    Alert("ENG_1_FAIL", 3,
          lambda s: s.eng.master[0] and not s.eng.running[0]
          and s.eng.mode == "NORM"
          and s.eng.phase[0] in ("OFF", "SHUTDOWN"),
          (("ENG 1 FAIL", R), (" THR LEVER 1.....IDLE", C)), "ENG"),
    Alert("ENG_2_FAIL", 3,
          lambda s: s.eng.master[1] and not s.eng.running[1]
          and s.eng.mode == "NORM"
          and s.eng.phase[1] in ("OFF", "SHUTDOWN"),
          (("ENG 2 FAIL", R), (" THR LEVER 2.....IDLE", C)), "ENG"),
    Alert("ENG_DUAL_FAILURE", 3,
          lambda s: _airborne(s) and not any(s.eng.running),
          (("ENG DUAL FAILURE", R), (" EMER ELEC PWR...MAN ON", C)), "ELEC"),
    # --- ELEC -----------------------------------------------------------
    Alert("ELEC_GEN_1_FAULT", 2,
          lambda s: s.elec.gen1_fault and s.elec.gen1,
          (("ELEC GEN 1 FAULT", A), (" GEN 1........OFF THEN ON", C)), "ELEC"),
    Alert("ELEC_GEN_2_FAULT", 2,
          lambda s: s.elec.gen2_fault and s.elec.gen2,
          (("ELEC GEN 2 FAULT", A), (" GEN 2........OFF THEN ON", C)), "ELEC"),
    Alert("ELEC_EMER_CONFIG", 3,
          lambda s: _airborne(s) and not s.elec.ac1 and not s.elec.ac2,
          (("ELEC EMER CONFIG", R), (" MIN RAT SPD.......140 KT", C)), "ELEC"),
    # --- HYD ------------------------------------------------------------
    Alert("HYD_G_SYS_LO_PR", 2,
          lambda s: any(s.eng.running) and s.hyd.green_press_psi < 1450,
          (("HYD G SYS LO PR", A), (" PTU..............CHECK", C)), "HYD"),
    Alert("HYD_B_SYS_LO_PR", 2,
          lambda s: (any(s.eng.running) or _airborne(s))
          and s.hyd.blue_press_psi < 1450,
          (("HYD B SYS LO PR", A),), "HYD"),
    Alert("HYD_Y_SYS_LO_PR", 2,
          lambda s: any(s.eng.running) and s.hyd.yellow_press_psi < 1450,
          (("HYD Y SYS LO PR", A), (" PTU..............CHECK", C)), "HYD"),
    Alert("HYD_G_Y_LO_PR", 3,
          lambda s: _airborne(s) and s.hyd.green_press_psi < 1450
          and s.hyd.yellow_press_psi < 1450,
          (("HYD G+Y SYS LO PR", R), (" FLT CTL......ALTN LAW", C)), "HYD"),
    # --- FUEL -----------------------------------------------------------
    Alert("FUEL_L_PUMPS_LO_PR", 2,
          lambda s: (s.elec.ac1 or s.elec.ac2)
          and not s.fuel.l_pumps_pressurized and any(s.eng.running),
          (("FUEL L TK PUMP 1+2 LO PR", A), (" GRVTY FEED ONLY", C)), "FUEL"),
    Alert("FUEL_R_PUMPS_LO_PR", 2,
          lambda s: (s.elec.ac1 or s.elec.ac2)
          and not s.fuel.r_pumps_pressurized and any(s.eng.running),
          (("FUEL R TK PUMP 1+2 LO PR", A), (" GRVTY FEED ONLY", C)), "FUEL"),
    Alert("FUEL_WING_LO_LVL", 2,
          lambda s: s.fuel.inner_l + s.fuel.outer_l < 1650
          or s.fuel.inner_r + s.fuel.outer_r < 1650,
          (("FUEL L(R) WING TK LO LVL", A), (" FUEL XFEED.........ON", C)),
          "FUEL"),
    # --- BLEED / PRESS ----------------------------------------------------
    Alert("BLEED_1_FAULT", 2,
          lambda s: s.bleed.eng1_bleed and s.eng.running[0]
          and not s.bleed.eng1_bleed_avail,
          (("AIR ENG 1 BLEED FAULT", A),), "BLEED"),
    Alert("BLEED_2_FAULT", 2,
          lambda s: s.bleed.eng2_bleed and s.eng.running[1]
          and not s.bleed.eng2_bleed_avail,
          (("AIR ENG 2 BLEED FAULT", A),), "BLEED"),
    Alert("CAB_PR_EXCESS_CAB_ALT", 3,
          lambda s: s.press.cabin_alt_ft > 9550,
          (("CAB PR EXCESS CAB ALT", R),
           (" CREW OXY MASKS.....ON", C),
           (" DESCENT.......INITIATE", C)), "PRESS"),
    Alert("CAB_PR_LO_DIFF_PR", 2,
          lambda s: _airborne(s) and s.fdm.alt_ft > 15000
          and not s.bleed.pack1_flow and not s.bleed.pack2_flow,
          (("CAB PR SYS 1+2 FAULT", A), (" PACK 1+2......CHECK", C)),
          "PRESS"),
    # --- F/CTL ------------------------------------------------------------
    Alert("FCTL_ALTN_LAW", 2,
          lambda s: s.fctl.law == "alternate",
          (("F/CTL ALTN LAW", A), (" (PROT LOST)", A),
           (" MAX SPEED.......320/.77", C)), "F/CTL"),
    Alert("FCTL_DIRECT_LAW", 2,
          lambda s: s.fctl.law == "direct",
          (("F/CTL DIRECT LAW", A), (" (PROT LOST)", A),
           (" MAN PITCH TRIM....USE", C)), "F/CTL"),
    # --- CONFIG / MISC ------------------------------------------------------
    Alert("CONFIG_PARK_BRK", 3,
          lambda s: s.fdm.wow and s.ctl.parking_brake
          and all(s.eng.running)
          and s.ctl.thrust_detent in ("FLX", "TOGA"),
          (("CONFIG PARK BRK ON", R),), ""),
    Alert("APU_LOW_FUEL", 2,
          lambda s: s.apu.state in ("START", "AVAIL")
          and s.fuel.total_lbs < 500,
          (("APU FUEL LO LVL", A),), "APU"),
]


def memos(s: SimState) -> list:
    """Green memo lines for the E/WD right column."""
    out = []
    if s.apu.avail:
        out.append(("APU AVAIL", G))
    if s.bleed.apu_bleed and s.apu.avail:
        out.append(("APU BLEED", G))
    if s.ctl.parking_brake and s.fdm.wow:
        out.append(("PARK BRK", G))
    if s.fuel.xfeed:
        out.append(("FUEL X FEED", G))
    if s.eng.mode == "IGN_START":
        out.append(("IGNITION", G))
    if s.ctl.speedbrake > 0.05:
        out.append(("SPEED BRK", G))
    if s.sim.paused:
        out.append(("SIM PAUSED", C))
    return out
