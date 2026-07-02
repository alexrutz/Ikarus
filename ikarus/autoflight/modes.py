"""Autoflight mode logic: armed/active mode state machine + FMA words.

The FCU knob actions (push/pull/set) arrive as method calls from the
command registry; `update()` runs every systems tick and handles
automatic transitions (ALT* capture, ALT hold, lever detent changes).

Mode coupling rule (encoded in `speed_on_thrust`): the A/THR holds speed
whenever the elevator is holding a path (ALT, ALT*, V/S); when thrust is
fixed (OP CLB -> THR CLB, OP DES -> THR IDLE) the elevator holds speed
instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from ikarus.core.state import SimState

ALT_CAPTURE_DECEL_FPS2 = 1.9   # capture arc steepness
ALT_HOLD_BAND_FT = 20.0
ALT_STAR_MIN_BAND_FT = 80.0
NAV_CAPTURE_XTK_NM = 1.5
LOC_CAPTURE_DOTS = 1.6
LOC_TRACK_DOTS = 0.25
GS_CAPTURE_DOTS = 0.8
GS_TRACK_DOTS = 0.25


@dataclass
class ModeEvents:
    """Set by knob actions, consumed by the next update()."""

    reset_vertical: bool = False


class ModeLogic:
    def __init__(self, state: SimState):
        self.state = state
        self.lat_active = ""       # HDG, NAV, LOC*, LOC
        self.lat_armed = ""
        self.vert_active = ""      # ALT, ALT*, V/S, OP CLB/DES, CLB/DES, G/S*
        self.vert_armed = ""
        self.athr_mode = ""        # SPEED, MACH, THR CLB, THR IDLE, MAN *
        self._alt_star_ref = 0.0   # FCU altitude when ALT* engaged

    # --- knob/lever actions --------------------------------------------------

    def hdg_pull(self) -> None:
        """Selected heading: fly the FCU heading."""
        self.state.fcu.hdg_managed = False
        if self.lat_active in ("NAV", "LOC*", "LOC"):
            self.lat_armed = ""
        self.lat_active = "HDG"

    def hdg_push(self) -> None:
        """Managed lateral: arm/engage NAV when a flight plan exists."""
        fms = self.state.fms
        if not fms.legs and not fms.nav_ok:
            self.hdg_pull()
            return
        self.state.fcu.hdg_managed = True
        if fms.nav_ok and abs(fms.xtk_nm) < NAV_CAPTURE_XTK_NM:
            self.lat_active = "NAV"
            self.lat_armed = ""
        else:
            self.lat_armed = "NAV"  # HDG remains active until capture
            if not self.lat_active:
                self.lat_active = "HDG"

    def vs_pull(self) -> None:
        fcu, fdm = self.state.fcu, self.state.fdm
        if fcu.vs_fpm is None:
            fcu.vs_fpm = round(fdm.vs_fpm / 100) * 100
        self.vert_active = "V/S"
        self._arm_alt_if_selected()

    def vs_push(self) -> None:
        """Push-to-level: V/S 0."""
        self.state.fcu.vs_fpm = 0.0
        self.vert_active = "V/S"
        self._arm_alt_if_selected()

    def alt_pull(self) -> None:
        """Open climb/descend to the FCU altitude (speed on elevator)."""
        fcu, fdm = self.state.fcu, self.state.fdm
        if fcu.alt_ft > fdm.alt_ft + 100:
            self.vert_active = "OP CLB"
        elif fcu.alt_ft < fdm.alt_ft - 100:
            self.vert_active = "OP DES"
        else:
            return
        fcu.vs_fpm = None
        self.vert_armed = "ALT"

    def alt_push(self) -> None:
        """Managed climb/descent: respects FMS constraints/profile."""
        fcu, fdm, fms = self.state.fcu, self.state.fdm, self.state.fms
        if not fms.nav_ok:
            self.alt_pull()
            return
        if fcu.alt_ft > fdm.alt_ft + 100:
            self.vert_active = "CLB"
        elif fcu.alt_ft < fdm.alt_ft - 100:
            self.vert_active = "DES"
        else:
            return
        fcu.vs_fpm = None
        self.vert_armed = "ALT"

    def loc_toggle(self) -> None:
        fcu = self.state.fcu
        fcu.loc = not fcu.loc
        fcu.appr = False
        if fcu.loc:
            if self.lat_active not in ("LOC*", "LOC"):
                self.lat_armed = "LOC"
        else:
            self._clear_approach_modes()

    def appr_toggle(self) -> None:
        fcu = self.state.fcu
        fcu.appr = not fcu.appr
        fcu.loc = False
        if fcu.appr:
            if self.lat_active not in ("LOC*", "LOC"):
                self.lat_armed = "LOC"
            if self.vert_active not in ("G/S*", "G/S"):
                self.vert_armed = "G/S"
        else:
            self._clear_approach_modes()

    def _clear_approach_modes(self) -> None:
        if self.lat_armed in ("LOC",):
            self.lat_armed = ""
        if self.vert_armed in ("G/S",):
            self.vert_armed = ""
        if self.lat_active in ("LOC*", "LOC"):
            self.state.fcu.hdg_deg = round(self.state.fdm.hdg_true_deg) % 360
            self.lat_active = "HDG"
        if self.vert_active in ("G/S*", "G/S"):
            self.state.fcu.vs_fpm = round(self.state.fdm.vs_fpm / 100) * 100
            self.vert_active = "V/S"

    def spd_pull(self) -> None:
        fcu, fdm = self.state.fcu, self.state.fdm
        if fcu.spd_managed:
            fcu.spd_kts = max(round(fdm.cas_kts), 100)
            fcu.spd_is_mach = False
        fcu.spd_managed = False

    def spd_push(self) -> None:
        """Managed speed: the FMS speed schedule drives the target."""
        fms = self.state.fms
        self.state.fcu.spd_managed = bool(fms.nav_ok or fms.legs)

    def ap_toggle(self, engage: bool | None = None) -> None:
        fcu = self.state.fcu
        was = fcu.ap1
        fcu.ap1 = (not was) if engage is None else bool(engage)
        if fcu.ap1 and not was:
            self._sync_engagement()

    def athr_toggle(self, engage: bool | None = None) -> None:
        fcu = self.state.fcu
        fcu.athr = (not fcu.athr) if engage is None else bool(engage)

    def _sync_engagement(self) -> None:
        """Bumpless AP engagement: hold present heading/trajectory."""
        fcu, fdm = self.state.fcu, self.state.fdm
        if not self.lat_active:
            fcu.hdg_deg = round(fdm.hdg_true_deg) % 360
            self.lat_active = "HDG"
        if not self.vert_active:
            if abs(fcu.alt_ft - fdm.alt_ft) < 250:
                self.vert_active = "ALT"
            else:
                fcu.vs_fpm = round(fdm.vs_fpm / 100) * 100
                self.vert_active = "V/S"
                self._arm_alt_if_selected()

    def _track_toward_course(self, course_mag: float) -> bool:
        """LOC capture sanity: not crossing the beam near-perpendicular."""
        from ikarus.nav import geo
        fdm = self.state.fdm
        course_true = (course_mag
                       + geo.magvar_deg(fdm.lat_deg, fdm.lon_deg)) % 360.0
        return abs(geo.angle_diff_deg(course_true, fdm.track_true_deg)) < 100.0

    def _arm_alt_if_selected(self) -> None:
        fcu, fdm = self.state.fcu, self.state.fdm
        vs = fcu.vs_fpm or 0.0
        toward = (fcu.alt_ft - fdm.alt_ft) * vs > 0
        self.vert_armed = "ALT" if toward and self.vert_active != "ALT" else ""

    # --- periodic update -------------------------------------------------------

    def update(self) -> None:
        state = self.state
        fcu, fdm, ctl = state.fcu, state.fdm, state.ctl

        guidance_active = fcu.ap1 or fcu.fd
        if not guidance_active:
            self.lat_active = self.vert_active = ""
            self.lat_armed = self.vert_armed = ""

        if guidance_active and not self.vert_active:
            self._sync_engagement()

        # --- approach arming (continuous while the button is latched) ----------
        fms, radio = state.fms, state.radio
        if (fcu.loc or fcu.appr) and self.lat_active not in ("LOC*", "LOC"):
            self.lat_armed = "LOC"
        if fcu.appr and self.vert_active not in ("G/S*", "G/S"):
            self.vert_armed = "G/S"

        # --- lateral captures --------------------------------------------------
        if self.lat_armed == "NAV" and fms.nav_ok \
                and abs(fms.xtk_nm) < NAV_CAPTURE_XTK_NM:
            self.lat_active = "NAV"
            self.lat_armed = ""
        if self.lat_active == "NAV" and not fms.nav_ok:
            fcu.hdg_deg = round(fdm.hdg_true_deg) % 360
            self.lat_active = "HDG"
        if self.lat_armed == "LOC" and radio.ils_ok \
                and abs(radio.ils_loc_dots) < LOC_CAPTURE_DOTS \
                and self._track_toward_course(radio.ils_course_mag):
            self.lat_active = "LOC*"
            self.lat_armed = ""
        if self.lat_active == "LOC*" and abs(radio.ils_loc_dots) < LOC_TRACK_DOTS:
            self.lat_active = "LOC"

        # G/S arms only engage after LOC capture
        if self.vert_armed == "G/S" and radio.ils_ok \
                and self.lat_active in ("LOC*", "LOC") \
                and abs(radio.ils_gs_dots) < GS_CAPTURE_DOTS:
            self.vert_active = "G/S*"
            self.vert_armed = ""
            fcu.vs_fpm = None
        if self.vert_active == "G/S*" and abs(radio.ils_gs_dots) < GS_TRACK_DOTS:
            self.vert_active = "G/S"

        # --- vertical captures ------------------------------------------------
        alt_err = fcu.alt_ft - fdm.alt_ft
        if self.vert_active in ("V/S", "OP CLB", "OP DES", "CLB", "DES"):
            vs_fps = abs(fdm.vs_fpm) / 60.0
            capture_band = max(ALT_STAR_MIN_BAND_FT,
                               vs_fps * vs_fps / (2 * ALT_CAPTURE_DECEL_FPS2))
            closing = alt_err * fdm.vs_fpm > 0 or abs(alt_err) < ALT_STAR_MIN_BAND_FT
            if abs(alt_err) < capture_band and closing:
                self.vert_active = "ALT*"
                if self.vert_armed == "ALT":
                    self.vert_armed = ""
                fcu.vs_fpm = None
                self._alt_star_ref = fcu.alt_ft
        if self.vert_active == "ALT*":
            if abs(alt_err) < ALT_HOLD_BAND_FT and abs(fdm.vs_fpm) < 200:
                self.vert_active = "ALT"
            elif fcu.alt_ft != self._alt_star_ref:
                # FCU altitude knob moved during capture: revert to V/S
                fcu.vs_fpm = round(fdm.vs_fpm / 100) * 100
                self.vert_active = "V/S"
                self._arm_alt_if_selected()
        if self.vert_active == "ALT" and abs(alt_err) > 250:
            # Altitude knob moved: hold until the pilot pulls/pushes.
            pass

        # --- A/THR mode -------------------------------------------------------
        detent = ctl.thrust_detent
        if detent in ("TOGA", "FLX"):
            self.athr_mode = f"MAN {detent}"
        elif not fcu.athr:
            self.athr_mode = ""
        elif detent in ("CLB", "MAN"):
            if self.vert_active in ("OP CLB", "CLB"):
                self.athr_mode = "THR CLB"
            elif self.vert_active == "OP DES" or (
                    self.vert_active == "DES" and state.fms.vdev_ft > -200):
                self.athr_mode = "THR IDLE"
            else:
                self.athr_mode = "MACH" if fcu.spd_is_mach else "SPEED"
        else:  # IDLE levers
            self.athr_mode = "THR IDLE" \
                if self.vert_active in ("OP DES", "DES") else ""

        self._write_fma()

    def speed_on_thrust(self) -> bool:
        return self.athr_mode in ("SPEED", "MACH")

    def _write_fma(self) -> None:
        fma, fcu, ctl = self.state.fma, self.state.fcu, self.state.ctl
        fma.thrust = self.athr_mode
        fma.thrust_man = self.athr_mode.startswith("MAN")
        vs = self.state.fcu.vs_fpm
        if self.vert_active == "V/S" and vs is not None:
            sign = "+" if vs >= 0 else "-"
            fma.vertical = f"V/S {sign}{abs(round(vs)):04d}"
        else:
            fma.vertical = self.vert_active
        fma.vertical_armed = self.vert_armed
        fma.lateral = self.lat_active
        fma.lateral_armed = self.lat_armed
        fma.ap = "AP1" if fcu.ap1 else ""
        fma.fd = "1FD2" if fcu.fd else ""
        athr_active = bool(fcu.athr and self.athr_mode
                           and not fma.thrust_man)
        fma.athr = "A/THR" if fcu.athr else ""
        fma.athr_active = athr_active
