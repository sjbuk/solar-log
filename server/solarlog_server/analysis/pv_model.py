"""PV yield model for a nominal 1 kWp array at the measured plane-of-array irradiance.

    P [kW/kWp] = G/1000 * (1 + gamma * (T_mod - 25)) * PR

T_mod is estimated from ambient temperature with the NOCT model
(T_mod = T_amb + G/800 * (NOCT - 20)) because the small reference cell on the logger
box does not heat up like a roof-mounted module. PR (performance ratio, excluding
temperature) covers inverter, wiring, soiling and mismatch losses; 0.86 matches the
14 % system loss used for the PVGIS comparison.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PvParams:
    gamma: float = -0.004  # power temperature coefficient, 1/K (typical mono-Si)
    pr: float = 0.86  # performance ratio excluding temperature effects
    noct: float = 45.0  # nominal operating cell temperature, degC


def module_temperature(g: float, tamb: float | None, tcell: float | None, noct: float = 45.0) -> float:
    if tamb is not None:
        return tamb + g / 800.0 * (noct - 20.0)
    if tcell is not None:
        return tcell
    return 25.0


def pv_power_per_kwp(g: float, t_mod: float, p: PvParams = PvParams()) -> float:
    """AC power in kW per installed kWp."""
    if g <= 0:
        return 0.0
    return max(0.0, g / 1000.0 * (1.0 + p.gamma * (t_mod - 25.0)) * p.pr)


def integrate(series: Sequence[tuple[float, float]], max_gap_s: float = 300.0) -> tuple[float, float]:
    """Trapezoidal integral of (epoch, value) pairs, in value*hours.

    Pairs further apart than max_gap_s are not bridged (missing data / night). Returns
    (integral, covered_seconds)."""
    total = 0.0
    covered = 0.0
    for (t0, v0), (t1, v1) in zip(series, series[1:]):
        dt = t1 - t0
        if 0 < dt <= max_gap_s:
            total += (v0 + v1) / 2.0 * dt / 3600.0
            covered += dt
    return total, covered


def energy_kwh_per_kwp(
    samples: Iterable[tuple[float, float, float | None, float | None]],
    p: PvParams = PvParams(),
    max_gap_s: float = 300.0,
) -> tuple[float, float]:
    """samples: (epoch, G W/m2, tamb, tcell) sorted by time. Returns (kWh/kWp, covered s)."""
    series = [
        (t, pv_power_per_kwp(g, module_temperature(g, ta, tc, p.noct), p)) for t, g, ta, tc in samples
    ]
    return integrate(series, max_gap_s)
