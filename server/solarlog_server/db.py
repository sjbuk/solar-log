"""SQLite storage."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    lat REAL, lon REAL, tilt REAL, azimuth REAL,
    fw TEXT, last_rssi INTEGER, last_vbat_mv INTEGER, last_seen INTEGER,
    isc_stc_ma REAL NOT NULL DEFAULT 190.0,   -- nominal reference-cell Isc at 1000 W/m2
    cal_factor REAL,                          -- fitted/manual W/m2 per mA (NULL = nominal)
    cal_source TEXT
);
CREATE TABLE IF NOT EXISTS samples (
    device_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    epoch INTEGER NOT NULL,
    isc_raw INTEGER NOT NULL,     -- 0.1 mA
    tcell_raw INTEGER,            -- 0.01 degC
    tamb_raw INTEGER,
    vbat_mv INTEGER NOT NULL,
    flags INTEGER NOT NULL,
    PRIMARY KEY (device_id, seq)
);
CREATE INDEX IF NOT EXISTS samples_time ON samples (device_id, epoch);
CREATE TABLE IF NOT EXISTS reference_cache (
    key TEXT PRIMARY KEY,
    fetched INTEGER NOT NULL,
    body TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Device:
    id: str
    lat: float | None
    lon: float | None
    tilt: float | None
    azimuth: float | None
    fw: str | None
    last_rssi: int | None
    last_vbat_mv: int | None
    last_seen: int | None
    isc_stc_ma: float
    cal_factor: float | None
    cal_source: str | None

    @property
    def factor(self) -> float:
        """W/m2 per mA currently in use."""
        return self.cal_factor if self.cal_factor else 1000.0 / self.isc_stc_ma


@dataclass(frozen=True)
class Sample:
    seq: int
    epoch: int
    isc_ma: float
    tcell: float | None
    tamb: float | None
    vbat_v: float
    flags: int


class Database:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def upsert_device(self, device_id: str, site: dict | None, fw: str | None, rssi: int | None,
                      vbat_mv: int | None, seen: int) -> None:
        site = site or {}
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO devices (id, lat, lon, tilt, azimuth, fw, last_rssi, last_vbat_mv, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     lat=COALESCE(excluded.lat, lat), lon=COALESCE(excluded.lon, lon),
                     tilt=COALESCE(excluded.tilt, tilt), azimuth=COALESCE(excluded.azimuth, azimuth),
                     fw=excluded.fw, last_rssi=excluded.last_rssi,
                     last_vbat_mv=excluded.last_vbat_mv, last_seen=excluded.last_seen""",
                (device_id, site.get("lat"), site.get("lon"), site.get("tilt"), site.get("azimuth"),
                 fw, rssi, vbat_mv, seen),
            )

    def insert_records(self, device_id: str, records: Iterable[Sequence]) -> int:
        rows = [(device_id, *r) for r in records]
        with self._lock, self._conn:
            before = self._conn.total_changes
            self._conn.executemany(
                """INSERT OR IGNORE INTO samples
                   (device_id, seq, epoch, isc_raw, tcell_raw, tamb_raw, vbat_mv, flags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            return self._conn.total_changes - before

    def last_seq(self, device_id: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(seq) AS s FROM samples WHERE device_id = ?", (device_id,)
            ).fetchone()
        return row["s"]

    def devices(self) -> list[Device]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
        return [Device(**dict(r)) for r in rows]

    def device(self, device_id: str) -> Device | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return Device(**dict(r)) if r else None

    def set_calibration(self, device_id: str, factor: float | None, source: str | None,
                        isc_stc_ma: float | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE devices SET cal_factor = ?, cal_source = ? WHERE id = ?",
                (factor, source, device_id),
            )
            if isc_stc_ma:
                self._conn.execute(
                    "UPDATE devices SET isc_stc_ma = ? WHERE id = ?", (isc_stc_ma, device_id)
                )

    def samples(self, device_id: str, start: int | None = None, end: int | None = None) -> list[Sample]:
        q = "SELECT * FROM samples WHERE device_id = ?"
        args: list = [device_id]
        if start is not None:
            q += " AND epoch >= ?"
            args.append(start)
        if end is not None:
            q += " AND epoch < ?"
            args.append(end)
        q += " ORDER BY epoch, seq"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [
            Sample(
                seq=r["seq"],
                epoch=r["epoch"],
                isc_ma=r["isc_raw"] / 10.0,
                tcell=None if r["tcell_raw"] is None else r["tcell_raw"] / 100.0,
                tamb=None if r["tamb_raw"] is None else r["tamb_raw"] / 100.0,
                vbat_v=r["vbat_mv"] / 1000.0,
                flags=r["flags"],
            )
            for r in rows
        ]

    def cache_get(self, key: str, max_age_s: int, now: int) -> str | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM reference_cache WHERE key = ?", (key,)).fetchone()
        if r and now - r["fetched"] <= max_age_s:
            return r["body"]
        return None

    def cache_put(self, key: str, body: str, now: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO reference_cache (key, fetched, body) VALUES (?, ?, ?)",
                (key, now, body),
            )
