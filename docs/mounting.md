# Enclosure and roof mounting

## Enclosure
* IP65 ABS junction box ~100 × 100 × 70 mm, **white or light grey** to limit heating.
* Reference cell bonded flush on the lid with outdoor silicone; cell leads through a
  drilled hole sealed with silicone.
* Two M12 cable glands: ambient probe lead, spare (later hot-water probes).
* Breather vent plug (Gore-type, ~£1) or a small drip hole at the lowest point, plus a
  silica-gel sachet — condensation is the main killer of roof electronics.
* Battery in a holder with a strap; keep the 18650 away from the lid (hottest part).
* The ESP32 antenna end should be near a side wall, away from the battery and any metal.

## Orientation
The cell must be at the **same tilt and azimuth as the planned panels**:
1. Measure the roof pitch with a phone inclinometer app on a rafter/tile batten (loft) or
   on the tiles.
2. Measure the roof azimuth with a phone compass along the fall line (compass degrees,
   180 = due south). Correct for magnetic declination (≈ 0 to −2° in the UK in 2026; small).
3. Enter tilt and azimuth in the setup portal — the server uses them for PVGIS and
   Open-Meteo comparison.

Either mount the box flat on the tiles (tilt = roof pitch automatically) or on an
adjustable aluminium-angle bracket.

## Location
* Put it where the panels would go, ideally at the **most shaded corner** (e.g. the one
  nearest a chimney) — the result is then conservative. Several units can be used to map
  shading across a roof.
* Keep it clear of the ridge vent and anything that shades it that would not shade panels.

## Fixing (non-penetrating)
* Stainless strap or wire hooked under a tile lip / round a slate hook, or
* Bonded to an existing satellite-dish bracket, or
* On a flat roof: weighted base (paving slab) with the bracket.
Do not drill tiles. Use a safety line and roof ladder — or mount from the loft via a
loose tile only if competent to do so.

## WiFi check before installation
Stand at the location (or hold the device out of a skylight) and run the setup portal's
"test upload" (button short-press). The upload log shows RSSI; aim for better than
−80 dBm. If weaker, add a WiFi extender in the loft.

## Solar hot water (later)
The same box position works. For collector modelling only irradiance and ambient
temperature are required; an optional extra DS18B20 can be added on the 1-Wire bus later
(e.g. on an existing cylinder) without hardware changes.
