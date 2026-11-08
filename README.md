# Solar-Log

A low-cost (~£35), battery-powered logger that sits on a roof **before** you buy solar
panels. It measures how much sunlight the proposed panel position really receives
(including local shading from chimneys, trees and dormers), uploads the data once a day
over WiFi, and a small self-hosted web app turns it into an estimate of
**kWh per kWp** you could expect — compared against PVGIS for the same site.
A later phase will reuse the same data to estimate **solar hot-water** collector output.

```
 ┌──────── roof ────────┐        WiFi, 1×/day        ┌──── home PC / Raspberry Pi ────┐
 │ ref cell (tilt/azim.)│  ───────────────────────►  │ FastAPI + SQLite               │
 │ ESP32 + INA219 + RTC │   JSON batch upload        │ calibration · PV model · PVGIS │
 │ 18650 + solar charge │                            │ dashboard · CSV export         │
 └──────────────────────┘                            └────────────────────────────────┘
```

## How it works
* A 1 W mini panel is used as a **reference cell**. Its short-circuit current (Isc) is
  proportional to the irradiance on the plane of the array. Every minute in daylight the
  firmware shorts it through the INA219 shunt for ~5 ms to read Isc; the rest of the time
  the same cell charges the battery through a CN3791 MPPT charger.
* Two DS18B20 probes record cell and ambient temperature (PV derating, frost charge
  lock-out, and later the solar-thermal model).
* Readings are kept in a flash ring log (months of capacity) and uploaded daily.
* Battery-only runtime is ~4 months (requirement: ≥1 month); with charging it is
  effectively indefinite.

## Repository layout
| Path | Contents |
|---|---|
| [`docs/`](docs/) | Hardware design, wiring, ESP32 DevKit low-power mod, power budget, mounting, data format |
| [`hardware/bom.csv`](hardware/bom.csv) | Bill of materials (UK prices) |
| [`firmware/`](firmware/) | PlatformIO project (ESP32 DevKitC primary, XIAO ESP32-C3 alternative) |
| [`server/`](server/) | Python FastAPI server, analysis and dashboard |
| [`tools/simulate_device.py`](tools/simulate_device.py) | Synthetic device for testing the server without hardware |

## Quick start (server + simulator)
```bash
cd server && pip install -e '.[dev]'
```
```bash
SOLARLOG_DEVICE_TOKENS="sim-1:secret" uvicorn solarlog_server.app:app --port 8000
```
```bash
python tools/simulate_device.py --url http://localhost:8000 --device sim-1 --token secret --days 30
```
Then open http://localhost:8000/.

## Firmware
```bash
cd firmware && pio test -e native
```
```bash
cd firmware && pio run -e esp32dev -t upload
```
See [`docs/hardware.md`](docs/hardware.md) before powering anything from the battery —
the stock ESP32 DevKit **must** be modified for low sleep current
([`docs/esp32-devkit-mod.md`](docs/esp32-devkit-mod.md)).

## Status / milestones
1. ☑ Design docs, BOM, power budget
2. ☐ DevKitC low-power mod + sleep current measurement (go/no-go ≤ 40 µA)
3. ☐ Bench test sampling, RTC, deep sleep, local log
4. ☐ Bench test charging + lock-out
5. ☑ Server upload API, storage, simulator, charts (initial)
6. ☐ End-to-end on bench with real hardware
7. ☑ Analysis: calibration, PV model, PVGIS comparison (initial)
8. ☐ Roof field trial
9. ☐ Solar hot-water model (stub in place)
