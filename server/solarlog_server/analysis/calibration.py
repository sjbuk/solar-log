"""Reference-cell calibration: Isc (mA) -> plane-of-array irradiance (W/m2).

G = k * Isc. Default k comes from the cell's nominal Isc at STC (1000 W/m2). The auto
fit compares hourly means of measured Isc with modelled global tilted irradiance
(Open-Meteo, same tilt/azimuth). Shading at the site only ever *reduces* the measured
current, so the ratio GTI/Isc is biased high in shaded hours; using a low quantile
picks the unshaded, model-consistent hours.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence


def default_factor(isc_stc_ma: float) -> float:
    return 1000.0 / isc_stc_ma


def hourly_means(samples: Iterable[tuple[int, float]]) -> dict[int, float]:
    """Mean Isc per hour, keyed by the hour END epoch (Open-Meteo convention: the value
    stamped T is the mean over the preceding hour)."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for epoch, isc in samples:
        end = (epoch // 3600 + 1) * 3600 if epoch % 3600 else epoch
        buckets[end].append(isc)
    return {k: sum(v) / len(v) for k, v in buckets.items() if len(v) >= 30}


def fit_factor(
    pairs: Sequence[tuple[float, float]],
    min_gti: float = 300.0,
    min_isc: float = 5.0,
    quantile: float = 0.25,
    min_pairs: int = 5,
) -> float | None:
    """pairs: (measured mean Isc mA, modelled GTI W/m2). Returns k in W/m2 per mA."""
    ratios = sorted(g / i for i, g in pairs if g >= min_gti and i >= min_isc)
    if len(ratios) < min_pairs:
        return None
    qs = statistics.quantiles(ratios, n=100, method="inclusive")
    idx = max(0, min(98, round(quantile * 100) - 1))
    return qs[idx]
