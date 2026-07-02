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
    thrust_lever: float = 0.0    # 0..1 (detents arrive with M2 A/THR)
    flaps_setting: int = 0       # 0..4 = A320 flap lever positions
    gear_down: bool = True
    speedbrake: float = 0.0      # 0..1
    parking_brake: bool = True


@dataclass
class AutopilotState:
    """Provisional M1 autopilot (evolves into FCU + mode logic in M2)."""

    ap_engaged: bool = False
    athr_engaged: bool = False
    sel_hdg_deg: float = 90.0
    sel_alt_ft: float = 33000.0
    sel_spd_kts: float = 280.0
    sel_vs_fpm: float = 0.0      # 0 = fly direct-to-altitude profile
    # Attitude targets produced by the outer loops / manual input,
    # consumed by the FBW inner loop every FDM step.
    pitch_target_deg: float = 0.0
    roll_target_deg: float = 0.0


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
    ap: AutopilotState = field(default_factory=AutopilotState)
    sim: SimMeta = field(default_factory=SimMeta)
