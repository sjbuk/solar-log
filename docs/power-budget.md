# Power budget

Battery: 18650, 3000 mAh nominal; assume **2400 mAh usable** (cold weather, protection
cut-off at ~3.0 V, ageing). Requirement: ≥ 1 month without any charging.

## Estimates (modified ESP32 DevKitC)
| State | Current | Duty | 24 h average |
|---|---|---|---|
| Deep sleep: ESP32 + HT7833 + Vbat divider (sensors unpowered) | 30–40 µA | ~100 % | **35 µA** |
| Sample wake: boot + Isc read (temps every 5th wake, 9-bit, light-sleep during conversion) | ~30 mA for ~80 ms | 1 per 60 s, daylight only (UK annual mean ≈ 12 h) | **20 µA** |
| Flash flush (every ~30 samples) | ~40 mA for ~30 ms | | < 1 µA |
| Daily WiFi upload + NTP | ~130 mA for ~6 s | 1 per day | **9 µA** |
| **Total** | | | **≈ 65 µA ≈ 1.6 mAh/day** |

**Battery only:** 2400 mAh / 1.6 mAh/day ≈ **1500 days theoretical**; Li-ion self-discharge
(~2–3 %/month) and protection-board drain (~3–8 µA) dominate long before that.
Even if every figure above is 3× worse (≈ 5 mAh/day) the battery lasts > 15 months.
The real number will be measured in milestones 2 and 8.

**Charging:** the 1 W reference cell delivers roughly 20 mAh/day on a dull December day and
>300 mAh/day in summer, comfortably above consumption.

**Unmodified DevKitC (~10 mA sleep):** ~240 mAh/day → **~10 days**. The low-power mod is
therefore mandatory.

## Firmware measures that keep the budget
* No WiFi on sample wakes; WiFi only for the daily upload, hard 20 s timeout.
* No sampling at night: the firmware computes the solar elevation and sleeps until shortly
  before sunrise.
* Records staged in RTC memory and written to flash in batches.
* Temperatures read every 5th sample, DS18B20 at 9-bit (~94 ms conversion) during light sleep.
* CPU at 80 MHz, quiet logging, bootloader image validation skipped on deep-sleep wake.
* Sensor rail fully switched off in sleep.

## How to measure
* Deep sleep: multimeter on µA range in series with the battery (short the meter while
  the board boots so the burden voltage does not brown it out, then open the short).
* Average: Nordic PPK2 (best), or log Vbat over a week with charging disabled and compare
  with the 18650 discharge curve.
