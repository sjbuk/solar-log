#include "record.h"

#include <math.h>

namespace solarlog {

static void put16(uint8_t* p, uint16_t v) {
  p[0] = v & 0xFF;
  p[1] = (v >> 8) & 0xFF;
}
static void put32(uint8_t* p, uint32_t v) {
  for (int i = 0; i < 4; ++i) p[i] = (v >> (8 * i)) & 0xFF;
}
static uint16_t get16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t get32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

void encodeRecord(const Record& r, uint8_t out[RECORD_SIZE]) {
  put32(out + 0, r.epoch);
  put16(out + 4, r.isc);
  put16(out + 6, (uint16_t)r.tcell);
  put16(out + 8, (uint16_t)r.tamb);
  put16(out + 10, r.vbat);
  put16(out + 12, r.seqLo);
  out[14] = r.flags;
  out[15] = r.version;
}

bool decodeRecord(const uint8_t in[RECORD_SIZE], Record& r) {
  if (in[15] != RECORD_VERSION) return false;
  r.epoch = get32(in + 0);
  r.isc = get16(in + 4);
  r.tcell = (int16_t)get16(in + 6);
  r.tamb = (int16_t)get16(in + 8);
  r.vbat = get16(in + 10);
  r.seqLo = get16(in + 12);
  r.flags = in[14];
  r.version = in[15];
  return true;
}

uint16_t iscFromMilliamps(float mA) {
  if (!(mA > 0.0f)) return 0;  // also catches NaN
  float raw = roundf(mA * 10.0f);
  if (raw > 65535.0f) return 65535;
  return (uint16_t)raw;
}

float iscToMilliamps(uint16_t raw) { return raw / 10.0f; }

int16_t tempFromCelsius(float c, bool valid) {
  if (!valid || isnan(c)) return TEMP_INVALID;
  float raw = roundf(c * 100.0f);
  if (raw > 32767.0f) raw = 32767.0f;
  if (raw < -32767.0f) raw = -32767.0f;
  return (int16_t)raw;
}

float tempToCelsius(int16_t raw) { return raw == TEMP_INVALID ? NAN : raw / 100.0f; }

}  // namespace solarlog
