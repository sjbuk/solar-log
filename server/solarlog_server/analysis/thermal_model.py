"""Solar hot-water (thermal collector) model — later phase, initial version.

Collector efficiency (EN ISO 9806 quadratic model):

    eta = eta0 - a1 * dT / G - a2 * dT^2 / G,   dT = T_mean_fluid - T_ambient

so useful heat per m2 of aperture is  q = eta0*G - a1*dT - a2*dT^2  (clamped at 0).
Coefficients are typical published values; replace with the datasheet of a candidate
collector for a specific quote.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Collector:
    name: str
    eta0: float
    a1: float  # W/(m2 K)
    a2: float  # W/(m2 K2)


FLAT_PLATE = Collector("flat_plate", 0.78, 3.5, 0.015)
EVACUATED_TUBE = Collector("evacuated_tube", 0.65, 1.2, 0.008)
COLLECTORS = {c.name: c for c in (FLAT_PLATE, EVACUATED_TUBE)}


def useful_heat_w_m2(g: float, tamb: float | None, t_mean: float = 50.0, c: Collector = FLAT_PLATE) -> float:
    """Useful heat output in W per m2 of aperture. tamb None -> 10 degC (UK annual mean)."""
    if g <= 0:
        return 0.0
    dt = t_mean - (10.0 if tamb is None else tamb)
    return max(0.0, c.eta0 * g - c.a1 * dt - c.a2 * dt * dt)
