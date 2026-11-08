# Prototype (perfboard) build

| File | Contents |
|---|---|
| `schematic.svg` | Full schematic, four blocks: power, reference cell / Isc / charging, sensor rail, ESP32 |
| `perfboard.svg` | Placement on a 70 × 90 mm perfboard (rows A–AA, columns 1–35) with connection lines per net |
| `netlist.json` | Every net with part, pin and hole position (e.g. `O27` = row O, column 27) |
| `gen_diagrams.py` | Generates all three; edit part positions in `PARTS` and re-run |

```bash
python hardware/prototype/gen_diagrams.py
```

Prototype uses through-hole substitutes: MCP1700-3302 (TO-92) for U2 with 1000 µF on 3V3,
IRLB8721 (TO-220) for Q1, 2N7000 for Q3, AO3401 on SOT-23 adapters for Q2/Q4, 1N5819 for D1.
The ESP32 (38-pin DevKitC header order), INA219 and DS3231 plug into female headers.
Check module header orders against your boards before soldering; a 30-pin ESP32 board
needs the ESP32 holes re-mapped.
