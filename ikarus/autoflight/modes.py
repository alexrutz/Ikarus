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


@dataclass
class ModeEvents:
    """Set by knob actions, consumed by the next update()."""

    reset_vertical: bool = False


class ModeLogic:
    def __init__(self, state: SimState):
        self.state = state
        self.lat_active = ""       # HDG (NAV, LOC*, LOC arrive with M3)
        self.lat_armed = ""
        self.vert_active = ""      # ALT, ALT*, V/S, OP CLB, OP DES
        self.vert_armed = ""
        self.athr_mode = ""        # SPEED, MACH, THR CLB, THR IDLE, MAN *

    # --- knob/lever actions --------------------------------------------------

    def hdg_pull(self) -> None:
        """Selected heading: fly the FCU heading."""
        self.state.fcu.hdg_managed = False
        self.lat_active = "HDG"

    def hdg_push(self) -> None:
        """Managed lateral (NAV) needs a flight plan — M3. Until then
        push behaves like pull so the FCU never dead-ends."""
        self.hdg_pull()

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
        """Managed climb/descent needs the FMS (M3); open mode until then."""
        self.alt_pull()

    def spd_pull(self) -> None:
        self.state.fcu.spd_managed = False

    def spd_push(self) -> None:
        """Managed speed arrives with the FMS (M3)."""
        self.state.fcu.spd_managed = False

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

        # --- vertical captures ------------------------------------------------
        alt_err = fcu.alt_ft - fdm.alt_ft
        if self.vert_active in ("V/S", "OP CLB", "OP DES"):
            vs_fps = abs(fdm.vs_fpm) / 60.0
            capture_band = max(ALT_STAR_MIN_BAND_FT,
                               vs_fps * vs_fps / (2 * ALT_CAPTURE_DECEL_FPS2))
            closing = alt_err * fdm.vs_fpm > 0 or abs(alt_err) < ALT_STAR_MIN_BAND_FT
            if abs(alt_err) < capture_band and closing:
                self.vert_active = "ALT*"
                self.vert_armed = ""
                fcu.vs_fpm = None
        if self.vert_active == "ALT*":
            if abs(alt_err) < ALT_HOLD_BAND_FT and abs(fdm.vs_fpm) < 200:
                self.vert_active = "ALT"
            elif abs(alt_err) > 1000:
                # FCU altitude moved away during capture: revert to V/S
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
            if self.vert_active == "OP CLB":
                self.athr_mode = "THR CLB"
            elif self.vert_active == "OP DES":
                self.athr_mode = "THR IDLE"
            else:
                self.athr_mode = "MACH" if fcu.spd_is_mach else "SPEED"
        else:  # IDLE levers
            self.athr_mode = "THR IDLE" if self.vert_active == "OP DES" else ""

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
