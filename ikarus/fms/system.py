"""FmsSystem: flight plan, guidance computation, MCDU, published FMS state.

Runs before the autoflight system each tick so NAV/managed modes see
fresh guidance. Publishes everything displays need into ``state.fms``.
"""

from __future__ import annotations

from ikarus.core.state import FmsLegState
from ikarus.fms import lateral, perf, vertical
from ikarus.nav import geo
from ikarus.fms.flightplan import FlightPlan
from ikarus.fms.mcdu import Mcdu
from ikarus.nav.database import NavDatabase
from ikarus.systems.base import System


class FmsSystem(System):
    name = "fms"

    def __init__(self, navdb: NavDatabase):
        super().__init__()
        self.navdb = navdb
        self.plan = FlightPlan(navdb)
        self.mcdu = Mcdu(self)
        self.cruise_alt_ft = 33000.0
        self.phase = "cruise"       # climb | cruise | descent | approach
        self._published_version = -1

    def plan_changed(self) -> None:
        """Called by the MCDU after any plan edit."""
        self._sync_approach_geometry()

    def init_situation(self, situation: str) -> None:
        fms = self.state.fms
        fms.mcdu_lines = self.mcdu.render()

    def _sync_approach_geometry(self) -> None:
        """Expose the selected approach to the ILS receiver."""
        fms = self.state.fms
        plan = self.plan
        fms.appr_freq_khz = 0.0
        fms.appr_thr_lat = 0.0
        if plan.appr_name and plan._arr_procs and plan.arr_runway:
            appr = plan._arr_procs.approaches[plan.appr_name]
            rwy = plan.arr_runway
            fms.appr_thr_lat = rwy.lat
            fms.appr_thr_lon = rwy.lon
            fms.appr_thr_elev_ft = rwy.elev_ft
            fms.appr_course_mag = appr.course_mag
            fms.appr_gs_deg = appr.gs_deg
            fms.appr_freq_khz = appr.loc_freq_khz
            fms.appr_ident = f"ILS{rwy.ident}"

    def _update_phase(self) -> None:
        fdm, fms = self.state.fdm, self.state.fms
        if fdm.wow:
            self.phase = "climb"
        elif self.phase in ("climb", "cruise"):
            if fdm.alt_ft > self.cruise_alt_ft - 500:
                self.phase = "cruise"
            if 0 <= fms.tod_dist_nm < 2 or (
                    self.phase == "cruise" and fdm.vs_fpm < -800
                    and fms.dist_to_dest_nm and fms.dist_to_dest_nm < 150):
                self.phase = "descent"
        if self.phase == "descent" and fms.dist_to_dest_nm \
                and fms.dist_to_dest_nm < 15:
            self.phase = "approach"

    def update(self, dt: float) -> None:
        fdm, fms = self.state.fdm, self.state.fms
        plan = self.plan

        if plan.active and not fdm.wow:
            plan.sequence(fdm.lat_deg, fdm.lon_deg, fdm.gs_kts)

        guidance = None
        if plan.active:
            guidance = lateral.compute(plan, fdm.lat_deg, fdm.lon_deg,
                                       fdm.track_true_deg, fdm.gs_kts)
        if guidance:
            fms.nav_roll_cmd_deg, fms.xtk_nm, course_true, fms.dtg_nm = guidance
            fms.course_mag = (course_true
                              - geo.magvar_deg(fdm.lat_deg, fdm.lon_deg)) % 360
            fms.nav_ok = True
        else:
            fms.nav_ok = False

        # vertical profile data
        if plan.active and plan.dest:
            dest = self.navdb.airport(plan.dest)
            fms.dist_to_dest_nm = vertical.dist_to_dest_nm(
                plan, fdm.lat_deg, fdm.lon_deg)
            fms.tod_dist_nm = vertical.tod_dist_nm(
                fms.dist_to_dest_nm, fdm.alt_ft, dest.elev_ft)
            fms.vdev_ft = fdm.alt_ft - vertical.profile_alt_ft(
                fms.dist_to_dest_nm, dest.elev_ft, self.cruise_alt_ft)
        else:
            fms.dist_to_dest_nm = 0.0
            fms.tod_dist_nm = -1.0
            fms.vdev_ft = 0.0

        self._update_phase()
        fms.managed_spd_kts = perf.managed_speed(
            self.phase, fdm.alt_ft, fdm.weight_lbs,
            self.state.ctl.flaps_setting)
        fms.clb_constraint_ft = vertical.next_alt_below_constraint(plan) \
            if plan.active else None

        # publish plan legs on change
        if plan.version != self._published_version:
            self._published_version = plan.version
            fms.origin, fms.dest = plan.origin, plan.dest
            fms.dep_runway = plan.dep_runway.ident if plan.dep_runway else ""
            fms.arr_runway = plan.arr_runway.ident if plan.arr_runway else ""
            fms.sid, fms.star = plan.sid_name, plan.star_name
            fms.approach = plan.appr_name
            fms.legs = [FmsLegState(w.ident, w.lat, w.lon, w.alt_above,
                                    w.alt_below, w.speed)
                        for w in plan.waypoints]
            fms.plan_version = plan.version
            self._sync_approach_geometry()
        fms.active_idx = plan.active_idx

        # MCDU render (cheap; every tick keeps DME/PROG live)
        fms.mcdu_lines = self.mcdu.render()
        fms.mcdu_scratch = self.mcdu.scratch
        fms.mcdu_page = self.mcdu.page
