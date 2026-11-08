# Hardware design

## Requirements
* Cheap, easily available parts (UK: eBay/AliExpress/Amazon/The Pi Hut/RS).
* ≥ 1 month on battery with no recharge (charging from the reference cell is a bonus).
* Survives a UK roof: −10 °C … +60 °C inside the box, rain, condensation.
* WiFi upload once a day to a self-hosted server.

## Block diagram
```
                  ┌───────────── switched 3V3 sensor rail (GPIO25) ────────────┐
                  │                                                             │
 ref cell ──► INA219 (Isc) ──► AO3400 short switch (GPIO26)    DS3231 RTC   DS18B20 ×2
    │                                                            (CR2032)   (cell, ambient)
    └──► SS14 ──► charge switch (GPIO27) ──► CN3791 MPPT ──► 18650 ──► HT7833 ──► ESP32 3V3
                                                                │
                                                       Vbat divider ──► GPIO35 (ADC1)
```

## Why a reference cell?
The short-circuit current of a PV cell is almost exactly proportional to the irradiance
falling on it (temperature coefficient only ≈ +0.05 %/K). Mounted at the *same tilt and
azimuth as the proposed array*, at the array location, it measures exactly what matters —
plane-of-array irradiance including real shading. Lux sensors (BH1750, TSL2561) saturate in
full sun and have the wrong spectral response, so they are not used.

## Shared measure / charge circuit
```
cell+ ──┬──► INA219 VIN+ ─[0.1 Ω shunt]─ VIN− ──► AO3400 (Q1) drain
        │                                           Q1 source ──► GND (cell−)
        │                                           Q1 gate ◄── GPIO26, 100 k to GND
        │
        └──► SS14 ──► AO3401 (Q2) source           Q2 gate ── 100 k ── Q2 source
                       Q2 drain ──► CN3791 IN+      Q2 gate ──► AO3400 (Q3) drain
                                                    Q3 gate ◄── GPIO27, 100 k to GND
                                                    Q3 source ──► GND
CN3791 BAT+ ──► 18650+       CN3791 CHRG LED pin ──► GPIO34 (via 10 k, active low, see wiring.md)
```
* **Normal:** Q1 off. The cell feeds the charger through the Schottky; the CN3791 MPPT holds
  the cell near its maximum-power voltage.
* **Sample:** Q1 on for ~3–5 ms. The cell is shorted through the shunt (≈ 25 mV across
  shunt + Q1), the Schottky blocks the charger side, and the INA219 reads the full Isc.
  Isc settles in microseconds, so the reading is a true short-circuit value. Charging lost:
  ~5 ms per minute (< 0.01 %).
* **Charge enable:** Q2 is a high-side P-MOSFET; because the cell is at 5–7 V a 3.3 V GPIO
  cannot switch it directly, so Q3 level-shifts. GPIO27 **high = charging allowed**. The
  100 k pull-down makes the fail-safe state "charging disabled" (important: Li-ion must not
  be charged below 0 °C). The pin level is held through deep sleep (`gpio_hold_en`).
* **Lock-out rules** (firmware, with hysteresis): enable when 2 °C ≤ T ≤ 43 °C and
  Vbat < 4.10 V; disable when T < 0 °C, T > 45 °C, Vbat > 4.19 V or the temperature probe
  is unreadable. The CN3791 still does its own CC/CV termination at 4.2 V.
* Buy the **6 V version** of the CN3791 module (the MPPT set-point is fixed by a resistor
  divider; 9 V/12 V/18 V versions exist).

## Sensor rail
The INA219, DS3231 and DS18B20s are powered from a P-MOSFET (AO3401) switched by GPIO25
(gate pulled up to 3V3 with 10 k → off in deep sleep). They therefore draw nothing while the
ESP32 sleeps. Before switching the rail off the firmware sets I²C/1-Wire pins to plain
inputs so the sensors are not back-powered through their pull-ups.

The DS3231 keeps time from its CR2032 while the rail is off (~3 µA from the coin cell, not
from the 18650). **Remove the charging resistor (or diode) on the common "ZS-042" DS3231
module** — it tries to charge the coin cell, which is unsafe for a non-rechargeable CR2032.
Also remove its power LED.

## MCU: ESP32 DevKitC (primary) / XIAO ESP32-C3 (alternative)
The original ESP32 dev board is used because it is already owned. Stock boards draw
5–15 mA in deep sleep and **must** be modified — see [esp32-devkit-mod.md](esp32-devkit-mod.md).
If the modified board cannot reach ≤ 40 µA, use a FireBeetle ESP32, LOLIN D32 or Seeed
XIAO ESP32-C3 instead (the firmware has an `xiao_esp32c3` build).

## Pin map (ESP32 DevKitC)
| Function | GPIO | Notes |
|---|---|---|
| I²C SDA / SCL | 21 / 22 | INA219 (0x40), DS3231 (0x68) |
| 1-Wire | 4 | 4.7 k pull-up to sensor rail |
| Sensor rail enable | 25 | Low = on (P-MOSFET), 10 k pull-up |
| Isc short MOSFET gate | 26 | High = short, 100 k pull-down |
| Charger enable | 27 | High = charging allowed, 100 k pull-down, held in sleep |
| Charger status (CHRG) | 34 | Input only pin, active low |
| Vbat sense | 35 | 1 M / 1 M divider + 100 nF, ADC1 (ADC2 is unusable with WiFi) |
| Service button | 33 | To GND, internal/external pull-up, ext0 wake |

Strapping pins (0, 2, 5, 12, 15) are avoided. See [wiring.md](wiring.md) for the full
connection list and [`firmware/include/board_esp32dev.h`](../firmware/include/board_esp32dev.h).

## Reference cell choice
6 V, 1 W monocrystalline epoxy or PET mini panel, roughly 110 × 60 mm, Isc ≈ 170–200 mA at
1000 W/m². The INA219 is configured for the 16 V / 400 mA range (0.05 mA resolution),
giving headroom for cloud-edge irradiance up to ~2000 W/m². Prefer PET-laminated panels
(better UV life than epoxy). Avoid "solar garden light" cells: too small, poor stability.

## Bill of materials
See [`hardware/bom.csv`](../hardware/bom.csv). Approx. £35 of new parts.

## Related documents
* [wiring.md](wiring.md) – connection list
* [esp32-devkit-mod.md](esp32-devkit-mod.md) – mandatory low-power modification
* [power-budget.md](power-budget.md) – battery life calculation
* [mounting.md](mounting.md) – enclosure and roof installation
* [data-format.md](data-format.md) – on-device record and upload formats
