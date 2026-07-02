"""Performance approximations: characteristic speeds and managed schedule.

Simple weight-based fits adequate for guidance and PFD speed-tape
markers; replace with table data if higher fidelity is ever needed.
Weights in lbs, speeds in kts CAS.
"""

from __future__ import annotations

REF_WEIGHT_LBS = 140000.0

# stall-ish reference speeds at REF_WEIGHT by flap setting (clean..full)
VS1G_REF = (168.0, 138.0, 128.0, 121.0, 116.0)


def _weight_factor(weight_lbs: float) -> float:
    return max(0.7, min(1.3, (weight_lbs / REF_WEIGHT_LBS) ** 0.5))


def vls(weight_lbs: float, flaps: int) -> float:
    """Lowest selectable speed: 1.23 * Vs1g clean/landing, 1.18 takeoff."""
    margin = 1.23 if flaps in (0, 4) else 1.18
    vs1g = VS1G_REF[max(0, min(4, flaps))] * _weight_factor(weight_lbs)
    return vs1g * margin / 1.23


def green_dot(weight_lbs: float) -> float:
    """Best lift/drag speed, clean."""
    return 205.0 * _weight_factor(weight_lbs)


def s_speed(weight_lbs: float) -> float:
    """Minimum slat-retract speed."""
    return 185.0 * _weight_factor(weight_lbs)


def f_speed(weight_lbs: float) -> float:
    """Minimum flap-retract speed."""
    return 160.0 * _weight_factor(weight_lbs)


def vapp(weight_lbs: float, wind_gust_kts: float = 0.0) -> float:
    return vls(weight_lbs, 4) + 5.0 + min(wind_gust_kts / 3.0, 15.0)


def v2(weight_lbs: float, flaps: int = 1) -> float:
    return VS1G_REF[max(1, min(3, flaps))] * _weight_factor(weight_lbs) * 1.13


def managed_speed(phase: str, alt_ft: float, weight_lbs: float,
                  flaps: int = 0) -> float:
    """Managed target by phase; 250 below FL100 in climb/descent.

    In approach the target respects the current configuration (as the
    real FMGC does): green dot clean, S/F speeds in intermediate
    configs, VAPP in landing config.
    """
    if phase == "climb":
        return 250.0 if alt_ft < 10000 else 290.0
    if phase == "descent":
        return 250.0 if alt_ft < 10500 else 280.0
    if phase == "approach":
        if flaps == 0:
            return green_dot(weight_lbs)
        if flaps == 1:
            return s_speed(weight_lbs)
        if flaps == 2:
            return f_speed(weight_lbs)
        return vapp(weight_lbs)
    return 280.0  # cruise (fixed-cost-index stand-in)
