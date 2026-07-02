"""System Display: page selection and per-page data assembly.

Page choice: pilot selection > page called by the highest alert >
phase-appropriate default. Data is a plain dict per page; the frontend
renders it.
"""

from __future__ import annotations

from ikarus.systems.base import System

PAGES = ("ENG", "BLEED", "PRESS", "ELEC", "HYD", "FUEL", "APU",
         "F/CTL", "CRUISE")


class SdSystem(System):
    name = "sd"

    def select_page(self, page: str) -> None:
        ecam = self.state.ecam
        page = page.upper()
        if page == ecam.sd_manual_page or page not in PAGES:
            ecam.sd_manual_page = ""    # second press deselects -> auto
        else:
            ecam.sd_manual_page = page

    def _auto_page(self) -> str:
        s = self.state
        for alert in s.ecam.alerts:
            if alert.sd_page and alert.id not in s.ecam.cleared_ids:
                return alert.sd_page
        phase = s.ecam.flight_phase
        if phase == 1:
            if s.apu.state in ("START",) or (s.apu.master and not s.apu.avail):
                return "APU"
            return "ELEC" if (s.elec.ac1 or s.elec.dc_bat) else "ENG"
        if phase in (2, 3, 7):
            return "ENG"
        return "CRUISE"

    def update(self, dt: float) -> None:
        s = self.state
        ecam = s.ecam
        page = ecam.sd_manual_page or self._auto_page()
        ecam.sd_page = page
        ecam.sd_data = getattr(self, f"_page_{page.lower().replace('/', '')}")()

    def _page_eng(self) -> dict:
        eng, f = self.state.eng, self.state.fuel
        return {
            "n1": [round(v, 1) for v in eng.n1],
            "n2": [round(v, 1) for v in eng.n2],
            "egt": [round(v) for v in eng.egt_c],
            "ff": [round(v) for v in eng.ff_pph],
            "phase": list(eng.phase),
            "fuel_used": [0, 0],
        }

    def _page_elec(self) -> dict:
        e, apu = self.state.elec, self.state.apu
        return {
            "ac1": e.ac1, "ac2": e.ac2, "ac_ess": e.ac_ess,
            "dc1": e.dc1, "dc2": e.dc2, "dc_bat": e.dc_bat, "dc_ess": e.dc_ess,
            "ac1_src": e.ac1_source, "ac2_src": e.ac2_source,
            "bat1": {"on": e.bat1, "v": e.bat1_voltage},
            "bat2": {"on": e.bat2, "v": e.bat2_voltage},
            "gen1": {"on": e.gen1, "load": e.gen1_load_pct, "fault": e.gen1_fault},
            "gen2": {"on": e.gen2, "load": e.gen2_load_pct, "fault": e.gen2_fault},
            "apu_gen": {"on": e.apu_gen, "load": apu.gen_load_pct,
                        "avail": apu.avail},
            "ext": {"avail": e.ext_pwr_avail, "on": e.ext_pwr},
        }

    def _page_hyd(self) -> dict:
        h = self.state.hyd
        return {
            "green": round(h.green_press_psi), "blue": round(h.blue_press_psi),
            "yellow": round(h.yellow_press_psi),
            "g_qty": round(h.green_qty, 2), "b_qty": round(h.blue_qty, 2),
            "y_qty": round(h.yellow_qty, 2),
            "eng1_pump": h.eng1_pump, "eng2_pump": h.eng2_pump,
            "blue_pump": h.blue_elec_pump, "yellow_elec": h.yellow_elec_pump,
            "ptu": h.ptu_running, "rat": h.rat_deployed,
        }

    def _page_fuel(self) -> dict:
        f = self.state.fuel
        return {
            "outer_l": round(f.outer_l), "inner_l": round(f.inner_l),
            "center": round(f.center), "inner_r": round(f.inner_r),
            "outer_r": round(f.outer_r), "total": round(f.total_lbs),
            "pumps": {"l1": f.pump_l1, "l2": f.pump_l2, "c1": f.pump_c1,
                      "c2": f.pump_c2, "r1": f.pump_r1, "r2": f.pump_r2},
            "xfeed": f.xfeed,
            "l_press": f.l_pumps_pressurized, "r_press": f.r_pumps_pressurized,
        }

    def _page_bleed(self) -> dict:
        b = self.state.bleed
        return {
            "duct1": round(b.duct1_psi), "duct2": round(b.duct2_psi),
            "eng1": b.eng1_bleed, "eng2": b.eng2_bleed,
            "apu": b.apu_bleed, "xbleed": b.xbleed,
            "xbleed_open": b.xbleed_open,
            "pack1": b.pack1, "pack2": b.pack2,
            "pack1_flow": b.pack1_flow, "pack2_flow": b.pack2_flow,
        }

    def _page_press(self) -> dict:
        p = self.state.press
        return {
            "cab_alt": round(p.cabin_alt_ft), "cab_vs": round(p.cabin_vs_fpm),
            "delta_p": round(p.delta_p_psi, 1),
            "outflow": round(p.outflow_pos, 2),
            "ldg_elev": round(p.ldg_elev_ft),
        }

    def _page_apu(self) -> dict:
        a = self.state.apu
        return {
            "n": round(a.n_pct, 1), "egt": round(a.egt_c),
            "state": a.state, "avail": a.avail, "flap": a.flap_open,
            "gen_load": round(a.gen_load_pct),
            "bleed": self.state.bleed.apu_bleed,
        }

    def _page_fctl(self) -> dict:
        fc = self.state.fctl
        fdm = self.state.fdm
        return {
            "law": fc.law,
            "elac": list(fc.elac), "sec": list(fc.sec), "fac": list(fc.fac),
            "elev": round(fdm.elevator_pos_norm, 2),
            "ail": round(fdm.aileron_pos_norm, 2),
            "rud": round(fdm.rudder_pos_norm, 2),
            "spdbrk": round(fdm.speedbrake_pos_norm, 2),
            "pitch_trim": round(fdm.pitch_trim_norm, 2),
        }

    def _page_cruise(self) -> dict:
        s = self.state
        return {
            "ff": [round(v) for v in s.eng.ff_pph],
            "fuel_total": round(s.fuel.total_lbs),
            "cab_alt": round(s.press.cabin_alt_ft),
            "delta_p": round(s.press.delta_p_psi, 1),
            "sat_c": round(15 - 1.98 * s.fdm.alt_ft / 1000),  # ISA approx
        }
