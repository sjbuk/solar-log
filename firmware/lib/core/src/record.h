// On-device measurement record. See docs/data-format.md.
#pragma once
#include <stddef.h>
#include <stdint.h>

namespace solarlog {

constexpr uint8_t RECORD_VERSION = 1;
constexpr size_t RECORD_SIZE = 16;
constexpr int16_t TEMP_INVALID = INT16_MIN;

enum RecordFlags : uint8_t {
  FLAG_CHARGING = 1 << 0,
  FLAG_CHARGE_LOCKOUT = 1 << 1,
  FLAG_TCELL_INVALID = 1 << 2,
  FLAG_TAMB_INVALID = 1 << 3,
  FLAG_ISC_INVALID = 1 << 4,
  FLAG_TIME_UNSYNCED = 1 << 5,
};

struct Record {
  uint32_t epoch = 0;     // Unix seconds UTC
  uint16_t isc = 0;       // 0.1 mA
  int16_t tcell = TEMP_INVALID;  // 0.01 degC
  int16_t tamb = TEMP_INVALID;   // 0.01 degC
  uint16_t vbat = 0;      // mV
  uint16_t seqLo = 0;     // low 16 bits of sequence number
  uint8_t flags = 0;
  uint8_t version = RECORD_VERSION;
};

void encodeRecord(const Record& r, uint8_t out[RECORD_SIZE]);
// Returns false if the version byte is unknown.
bool decodeRecord(const uint8_t in[RECORD_SIZE], Record& r);

// Unit conversions with clamping.
uint16_t iscFromMilliamps(float mA);
float iscToMilliamps(uint16_t raw);
int16_t tempFromCelsius(float c, bool valid);
float tempToCelsius(int16_t raw);

}  // namespace solarlog
