# Solar-Log firmware

PlatformIO / Arduino-ESP32. Environments: `esp32dev` (original ESP32 DevKitC, primary),
`xiao_esp32c3` (alternative), `native` (unit tests).

| Path | Contents |
|---|---|
| `lib/core/` | Hardware-independent logic: record format, flash ring log, solar position, wake scheduling, charge lock-out policy, upload JSON |
| `src/hw.*` | Sensor rail, INA219 Isc short-pulse read, DS18B20, Vbat, charger enable/status, DS3231 |
| `src/fs_storage.h` | LittleFS backend for the ring log |
| `src/uploader.*` | WiFi + NTP + batched HTTP upload with server ack |
| `src/provisioning.*` | WiFiManager setup portal (`SolarLog-xxxxxx` AP) |
| `src/main.cpp` | Wake → sample → stage → flush → upload → deep sleep |
| `include/board_*.h` | Pin maps |

## Use
* Hold the button ≥ 3 s on power-up (or from sleep) → setup portal: WiFi, server URL,
  token, lat/lon, tilt, azimuth. A short press uploads immediately (WiFi/RSSI check).
* The serial log at cold boot shows firmware version, RTC state and both probe readings.
* `-DSOLARLOG_SLEEP_TEST` builds a pure deep-sleep image for the low-power mod check.

## Tests
```bash
pio test -e native
```
Without PlatformIO: `./test/run_host_tests.sh` (plain g++ with a small Unity shim).

> Status: core logic is unit-tested; the ESP32 application (`src/`) has not yet been
> compiled or run on hardware.
