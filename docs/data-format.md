# Data formats

## On-device record (16 bytes, little-endian, version 1)
| Offset | Type | Field | Unit |
|---|---|---|---|
| 0 | uint32 | `epoch` | Unix seconds, UTC |
| 4 | uint16 | `isc` | 0.1 mA (0 … 6553.5 mA) |
| 6 | int16 | `tcell` | 0.01 °C (`INT16_MIN` = invalid) |
| 8 | int16 | `tamb` | 0.01 °C (`INT16_MIN` = invalid) |
| 10 | uint16 | `vbat` | mV |
| 12 | uint16 | `seq_lo` | low 16 bits of the record sequence number (consistency check) |
| 14 | uint8 | `flags` | bit 0 charging, 1 charge lock-out, 2 tcell invalid, 3 tamb invalid, 4 isc invalid, 5 time unsynced |
| 15 | uint8 | `version` | 1 |

Defined in [`firmware/lib/core/src/record.h`](../firmware/lib/core/src/record.h).

## Flash ring log (`/log.bin` on LittleFS)
32-byte header (`magic "SLG1"`, capacity, `head_seq` = sequence number of the oldest
un-acknowledged record, `count`) followed by `capacity` record slots. Record with sequence
number *s* lives in slot `s % capacity`. When full, the oldest record is overwritten.
Sequence numbers are 32-bit and never reset unless the log is formatted.

## Upload (`POST /api/v1/upload`)
Header `Authorization: Bearer <device token>`, JSON body:
```json
{
  "device": "solarlog-a1b2c3",
  "fw": "0.1.0",
  "rssi": -71,
  "vbat_mV": 3987,
  "site": {"lat": 51.50, "lon": -0.12, "tilt": 35, "azimuth": 180},
  "records": [[seq, epoch, isc_0.1mA, tcell_0.01C, tamb_0.01C, vbat_mV, flags], ...]
}
```
* `records` are in ascending `seq`, at most 200 per request (firmware sends 100).
* Invalid temperatures are sent as `null`.
* `azimuth` is compass degrees (180 = south).
* Response `200 {"last_seq": N, "stored": k}`; the device then discards records with
  `seq ≤ N`. Re-sending records is harmless (idempotent on device + seq).

## Server CSV export (`GET /api/v1/devices/{id}/data.csv`)
`seq,utc,isc_mA,irradiance_Wm2,tcell_C,tamb_C,vbat_V,flags`
