# Solar-Log server

FastAPI + SQLite server that receives daily uploads from the logger, turns reference-cell
current into irradiance, and estimates PV (and solar hot-water) yield.

## Run
```bash
pip install -e '.[dev]'
```
```bash
SOLARLOG_DEVICE_TOKENS="solarlog-abc123:change-me" uvicorn solarlog_server.app:app --host 0.0.0.0 --port 8000
```
or `docker compose up -d` (edit the token in `docker-compose.yml`).

| Variable | Default | Meaning |
|---|---|---|
| `SOLARLOG_DB` | `solarlog.db` | SQLite file |
| `SOLARLOG_DEVICE_TOKENS` | – | `device_id:token,...` accepted for uploads |
| `SOLARLOG_TZ` | `Europe/London` | timezone used to group samples into days |

## API
| Method & path | Purpose |
|---|---|
| `POST /api/v1/upload` | Device upload (see `docs/data-format.md`) |
| `GET /api/v1/devices` | Devices, site, battery, RSSI, calibration |
| `GET /api/v1/devices/{id}/data[.csv]?start&end` | Samples (start/end: unix seconds or ISO dates, UTC) |
| `GET /api/v1/devices/{id}/daily` | Per-day insolation, kWh/kWp, solar-thermal kWh/m², coverage |
| `GET /api/v1/devices/{id}/summary[?reference=false]` | Monthly comparison with PVGIS, annual estimate |
| `POST /api/v1/devices/{id}/calibration` | `{"factor": 5.3}` manual, `{"isc_stc_ma": 200}` nominal, `{"auto": true, "days": 30}` fit vs Open-Meteo |
| `GET /`, `GET /devices/{id}` | Dashboard |

## How the estimate is made
1. **Irradiance** G = k · Isc. k defaults to 1000 / (cell Isc at STC, 190 mA); once a few
   weeks of data exist, run the auto calibration, which fits k against Open-Meteo modelled
   tilted irradiance using the low quartile of GTI/Isc (unshaded, clear hours).
2. **PV power** per kWp = G/1000 · (1 − 0.4 %/K · (T_mod − 25)) · 0.86, with T_mod from the
   NOCT model on ambient temperature. Integrated per local day; gaps > 5 min are not
   bridged and reported as reduced `coverage`.
3. **Site factor** per month = measured kWh/kWp/day ÷ PVGIS (same tilt/azimuth, 14 % loss,
   no local shading). The annual estimate scales PVGIS monthly totals by those factors
   (mean factor for months without data). PVGIS responses are cached for 30 days.
4. **Solar hot water** (initial): EN ISO 9806 quadratic efficiency model for typical flat
   plate and evacuated-tube collectors at 50 °C mean fluid temperature.

## Tests
```bash
python -m pytest
```
