# ESP32 DevKitC / NodeMCU-32S low-power modification

## Why
The ESP32 chip itself uses ~10 µA in deep sleep, but typical dev boards add:

| Component | Typical drain |
|---|---|
| AMS1117-3.3 regulator quiescent current | 5–10 mA |
| Power LED | 1–3 mA |
| USB-UART (CP2102 / CH340) on the 3V3 rail, USB unplugged | 0.1–2 mA |

At ~10 mA a 3000 mAh battery lasts ~12 days — below the 1-month requirement. After the
mod the target is **≤ 40 µA** in deep sleep.

## Steps
1. **Measure first.** Flash a sleep-test build (add `-DSOLARLOG_SLEEP_TEST` to
   `build_flags`), which sets all pins to their safe state and goes straight to deep
   sleep. Put a multimeter in the µA/mA range in series with the battery. Note the reading.
2. **Remove the power LED** (or its series resistor) with a soldering iron.
3. **Bypass the AMS1117**: power the board through the **3V3 pin** from an HT7833
   (or MCP1700-3302 if you add ≥ 1000 µF, since it is only rated 250 mA) fed from the
   battery. Leave 5V/VIN unconnected. Fit 470 µF + 100 nF right at the 3V3 pin to cover
   WiFi TX peaks (~350 mA for a few ms).
4. **Check AMS1117 back-feed.** With 3.3 V on its output and nothing on its input some
   AMS1117s leak a few hundred µA. If the reading is still high, lift the AMS1117 output
   pin (or remove the regulator — but then USB alone no longer powers the board).
5. **USB-UART chip.** If still > 40 µA, cut the trace feeding the CP2102/CH340 VDD from
   3V3 and bridge it with a 2-pin jumper. Close the jumper only for flashing/serial debug.
6. **Re-measure.** Expected: ESP32 ~10 µA + HT7833 ~4 µA + Vbat divider ~2 µA + residual
   board leakage → 20–40 µA.

## Flashing after the mod
* Remove the battery (or open its switch), close the USB-UART jumper, plug in USB.
  If you removed the AMS1117 you must power 3V3 from a bench supply / the battery while
  flashing — **never connect USB 5 V and the battery together** if any path from 5 V to the
  battery could exist through the modified regulator.
* Easiest: keep the AMS1117 in place, only lift its **output** pin and add a small jumper
  from that pin to 3V3 that you close only while on USB with the battery disconnected.

## Go / no-go
If you cannot get below ~40 µA, buy a board designed for battery use — FireBeetle ESP32
(~10 µA), LOLIN D32 or Seeed XIAO ESP32-C3 (~44 µA). The firmware supports the XIAO C3
directly (`pio run -e xiao_esp32c3`).
