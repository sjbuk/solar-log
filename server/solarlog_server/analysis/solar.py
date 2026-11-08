"""Solar position (NOAA solar calculator formulation). Same algorithm as the firmware
(firmware/lib/core/src/solar.cpp) plus azimuth and plane-of-array geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SunPosition:
    elevation: float  # degrees above horizon
    azimuth: float  # compass degrees, 0 = N, 90 = E, 180 = S


def sun_position(epoch: float, lat: float, lon: float) -> SunPosition:
    """Sun position for a UTC unix time. lon is east-positive."""
    days = epoch / 86400.0
    jd = days + 2440587.5
    hour_utc = (days - math.floor(days)) * 24.0
    t = (jd - 2451545.0) / 36525.0

    l0 = math.fmod(280.46646 + t * (36000.76983 + t * 0.0003032), 360.0)
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    rm = math.radians(m)
    c = (
        math.sin(rm) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * rm) * (0.019993 - 0.000101 * t)
        + math.sin(3 * rm) * 0.000289
    )
    omega = 125.04 - 1934.136 * t
    app_long = l0 + c - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long)))

    y = math.tan(math.radians(eps / 2)) ** 2
    rl0 = math.radians(l0)
    eq_time = 4.0 * math.degrees(
        y * math.sin(2 * rl0)
        - 2 * e * math.sin(rm)
        + 4 * e * y * math.sin(rm) * math.cos(2 * rl0)
        - 0.5 * y * y * math.sin(4 * rl0)
        - 1.25 * e * e * math.sin(2 * rm)
    )
    tst = math.fmod(hour_utc * 60.0 + eq_time + 4.0 * lon, 1440.0)
    if tst < 0:
        tst += 1440.0
    ha = math.radians(tst / 4.0 - 180.0)

    rlat = math.radians(lat)
    cos_zen = math.sin(rlat) * math.sin(decl) + math.cos(rlat) * math.cos(decl) * math.cos(ha)
    cos_zen = max(-1.0, min(1.0, cos_zen))
    zen = math.acos(cos_zen)

    denom = math.cos(rlat) * math.sin(zen)
    if abs(denom) < 1e-9:
        az = 180.0
    else:
        x = (math.sin(rlat) * cos_zen - math.sin(decl)) / denom
        az = math.degrees(math.acos(max(-1.0, min(1.0, x))))
        az = (az + 180.0) % 360.0 if ha > 0 else (540.0 - az) % 360.0
    return SunPosition(90.0 - math.degrees(zen), az)


def cos_incidence(sun: SunPosition, tilt: float, azimuth: float) -> float:
    """Cosine of the angle between the sun and a plane's normal (tilt from horizontal,
    azimuth in compass degrees). Negative means the sun is behind the plane."""
    zen = math.radians(90.0 - sun.elevation)
    b = math.radians(tilt)
    return math.cos(zen) * math.cos(b) + math.sin(zen) * math.sin(b) * math.cos(
        math.radians(sun.azimuth - azimuth)
    )


def daylight_seconds(day_start: int, day_end: int, lat: float, lon: float, step: int = 300) -> int:
    """Seconds between day_start and day_end with the sun above the horizon."""
    total = 0
    for t in range(day_start, day_end, step):
        if sun_position(t + step / 2, lat, lon).elevation > 0:
            total += step
    return total
