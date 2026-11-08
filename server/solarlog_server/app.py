"""FastAPI application: device upload API, data/analysis API and dashboard.

Configuration (environment):
  SOLARLOG_DB              SQLite path (default ./solarlog.db)
  SOLARLOG_DEVICE_TOKENS   comma-separated device_id:token pairs (required for uploads)
  SOLARLOG_TZ              timezone for daily grouping (default Europe/London)
"""


import csv
import datetime as dt
import hmac
import io
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .analysis import calibration, reference
from .db import Database, Device
from .report import FLAG_TIME_UNSYNCED, daily_results

MAX_RECORDS_PER_UPLOAD = 500
PVGIS_CACHE_S = 30 * 86400


class Site(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tilt: float = Field(ge=0, le=90)
    azimuth: float = Field(ge=0, le=360)


# [seq, epoch, isc_0.1mA, tcell_0.01C|null, tamb_0.01C|null, vbat_mV, flags]
RecordRow = tuple[int, int, int, int | None, int | None, int, int]


class Upload(BaseModel):
    device: str = Field(min_length=1, max_length=64)
    fw: str | None = None
    rssi: int | None = None
    vbat_mV: int | None = None
    site: Site | None = None
    records: list[RecordRow] = Field(default_factory=list, max_length=MAX_RECORDS_PER_UPLOAD)


class CalibrationRequest(BaseModel):
    factor: float | None = Field(default=None, gt=0, description="W/m2 per mA; null resets to nominal")
    isc_stc_ma: float | None = Field(default=None, gt=0)
    auto: bool = False
    days: int = Field(default=30, ge=3, le=365)


def parse_tokens(spec: str) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        dev, sep, tok = part.partition(":")
        if not sep or not dev or not tok:
            raise ValueError(f"bad SOLARLOG_DEVICE_TOKENS entry: {part!r}")
        tokens[dev] = tok
    return tokens


def create_app(db_path: str | None = None, tokens: dict[str, str] | None = None,
               tz: str | None = None) -> FastAPI:
    db = Database(db_path or os.environ.get("SOLARLOG_DB", "solarlog.db"))
    device_tokens = tokens if tokens is not None else parse_tokens(os.environ.get("SOLARLOG_DEVICE_TOKENS", ""))
    timezone = tz or os.environ.get("SOLARLOG_TZ", "Europe/London")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    app = FastAPI(title="Solar-Log", version="0.1.0")
    app.state.db = db

    def get_device(device_id: str) -> Device:
        d = db.device(device_id)
        if d is None:
            raise HTTPException(404, "unknown device")
        return d

    # ------------------------------------------------------------------ device API
    @app.post("/api/v1/upload")
    def upload(body: Upload, authorization: Annotated[str | None, Header()] = None) -> dict:
        expected = device_tokens.get(body.device)
        given = (authorization or "").removeprefix("Bearer ").strip()
        if not expected or not hmac.compare_digest(expected.encode(), given.encode()):
            raise HTTPException(401, "bad device token")
        recs = sorted(body.records, key=lambda r: r[0])
        db.upsert_device(body.device, body.site.model_dump() if body.site else None, body.fw,
                         body.rssi, body.vbat_mV, int(time.time()))
        stored = db.insert_records(body.device, recs)
        last = recs[-1][0] if recs else db.last_seq(body.device)
        return {"last_seq": -1 if last is None else last, "stored": stored}

    # ------------------------------------------------------------------ data API
    @app.get("/api/v1/devices")
    def list_devices() -> list[dict]:
        return [asdict(d) | {"factor": d.factor} for d in db.devices()]

    def range_args(start: str | None, end: str | None) -> tuple[int | None, int | None]:
        """Accept unix seconds or ISO dates/datetimes (naive values are UTC)."""
        def conv(v: str | None) -> int | None:
            if v is None:
                return None
            if v.isdigit():
                return int(v)
            try:
                t = dt.datetime.fromisoformat(v)
            except ValueError as exc:
                raise HTTPException(422, f"bad time {v!r}") from exc
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return int(t.timestamp())
        return conv(start), conv(end)

    @app.get("/api/v1/devices/{device_id}/data")
    def data(device: Annotated[Device, Depends(get_device)], start: str | None = None,
             end: str | None = None) -> list[dict]:
        s, e = range_args(start, end)
        k = device.factor
        return [asdict(x) | {"irradiance": round(x.isc_ma * k, 1)} for x in db.samples(device.id, s, e)]

    @app.get("/api/v1/devices/{device_id}/data.csv", response_class=PlainTextResponse)
    def data_csv(device: Annotated[Device, Depends(get_device)], start: str | None = None,
                 end: str | None = None) -> PlainTextResponse:
        s, e = range_args(start, end)
        k = device.factor
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["seq", "utc", "isc_mA", "irradiance_Wm2", "tcell_C", "tamb_C", "vbat_V", "flags"])
        for x in db.samples(device.id, s, e):
            w.writerow([x.seq, dt.datetime.fromtimestamp(x.epoch, dt.timezone.utc).isoformat(),
                        x.isc_ma, round(x.isc_ma * k, 1), x.tcell, x.tamb, x.vbat_v, x.flags])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{device.id}.csv"'})

    @app.get("/api/v1/devices/{device_id}/daily")
    def daily(device: Annotated[Device, Depends(get_device)]) -> list[dict]:
        return [r.as_dict() for r in daily_results(device, db.samples(device.id), timezone)]

    def pvgis_for(device: Device) -> list[reference.PvgisMonth]:
        if device.lat is None or device.lon is None or device.tilt is None or device.azimuth is None:
            raise HTTPException(409, "device has not reported its site (lat/lon/tilt/azimuth)")
        url = reference.pvgis_url(device.lat, device.lon, device.tilt, device.azimuth)
        now = int(time.time())
        cached = db.cache_get(url, PVGIS_CACHE_S, now)
        if cached is None:
            try:
                months = reference.fetch_pvgis(device.lat, device.lon, device.tilt, device.azimuth)
            except Exception as exc:  # network/API failure
                raise HTTPException(502, f"PVGIS request failed: {exc}") from exc
            db.cache_put(url, json.dumps([asdict(m) for m in months]), now)
            return months
        return [reference.PvgisMonth(**m) for m in json.loads(cached)]

    @app.get("/api/v1/devices/{device_id}/summary")
    def summary(device: Annotated[Device, Depends(get_device)],
                with_reference: Annotated[bool, Query(alias="reference")] = True) -> dict:
        days = daily_results(device, db.samples(device.id), timezone)
        triples = [(dt.date.fromisoformat(d.date), d.pv_kwh_per_kwp, d.coverage) for d in days]
        pvgis = pvgis_for(device) if with_reference else []
        months, annual = reference.compare_months(triples, pvgis)
        good = [d for d in days if d.coverage >= 0.9]
        return {
            "device": device.id,
            "calibration": {"factor": device.factor, "source": device.cal_source or "nominal",
                            "isc_stc_ma": device.isc_stc_ma},
            "days_logged": len(days),
            "days_full_coverage": len(good),
            "mean_daily_kwh_per_kwp": round(sum(d.pv_kwh_per_kwp for d in good) / len(good), 3) if good else None,
            "months": [asdict(m) for m in months if m.days or m.pvgis_e_d is not None],
            "annual_estimate_kwh_per_kwp": round(annual, 1) if annual is not None else None,
            "pvgis_annual_kwh_per_kwp": round(sum(m.e_m for m in pvgis), 1) if pvgis else None,
        }

    @app.post("/api/v1/devices/{device_id}/calibration")
    def set_calibration(device: Annotated[Device, Depends(get_device)], req: CalibrationRequest) -> dict:
        if not req.auto:
            db.set_calibration(device.id, req.factor, "manual" if req.factor else None, req.isc_stc_ma)
            return {"factor": db.device(device.id).factor}
        if device.lat is None or device.tilt is None:
            raise HTTPException(409, "device has not reported its site")
        end = dt.date.today() - dt.timedelta(days=6)  # archive API lags ~5 days
        start = end - dt.timedelta(days=req.days)
        s = int(dt.datetime.combine(start, dt.time(), dt.timezone.utc).timestamp())
        e = int(dt.datetime.combine(end + dt.timedelta(days=1), dt.time(), dt.timezone.utc).timestamp())
        samples = [x for x in db.samples(device.id, s, e) if not x.flags & FLAG_TIME_UNSYNCED]
        means = calibration.hourly_means((x.epoch, x.isc_ma) for x in samples)
        try:
            gti = reference.fetch_open_meteo_gti(device.lat, device.lon, device.tilt, device.azimuth, start, end)
        except Exception as exc:
            raise HTTPException(502, f"Open-Meteo request failed: {exc}") from exc
        pairs = [(isc, gti[t]) for t, isc in means.items() if t in gti]
        k = calibration.fit_factor(pairs)
        if k is None:
            raise HTTPException(422, f"not enough sunny hours to calibrate ({len(pairs)} matched hours)")
        db.set_calibration(device.id, k, f"open-meteo {start}..{end}", req.isc_stc_ma)
        return {"factor": k, "hours": len(pairs)}

    # ------------------------------------------------------------------ dashboard
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {"devices": db.devices()})

    @app.get("/devices/{device_id}", response_class=HTMLResponse)
    def device_page(request: Request, device: Annotated[Device, Depends(get_device)]) -> HTMLResponse:
        return templates.TemplateResponse(request, "device.html", {"device": device})

    return app


def __getattr__(name: str):
    # Lazily build the env-configured app for `uvicorn solarlog_server.app:app`,
    # so importing this module (e.g. in tests) has no side effects.
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
