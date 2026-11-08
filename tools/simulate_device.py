#!/usr/bin/env python3
"""Synthetic Solar-Log device: generates realistic-looking records and uploads them
exactly like the firmware does (see docs/data-format.md). For testing the server and
dashboard without hardware.

    python tools/simulate_device.py --url http://localhost:8000 --device sim-1 --token secret --days 30
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import random
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from solarlog_server.analysis.solar import cos_incidence, sun_position  # noqa: E402

ISC_STC_MA = 190.0
BATCH = 100


def clear_sky_poa(epoch: float, lat: float, lon: float, tilt: float, azimuth: float) -> float:
    """Very simple clear-sky plane-of-array irradiance (W/m2)."""
    sun = sun_position(epoch, lat, lon)
    if sun.elevation <= 0:
        return 0.0
    sin_el = math.sin(math.radians(sun.elevation))
    ghi = 1098.0 * sin_el * math.exp(-0.057 / sin_el)  # Haurwitz
    dhi = 0.15 * ghi
    dni = (ghi - dhi) / sin_el
    beam = dni * max(0.0, cos_incidence(sun, tilt, azimuth))
    diffuse = dhi * (1 + math.cos(math.radians(tilt))) / 2
    return beam + diffuse


def generate(start: int, days: int, lat: float, lon: float, tilt: float, azimuth: float,
             interval: int = 60, seed: int = 1, first_seq: int = 0) -> Iterator[list]:
    """Yield firmware-format record rows [seq, epoch, isc, tcell, tamb, vbat, flags]."""
    rng = random.Random(seed)
    seq = first_seq
    vbat = 3950.0
    for day in range(days):
        day_start = start + day * 86400
        # Daily weather: clear, mixed or overcast.
        kind = rng.choices(["clear", "mixed", "overcast"], [0.25, 0.45, 0.30])[0]
        cloud = 1.0
        doy = time.gmtime(day_start).tm_yday
        t_mean = 10.5 - 6.0 * math.cos(2 * math.pi * (doy - 20) / 365)  # UK-ish seasonal
        for t in range(day_start, day_start + 86400, interval):
            if sun_position(t, lat, lon).elevation <= -2:
                continue
            if kind == "clear":
                cloud = 0.97 + 0.03 * rng.random()
            elif kind == "mixed":
                cloud = min(1.1, max(0.2, cloud + rng.gauss(0, 0.12)))  # random walk, edge enhancement
            else:
                cloud = 0.15 + 0.1 * rng.random()
            g = clear_sky_poa(t, lat, lon, tilt, azimuth) * cloud
            hour = (t % 86400) / 3600
            tamb = t_mean + 4.0 * math.sin(math.pi * (hour - 9) / 12)
            tcell = tamb + g / 800 * 25
            vbat = min(4180.0, max(3600.0, vbat + (g / 1000) * 0.6 - 0.05))
            flags = 1 if g > 50 and vbat < 4170 else 0  # charging
            yield [seq, t, round(g / 1000 * ISC_STC_MA * 10), round(tcell * 100), round(tamb * 100),
                   round(vbat), flags]
            seq += 1


def http_poster(url: str, token: str) -> Callable[[dict], dict]:
    def post(body: dict) -> dict:
        req = urllib.request.Request(
            url.rstrip("/") + "/api/v1/upload",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    return post


def upload(rows: list[list], post: Callable[[dict], dict], device: str, site: dict) -> int:
    sent = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        res = post({"device": device, "fw": "sim", "rssi": -65, "vbat_mV": chunk[-1][5],
                    "site": site, "records": chunk})
        if res["last_seq"] != chunk[-1][0]:
            raise RuntimeError(f"unexpected ack {res}")
        sent += len(chunk)
    return sent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--device", default="sim-1")
    ap.add_argument("--token", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--start", help="first day YYYY-MM-DD (UTC); default: N days ago")
    ap.add_argument("--lat", type=float, default=51.5074)
    ap.add_argument("--lon", type=float, default=-0.1278)
    ap.add_argument("--tilt", type=float, default=35)
    ap.add_argument("--azimuth", type=float, default=180)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    if a.start:
        start = calendar.timegm(time.strptime(a.start, "%Y-%m-%d"))
    else:
        now = int(time.time())
        start = now - now % 86400 - a.days * 86400
    rows = list(generate(start, a.days, a.lat, a.lon, a.tilt, a.azimuth, seed=a.seed))
    site = {"lat": a.lat, "lon": a.lon, "tilt": a.tilt, "azimuth": a.azimuth}
    n = upload(rows, http_poster(a.url, a.token), a.device, site)
    print(f"uploaded {n} records for {a.device} ({a.days} days)")


if __name__ == "__main__":
    main()
