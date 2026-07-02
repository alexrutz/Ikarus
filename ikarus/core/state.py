"""SimState: the central state tree.

Every section is a plain dataclass owned by exactly one system (the
single-writer rule); any system may read any section. The WebSocket
snapshot is serialized from this same tree — there is no second data
model between simulation and displays.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ikarus.core.fdm import FdmState


@dataclass
class ControlsState:
    """Pilot inceptor state (keyboard/mouse fallback controls)."""

    pitch_input: float = 0.0     # -1..1, nose-up positive, decays to 0
    roll_input: float = 0.0      # -1..1, right positive, decays to 0
    rudder_input: float = 0.0    # -1..1, right positive, decays to 0
    # Sidestick attitude targets (used when AP is off)
    pitch_target_deg: float = 0.0
    roll_target_deg: float = 0.0
    # Thrust levers: a detent plus a manual position used in MAN
    thrust_detent: str = "IDLE"  # IDLE | MAN | CLB | FLX | TOGA
    thrust_manual: float = 0.0   # 0..1, lever position within manual range
    flaps_setting: int = 0       # 0..4 = A320 flap lever positions
    gear_down: bool = True
    speedbrake: float = 0.0      # 0..1
    parking_brake: bool = True


@dataclass
class FcuState:
    """Flight Control Unit: windows, selected/managed, engagement switches."""

    spd_kts: float = 280.0
    spd_is_mach: bool = False
    spd_managed: bool = False    # managed speed arrives with the FMS (M3)
    hdg_deg: float = 90.0
    hdg_managed: bool = False    # dashes; NAV mode arrives with M3
    alt_ft: float = 33000.0
    vs_fpm: float | None = None  # None = window dashed
    ap1: bool = False
    fd: bool = True
    athr: bool = False           # armed/active master switch


@dataclass
class FmaState:
    """Flight Mode Annunciator: five columns, rendered by the PFD."""

    thrust: str = ""             # col 1 (green or white if MAN)
    thrust_man: bool = False     # white MAN annunciation style
    vertical: str = ""           # col 2 active (green)
    vertical_armed: str = ""     # col 2 armed (cyan)
    lateral: str = ""            # col 3 active (green)
    lateral_armed: str = ""      # col 3 armed (cyan)
    ap: str = ""                 # col 5 line 1: AP1 / ""
    fd: str = ""                 # col 5 line 2: 1FD- style, simplified "FD"
    athr: str = ""               # col 5 line 3: A/THR (white=active, cyan=armed)
    athr_active: bool = False


@dataclass
class GuidanceState:
    """Autoflight guidance output: targets the FBW inner loop flies.

    Written only by the autoflight system. FD bars display the same
    targets, so the flight director is this state rendered.
    """

    pitch_target_deg: float = 0.0
    roll_target_deg: float = 0.0
    target_cas_kts: float = 280.0   # resolved (mach converted) A/THR target
    law: str = "normal"             # normal | alternate | direct (M5)


@dataclass
class SimMeta:
    time_s: float = 0.0
    paused: bool = False
    accel: int = 1
    situation: str = "cruise"


@dataclass
class SimState:
    fdm: FdmState
    ctl: ControlsState = field(default_factory=ControlsState)
    fcu: FcuState = field(default_factory=FcuState)
    fma: FmaState = field(default_factory=FmaState)
    guidance: GuidanceState = field(default_factory=GuidanceState)
    sim: SimMeta = field(default_factory=SimMeta)
