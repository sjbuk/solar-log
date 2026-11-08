# Wiring

For a perfboard build see [`hardware/prototype/`](../hardware/prototype/): schematic, placement guide
and a hole-by-hole net list generated from one script.

All grounds are common: ESP32 GND, battery −, cell −, CN3791 GND, sensor GND.

## Power path
| From | To | Notes |
|---|---|---|
| 18650 + (via holder, protected cell) | CN3791 BAT+ | |
| 18650 + | HT7833 VIN | Add 10 µF at VIN |
| HT7833 VOUT | ESP32 **3V3** pin | 470 µF low-ESR electrolytic + 100 nF at the 3V3 pin |
| 18650 + | 1 MΩ → GPIO35 → 1 MΩ → GND | 100 nF from GPIO35 to GND |
| ESP32 5V / VIN | *not connected* | Never connect USB and battery at the same time unless the mod jumper is set (see mod doc) |

## Sensor rail (switched 3V3)
| From | To |
|---|---|
| ESP32 3V3 | AO3401 (Q4) source |
| Q4 gate | GPIO25, and 10 kΩ to 3V3 |
| Q4 drain = **SENSOR_3V3** | INA219 VCC, DS3231 VCC, DS18B20 VDD (red), 4.7 kΩ 1-Wire pull-up |

## Signals
| Signal | ESP32 GPIO | Device pin |
|---|---|---|
| SDA | 21 | INA219 SDA, DS3231 SDA (module pull-ups go to SENSOR_3V3) |
| SCL | 22 | INA219 SCL, DS3231 SCL |
| 1-Wire | 4 | Both DS18B20 data (yellow), 4.7 kΩ to SENSOR_3V3 |
| SHORT | 26 | AO3400 (Q1) gate, 100 kΩ to GND |
| CHG_EN | 27 | AO3400 (Q3) gate, 100 kΩ to GND |
| CHG_STAT | 34 | CN3791 CHRG pin (open-drain) with 100 kΩ pull-up to 3V3 (GPIO34 has no internal pull-up). **Remove the module's CHRG LED** — it is fed from the panel voltage and would push ~4 V into GPIO34 |
| BUTTON | 33 | Push button to GND, 100 kΩ pull-up to 3V3 |

## Reference cell & charger
| From | To |
|---|---|
| Cell + | INA219 VIN+ ; SS14 anode |
| INA219 VIN− | Q1 drain |
| Q1 source | GND |
| SS14 cathode | Q2 (AO3401) source; 100 kΩ Q2 source → Q2 gate |
| Q2 gate | Q3 (AO3400) drain |
| Q3 source | GND |
| Q2 drain | CN3791 IN+ |
| Cell − | GND |

## DS18B20 placement
* **Cell probe**: stainless probe bonded to the back of the reference cell with thermal
  epoxy / thermal pad + aluminium tape.
* **Ambient probe**: in a small radiation shield (stack of white plastic plant-pot saucers)
  below the box, out of direct sun.
* The firmware cannot tell which probe is which; on boot it prints both ROM addresses and
  readings on serial. Warm the cell probe in your hand; if they are reversed set
  "swap probes" in the setup portal.
