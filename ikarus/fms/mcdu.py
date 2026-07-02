"""MCDU: server-side page state machine rendering 14 lines of 24 chars.

Lines are lists of segments ``[col, text, color]`` (color in
w/g/c/a/m/y = white green cyan amber magenta yellow). The browser MCDU
is a dumb terminal: it draws segments and sends key names back
(``mcdu.key`` command). All page logic lives here, so pytest can drive
the MCDU exactly like the UI does and assert on rendered text.

Keys: A..Z 0..9 . / - CLR OVFY, LSK1L..LSK6L, LSK1R..LSK6R,
      INIT FPLN RADNAV PERF PROG DIR, UP DOWN.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ikarus.fms import perf, vertical
from ikarus.fms.flightplan import PlanError

if TYPE_CHECKING:
    from ikarus.fms.system import FmsSystem

N_COLS = 24
LSK_ROWS = {1: 2, 2: 4, 3: 6, 4: 8, 5: 10, 6: 12}  # LSK n -> value line


class Mcdu:
    def __init__(self, fms: "FmsSystem"):
        self.fms = fms
        self.page = "INIT"
        self.scratch = ""
        self.scroll = 0
        self._msg = ""

    # --- key handling -----------------------------------------------------------

    def key(self, k: str) -> None:
        k = str(k).upper()
        if k in ("INIT", "FPLN", "RADNAV", "PERF", "PROG", "DIR",
                 "DEPART", "ARRIVE"):
            self.page = "DIRTO" if k == "DIR" else k
            self.scroll = 0
        elif k == "CLR":
            if self._msg:
                self._msg = ""
            elif self.scratch:
                self.scratch = self.scratch[:-1]
            else:
                self.scratch = "CLR"
        elif k == "OVFY":
            pass  # overfly not modeled
        elif k == "UP":
            self.scroll += 1
        elif k == "DOWN":
            self.scroll = max(0, self.scroll - 1)
        elif k.startswith("LSK"):
            try:
                n = int(k[3])
                side = k[4]
            except (ValueError, IndexError):
                return
            self._lsk(n, side)
        elif len(k) == 1 and (k.isalnum() or k in "./-+ "):
            if self.scratch == "CLR":
                self.scratch = ""
            if len(self.scratch) < 22:
                self.scratch += k

    def _take_scratch(self) -> str:
        s = self.scratch
        self.scratch = ""
        return s

    def _error(self, msg: str) -> None:
        self._msg = msg

    def _lsk(self, n: int, side: str) -> None:
        handler = getattr(self, f"_lsk_{self.page.lower()}", None)
        if handler:
            try:
                handler(n, side)
            except PlanError as e:
                self._error(str(e).upper()[:22])

    # --- per-page LSK handlers ---------------------------------------------------

    def _lsk_init(self, n: int, side: str) -> None:
        if n == 1 and side == "R":
            entry = self._take_scratch()
            if "/" in entry:
                origin, dest = entry.split("/", 1)
                self.fms.plan.set_route(origin, dest)
                self.fms.plan_changed()
            else:
                self._error("FORMAT: FROM/TO")
        elif n == 6 and side == "L":
            entry = self._take_scratch()
            try:
                self.fms.cruise_alt_ft = float(entry) * 100 \
                    if len(entry) <= 3 else float(entry)
            except ValueError:
                self._error("FORMAT: CRZ FL")

    def _lsk_depart(self, n: int, side: str) -> None:
        plan = self.fms.plan
        if side == "L":
            runways = self._dep_runways()
            if not plan.dep_runway:
                if n <= len(runways):
                    plan.set_dep_runway(runways[n - 1].ident)
                    self.fms.plan_changed()
            else:
                sids = self._dep_sids()
                if n <= len(sids):
                    plan.set_sid(sids[n - 1])
                    self.fms.plan_changed()
        elif side == "R" and n == 6:
            plan.dep_runway = None
            plan.sid_name = ""
            plan._rebuild()
            self.fms.plan_changed()

    def _lsk_arrive(self, n: int, side: str) -> None:
        plan = self.fms.plan
        if side == "L":
            apprs = self._arr_approaches()
            if not plan.appr_name:
                if n <= len(apprs):
                    plan.set_approach(apprs[n - 1])
                    self.fms.plan_changed()
            else:
                stars = self._arr_stars()
                if n <= len(stars):
                    plan.set_star(stars[n - 1])
                    self.fms.plan_changed()
        elif side == "R" and n == 6:
            plan.appr_name = plan.star_name = ""
            plan.arr_runway = None
            plan._rebuild()
            self.fms.plan_changed()

    def _lsk_fpln(self, n: int, side: str) -> None:
        plan = self.fms.plan
        idx = plan.active_idx + self.scroll + (n - 1)
        entry = self._take_scratch()
        if entry == "CLR":
            if 0 <= idx < len(plan.waypoints):
                plan.delete_enroute_fix(plan.waypoints[idx].ident)
                self.fms.plan_changed()
        elif entry:
            # insert typed fix before the displayed row's waypoint,
            # positioned within the enroute segment
            plan.insert_fix(entry)
            self.fms.plan_changed()

    def _lsk_dirto(self, n: int, side: str) -> None:
        plan = self.fms.plan
        entry = self._take_scratch()
        fdm = self.fms.state.fdm
        if entry and entry != "CLR":
            plan.direct_to(entry, fdm.lat_deg, fdm.lon_deg)
            self.fms.plan_changed()
            self.page = "FPLN"
            return
        idx = plan.active_idx + self.scroll + (n - 1)
        if 0 <= idx < len(plan.waypoints):
            plan.direct_to(plan.waypoints[idx].ident,
                           fdm.lat_deg, fdm.lon_deg)
            self.fms.plan_changed()
            self.page = "FPLN"

    def _lsk_radnav(self, n: int, side: str) -> None:
        radio = self.fms.state.radio
        entry = self._take_scratch()
        if not entry or entry == "CLR":
            entry = "0"
        try:
            freq = float(entry) * 1000 if "." in entry else float(entry)
        except ValueError:
            self._error("FORMAT: 114.20")
            return
        if n == 1 and side == "L":
            radio.nav1_freq_khz = freq
        elif n == 1 and side == "R":
            radio.nav2_freq_khz = freq

    # --- rendering ----------------------------------------------------------------

    def render(self) -> list[list]:
        lines = [[] for _ in range(14)]
        getattr(self, f"_render_{self.page.lower()}", self._render_init)(lines)
        # scratchpad / message line
        if self._msg:
            lines[13] = [[0, self._msg, "a"]]
        else:
            lines[13] = [[0, self.scratch or "", "w"]]
        return lines

    @staticmethod
    def _title(lines: list, text: str, color: str = "w") -> None:
        col = max(0, (N_COLS - len(text)) // 2)
        lines[0] = [[col, text, color]]

    @staticmethod
    def _label(lines: list, row: int, side: str, text: str) -> None:
        line = LSK_ROWS[row] - 1
        col = 0 if side == "L" else max(0, N_COLS - len(text))
        lines[line].append([col, text, "w"])

    @staticmethod
    def _value(lines: list, row: int, side: str, text: str,
               color: str = "c") -> None:
        line = LSK_ROWS[row]
        col = 0 if side == "L" else max(0, N_COLS - len(text))
        lines[line].append([col, text, color])

    def _render_init(self, lines: list) -> None:
        plan = self.fms.plan
        self._title(lines, "INIT")
        self._label(lines, 1, "R", "FROM/TO")
        route = f"{plan.origin or '____'}/{plan.dest or '____'}"
        self._value(lines, 1, "R", route, "c" if plan.origin else "a")
        self._label(lines, 6, "L", "CRZ FL")
        self._value(lines, 6, "L", f"FL{int(self.fms.cruise_alt_ft / 100)}")
        if plan.origin:
            self._label(lines, 3, "L", "DEPART>")
            self._label(lines, 3, "R", "ARRIVE>")

    def _dep_runways(self):
        return self.fms.plan.navdb.runways(self.fms.plan.origin)

    def _dep_sids(self):
        procs = self.fms.plan._dep_procs
        rwy = self.fms.plan.dep_runway
        if not procs:
            return []
        return [name for name, sid in procs.sids.items()
                if not sid.runways or not rwy or rwy.ident in sid.runways]

    def _arr_approaches(self):
        procs = self.fms.plan._arr_procs
        return list(procs.approaches) if procs else []

    def _arr_stars(self):
        procs = self.fms.plan._arr_procs
        appr = self.fms.plan.appr_name
        rwy = self.fms.plan.arr_runway
        if not procs:
            return []
        return [name for name, star in procs.stars.items()
                if not star.runways or not rwy or rwy.ident in star.runways]

    def _render_depart(self, lines: list) -> None:
        plan = self.fms.plan
        self._title(lines, f"DEPART {plan.origin}")
        if not plan.dep_runway:
            self._label(lines, 1, "L", "RWYS")
            for i, r in enumerate(self._dep_runways()[:5]):
                self._value(lines, i + 1, "L", f"<{r.ident}", "c")
        else:
            self._label(lines, 1, "L",
                        f"RWY {plan.dep_runway.ident}  SIDS")
            sids = self._dep_sids()
            for i, name in enumerate(sids[:5]):
                marker = " " if name != plan.sid_name else "*"
                self._value(lines, i + 1, "L", f"<{name}{marker}", "c")
            self._label(lines, 6, "R", "CLEAR>")
        if plan.sid_name:
            self._value(lines, 6, "R", plan.sid_name, "g")

    def _render_arrive(self, lines: list) -> None:
        plan = self.fms.plan
        self._title(lines, f"ARRIVE {plan.dest}")
        if not plan.appr_name:
            self._label(lines, 1, "L", "APPROACHES")
            for i, name in enumerate(self._arr_approaches()[:5]):
                self._value(lines, i + 1, "L", f"<{name}", "c")
        else:
            self._label(lines, 1, "L",
                        f"{plan.appr_name}  STARS")
            for i, name in enumerate(self._arr_stars()[:5]):
                marker = " " if name != plan.star_name else "*"
                self._value(lines, i + 1, "L", f"<{name}{marker}", "c")
            self._label(lines, 6, "R", "CLEAR>")

    def _render_fpln(self, lines: list) -> None:
        plan = self.fms.plan
        self._title(lines, f"F-PLN {plan.origin}-{plan.dest}"
                    if plan.origin else "F-PLN")
        start = max(plan.active_idx + self.scroll, 0)
        for row in range(1, 7):
            idx = start + row - 1
            if idx >= len(plan.waypoints):
                if idx == len(plan.waypoints):
                    self._value(lines, row, "L", "----END OF F-PLN----", "w")
                break
            w = plan.waypoints[idx]
            color = "w" if idx < plan.active_idx else \
                ("g" if idx > plan.active_idx else "m")
            cons = ""
            if w.alt_above and w.alt_below and w.alt_above == w.alt_below:
                cons = f" {int(w.alt_above)}"
            elif w.alt_above:
                cons = f" +{int(w.alt_above)}"
            elif w.alt_below:
                cons = f" -{int(w.alt_below)}"
            if w.speed:
                cons += f" /{int(w.speed)}"
            self._value(lines, row, "L", f"{w.ident}{cons}", color)

    def _render_dirto(self, lines: list) -> None:
        plan = self.fms.plan
        self._title(lines, "DIR TO")
        self._label(lines, 1, "L", "WAYPOINT")
        start = max(plan.active_idx, 0)
        for row in range(1, 7):
            idx = start + self.scroll + row - 1
            if idx >= len(plan.waypoints):
                break
            self._value(lines, row, "L",
                        f"<{plan.waypoints[idx].ident}", "c")

    def _render_radnav(self, lines: list) -> None:
        radio = self.fms.state.radio
        self._title(lines, "RADIO NAV")
        self._label(lines, 1, "L", "VOR1/FREQ")
        f1 = radio.nav1_freq_khz / 1000
        self._value(lines, 1, "L",
                    f"{radio.nav1_ident or '[  ]'}/{f1:.2f}" if f1 else "[ ]/[ ]")
        self._label(lines, 1, "R", "VOR2/FREQ")
        f2 = radio.nav2_freq_khz / 1000
        self._value(lines, 1, "R",
                    f"{radio.nav2_ident or '[  ]'}/{f2:.2f}" if f2 else "[ ]/[ ]")
        self._label(lines, 3, "L", "ILS/FREQ (AUTO)")
        fms = self.fms.state.fms
        if fms.appr_freq_khz:
            self._value(lines, 3, "L",
                        f"{fms.appr_ident}/{fms.appr_freq_khz / 1000:.2f}", "g")
        if radio.nav1_ok:
            self._label(lines, 5, "L", "DME1")
            self._value(lines, 5, "L", f"{radio.nav1_dme_nm}", "g")
        if radio.nav2_ok:
            self._label(lines, 5, "R", "DME2")
            self._value(lines, 5, "R", f"{radio.nav2_dme_nm}", "g")

    def _render_perf(self, lines: list) -> None:
        st = self.fms.state
        weight = st.fdm.weight_lbs
        self._title(lines, f"PERF {self.fms.phase.upper()}")
        self._label(lines, 1, "L", "MANAGED SPD")
        self._value(lines, 1, "L",
                    f"{perf.managed_speed(self.fms.phase, st.fdm.alt_ft, weight):.0f}", "g")
        self._label(lines, 2, "L", "GREEN DOT")
        self._value(lines, 2, "L", f"{perf.green_dot(weight):.0f}", "g")
        self._label(lines, 3, "L", "S / F")
        self._value(lines, 3, "L",
                    f"{perf.s_speed(weight):.0f} / {perf.f_speed(weight):.0f}", "g")
        self._label(lines, 4, "L", "VLS")
        self._value(lines, 4, "L",
                    f"{perf.vls(weight, st.ctl.flaps_setting):.0f}", "a")
        self._label(lines, 5, "L", "VAPP")
        self._value(lines, 5, "L", f"{perf.vapp(weight):.0f}", "m")

    def _render_prog(self, lines: list) -> None:
        st = self.fms.state
        fms = st.fms
        self._title(lines, "PROG")
        self._label(lines, 1, "L", "CRZ")
        self._value(lines, 1, "L", f"FL{int(self.fms.cruise_alt_ft / 100)}")
        self._label(lines, 2, "L", "DIST TO DEST")
        self._value(lines, 2, "L", f"{fms.dist_to_dest_nm:.0f}", "g")
        self._label(lines, 3, "L", "V/DEV")
        self._value(lines, 3, "L", f"{fms.vdev_ft:+.0f} FT", "g")
        self._label(lines, 4, "L", "XTK")
        self._value(lines, 4, "L", f"{fms.xtk_nm:+.2f} NM", "g")
