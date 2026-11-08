"""Turn stored samples into daily / monthly results."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from zoneinfo import ZoneInfo

from .analysis import pv_model, thermal_model
from .analysis.solar import daylight_seconds
from .db import Device, Sample

# Record flag bits (firmware/lib/core/src/record.h)
FLAG_CHARGING = 1 << 0
FLAG_CHARGE_LOCKOUT = 1 << 1
FLAG_ISC_INVALID = 1 << 4
FLAG_TIME_UNSYNCED = 1 << 5


@dataclass
class DailyResult:
    date: str
    samples: int
    coverage: float  # fraction of sun-up time covered by data
    peak_irradiance: float  # W/m2
    insolation_kwh_m2: float
    pv_kwh_per_kwp: float
    thermal_flat_kwh_m2: float
    thermal_tube_kwh_m2: float
    tamb_mean: float | None
    vbat_min: float

    def as_dict(self) -> dict:
        return asdict(self)


def usable(s: Sample) -> bool:
    return not (s.flags & (FLAG_ISC_INVALID | FLAG_TIME_UNSYNCED))


def daily_results(device: Device, samples: Sequence[Sample], tz: str = "Europe/London",
                  max_gap_s: float = 300.0) -> list[DailyResult]:
    zone = ZoneInfo(tz)
    k = device.factor
    days: dict[dt.date, list[Sample]] = {}
    for s in samples:
        if usable(s):
            d = dt.datetime.fromtimestamp(s.epoch, zone).date()
            days.setdefault(d, []).append(s)

    out: list[DailyResult] = []
    for d in sorted(days):
        ss = days[d]
        g = [(s.epoch, s.isc_ma * k) for s in ss]
        insol, covered = pv_model.integrate(g, max_gap_s)
        pv, _ = pv_model.energy_kwh_per_kwp(((s.epoch, s.isc_ma * k, s.tamb, s.tcell) for s in ss),
                                             max_gap_s=max_gap_s)
        flat, _ = pv_model.integrate(
            [(s.epoch, thermal_model.useful_heat_w_m2(s.isc_ma * k, s.tamb, c=thermal_model.FLAT_PLATE))
             for s in ss], max_gap_s)
        tube, _ = pv_model.integrate(
            [(s.epoch, thermal_model.useful_heat_w_m2(s.isc_ma * k, s.tamb, c=thermal_model.EVACUATED_TUBE))
             for s in ss], max_gap_s)

        start = int(dt.datetime.combine(d, dt.time(), zone).timestamp())
        end = int(dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), zone).timestamp())
        if device.lat is not None and device.lon is not None:
            sun_up = daylight_seconds(start, end, device.lat, device.lon)
        else:
            sun_up = 12 * 3600
        coverage = min(1.0, covered / sun_up) if sun_up else 0.0
        tambs = [s.tamb for s in ss if s.tamb is not None]
        out.append(DailyResult(
            date=d.isoformat(),
            samples=len(ss),
            coverage=round(coverage, 3),
            peak_irradiance=round(max(v for _, v in g), 1),
            insolation_kwh_m2=round(insol / 1000.0, 4),
            pv_kwh_per_kwp=round(pv, 4),
            thermal_flat_kwh_m2=round(flat / 1000.0, 4),
            thermal_tube_kwh_m2=round(tube / 1000.0, 4),
            tamb_mean=round(sum(tambs) / len(tambs), 2) if tambs else None,
            vbat_min=min(s.vbat_v for s in ss),
        ))
    return out
