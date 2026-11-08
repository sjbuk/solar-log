"""External reference data: PVGIS (expected PV yield) and Open-Meteo (modelled
irradiance for calibration). Network access is isolated in the fetch_* functions; the
parse/compare functions are pure and unit-tested."""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "solarlog-server/0.1"


@dataclass(frozen=True)
class PvgisMonth:
    month: int
    e_d: float  # mean daily energy, kWh/kWp
    e_m: float  # monthly energy, kWh/kWp


def compass_to_south_zero(azimuth: float) -> float:
    """Compass (180 = S) -> PVGIS/Open-Meteo convention (0 = S, -90 = E, +90 = W)."""
    a = azimuth - 180.0
    while a > 180:
        a -= 360
    while a <= -180:
        a += 360
    return a


def _get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def pvgis_url(lat: float, lon: float, tilt: float, azimuth: float, loss: float = 14.0) -> str:
    q = {
        "lat": f"{lat:.5f}",
        "lon": f"{lon:.5f}",
        "peakpower": "1",
        "loss": f"{loss:g}",
        "angle": f"{tilt:g}",
        "aspect": f"{compass_to_south_zero(azimuth):g}",
        "outputformat": "json",
    }
    return f"{PVGIS_URL}?{urllib.parse.urlencode(q)}"


def parse_pvgis(data: Mapping) -> list[PvgisMonth]:
    rows = data["outputs"]["monthly"]["fixed"]
    return [PvgisMonth(int(r["month"]), float(r["E_d"]), float(r["E_m"])) for r in rows]


def fetch_pvgis(lat: float, lon: float, tilt: float, azimuth: float, loss: float = 14.0) -> list[PvgisMonth]:
    return parse_pvgis(_get_json(pvgis_url(lat, lon, tilt, azimuth, loss)))


def open_meteo_url(lat: float, lon: float, tilt: float, azimuth: float, start: dt.date, end: dt.date) -> str:
    q = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "global_tilted_irradiance",
        "tilt": f"{tilt:g}",
        "azimuth": f"{compass_to_south_zero(azimuth):g}",
        "timezone": "GMT",
    }
    return f"{OPEN_METEO_ARCHIVE_URL}?{urllib.parse.urlencode(q)}"


def parse_open_meteo(data: Mapping) -> dict[int, float]:
    """-> {hour-end epoch: GTI W/m2}. Times are GMT, values are preceding-hour means."""
    h = data["hourly"]
    out: dict[int, float] = {}
    for t, g in zip(h["time"], h["global_tilted_irradiance"]):
        if g is None:
            continue
        ts = dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc)
        out[int(ts.timestamp())] = float(g)
    return out


def fetch_open_meteo_gti(
    lat: float, lon: float, tilt: float, azimuth: float, start: dt.date, end: dt.date
) -> dict[int, float]:
    return parse_open_meteo(_get_json(open_meteo_url(lat, lon, tilt, azimuth, start, end)))


@dataclass(frozen=True)
class MonthComparison:
    month: int
    days: int  # days with sufficient coverage
    measured_e_d: float | None  # kWh/kWp/day
    pvgis_e_d: float | None
    site_factor: float | None  # measured / PVGIS


def compare_months(
    daily: Sequence[tuple[dt.date, float, float]],
    pvgis: Sequence[PvgisMonth],
    min_coverage: float = 0.9,
) -> tuple[list[MonthComparison], float | None]:
    """daily: (date, kWh/kWp, coverage 0..1). Returns per-month comparison and an annual
    kWh/kWp estimate = sum(PVGIS E_m * site factor), using the mean site factor for
    months without data. Annual is None if no month has data."""
    ref = {m.month: m for m in pvgis}
    by_month: dict[int, list[float]] = {}
    for d, e, cov in daily:
        if cov >= min_coverage:
            by_month.setdefault(d.month, []).append(e)
    rows: list[MonthComparison] = []
    factors: dict[int, float] = {}
    for m in range(1, 13):
        vals = by_month.get(m, [])
        meas = sum(vals) / len(vals) if vals else None
        p = ref.get(m)
        sf = meas / p.e_d if (meas is not None and p and p.e_d > 0) else None
        if sf is not None:
            factors[m] = sf
        rows.append(MonthComparison(m, len(vals), None if meas is None else round(meas, 3),
                                    p.e_d if p else None, None if sf is None else round(sf, 3)))
    if not factors or not ref:
        return rows, None
    mean_sf = sum(factors.values()) / len(factors)
    annual = sum(p.e_m * factors.get(p.month, mean_sf) for p in pvgis)
    return rows, annual
