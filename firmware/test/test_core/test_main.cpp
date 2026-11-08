// Native unit tests for hardware-independent firmware logic: `pio test -e native`
#include <math.h>
#include <string.h>
#include <unity.h>

#include <vector>

#include "charge.h"
#include "record.h"
#include "ringlog.h"
#include "schedule.h"
#include "solar.h"
#include "upload_json.h"

using namespace solarlog;

class MemStorage : public Storage {
 public:
  explicit MemStorage(size_t size) : data(size, 0xFF) {}
  bool read(uint32_t off, void* buf, size_t len) override {
    if (off + len > data.size()) return false;
    memcpy(buf, &data[off], len);
    return true;
  }
  bool write(uint32_t off, const void* buf, size_t len) override {
    if (off + len > data.size()) return false;
    memcpy(&data[off], buf, len);
    return true;
  }
  std::vector<uint8_t> data;
};

void setUp() {}
void tearDown() {}

// ---------------------------------------------------------------- record
void test_record_roundtrip() {
  Record r;
  r.epoch = 1767225600u;
  r.isc = iscFromMilliamps(187.34f);
  r.tcell = tempFromCelsius(-5.25f, true);
  r.tamb = tempFromCelsius(0, false);
  r.vbat = 3987;
  r.seqLo = 0xBEEF;
  r.flags = FLAG_CHARGING | FLAG_TAMB_INVALID;
  uint8_t buf[RECORD_SIZE];
  encodeRecord(r, buf);
  TEST_ASSERT_EQUAL_UINT8(0x00, buf[0]);  // little-endian epoch low byte
  TEST_ASSERT_EQUAL_UINT8(RECORD_VERSION, buf[15]);
  Record d;
  TEST_ASSERT_TRUE(decodeRecord(buf, d));
  TEST_ASSERT_EQUAL_UINT32(r.epoch, d.epoch);
  TEST_ASSERT_EQUAL_UINT16(1873, d.isc);
  TEST_ASSERT_EQUAL_INT16(-525, d.tcell);
  TEST_ASSERT_EQUAL_INT16(TEMP_INVALID, d.tamb);
  TEST_ASSERT_EQUAL_UINT16(3987, d.vbat);
  TEST_ASSERT_EQUAL_UINT16(0xBEEF, d.seqLo);
  TEST_ASSERT_EQUAL_UINT8(r.flags, d.flags);
  buf[15] = 99;
  TEST_ASSERT_FALSE(decodeRecord(buf, d));
}

void test_conversions_clamp() {
  TEST_ASSERT_EQUAL_UINT16(0, iscFromMilliamps(-3.0f));
  TEST_ASSERT_EQUAL_UINT16(0, iscFromMilliamps(NAN));
  TEST_ASSERT_EQUAL_UINT16(65535, iscFromMilliamps(1e6f));
  TEST_ASSERT_EQUAL_INT16(TEMP_INVALID, tempFromCelsius(NAN, true));
  TEST_ASSERT_EQUAL_INT16(32767, tempFromCelsius(500.0f, true));
  TEST_ASSERT_TRUE(isnan(tempToCelsius(TEMP_INVALID)));
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 21.5f, tempToCelsius(2150));
}

// ---------------------------------------------------------------- ring log
static Record mk(uint32_t epoch) {
  Record r;
  r.epoch = epoch;
  r.isc = (uint16_t)epoch;
  return r;
}

void test_ringlog_append_peek_ack() {
  MemStorage st(RingLog::storageBytes(8));
  RingLog log(st);
  TEST_ASSERT_FALSE(log.begin(8));  // fresh -> formatted
  for (uint32_t i = 0; i < 5; ++i) log.append(mk(100 + i));
  TEST_ASSERT_EQUAL_UINT32(5, log.count());
  TEST_ASSERT_EQUAL_UINT32(0, log.headSeq());
  Record r;
  uint32_t seq;
  TEST_ASSERT_TRUE(log.peek(2, r, &seq));
  TEST_ASSERT_EQUAL_UINT32(2, seq);
  TEST_ASSERT_EQUAL_UINT32(102, r.epoch);
  log.ack(2);
  TEST_ASSERT_EQUAL_UINT32(2, log.count());
  TEST_ASSERT_EQUAL_UINT32(3, log.headSeq());
  TEST_ASSERT_TRUE(log.peek(0, r, &seq));
  TEST_ASSERT_EQUAL_UINT32(3, seq);
  log.ack(1);  // stale ack is a no-op
  TEST_ASSERT_EQUAL_UINT32(2, log.count());
  log.ack(1000);  // over-ack clamps
  TEST_ASSERT_EQUAL_UINT32(0, log.count());
  TEST_ASSERT_EQUAL_UINT32(5, log.nextSeq());
}

void test_ringlog_overflow_and_reload() {
  MemStorage st(RingLog::storageBytes(4));
  {
    RingLog log(st);
    log.begin(4);
    for (uint32_t i = 0; i < 10; ++i) log.append(mk(i));
    TEST_ASSERT_EQUAL_UINT32(4, log.count());
    TEST_ASSERT_EQUAL_UINT32(6, log.headSeq());
    TEST_ASSERT_EQUAL_UINT32(6, log.overwritten());
  }
  RingLog again(st);
  TEST_ASSERT_TRUE(again.begin(4));  // persisted header reloads
  TEST_ASSERT_EQUAL_UINT32(4, again.count());
  Record r;
  uint32_t seq;
  for (uint32_t i = 0; i < 4; ++i) {
    TEST_ASSERT_TRUE(again.peek(i, r, &seq));
    TEST_ASSERT_EQUAL_UINT32(6 + i, seq);
    TEST_ASSERT_EQUAL_UINT32(6 + i, r.epoch);
  }
  // Capacity change formats
  RingLog bigger(st);
  TEST_ASSERT_FALSE(bigger.begin(3));
  TEST_ASSERT_EQUAL_UINT32(0, bigger.count());
}

void test_ringlog_corrupt_header_formats() {
  MemStorage st(RingLog::storageBytes(4));
  RingLog log(st);
  log.begin(4);
  log.append(mk(1));
  st.data[12] ^= 0xFF;  // corrupt count
  RingLog again(st);
  TEST_ASSERT_FALSE(again.begin(4));
  TEST_ASSERT_EQUAL_UINT32(0, again.count());
}

// ---------------------------------------------------------------- solar
// Reference values from the NOAA solar calculator.
void test_solar_elevation_london_solstice_noon() {
  // 2026-06-21 12:00 UTC, London (51.5074 N, 0.1278 W): ~61.9 deg
  double el = solarElevationDeg(1782043200u, 51.5074, -0.1278);
  TEST_ASSERT_FLOAT_WITHIN(0.5, 61.9, el);
}

void test_solar_elevation_edinburgh_winter() {
  // 2026-12-21 12:00 UTC, Edinburgh (55.9533 N, 3.1883 W): ~10.4 deg
  double el = solarElevationDeg(1797854400u, 55.9533, -3.1883);
  TEST_ASSERT_FLOAT_WITHIN(0.5, 10.4, el);
  // Midnight is well below horizon
  TEST_ASSERT_TRUE(solarElevationDeg(1797811200u, 55.9533, -3.1883) < -50);
}

void test_seconds_until_sunrise() {
  // 2026-06-21 00:00 UTC London: sunrise ~03:43 UTC (elevation -0.83);
  // threshold -2 deg is crossed a little before (~03:33).
  uint32_t midnight = 1782000000u - (1782000000u % 86400u);
  uint32_t s = secondsUntilElevationAbove(midnight, 51.5074, -0.1278, -2.0);
  TEST_ASSERT_UINT32_WITHIN(20 * 60, 3 * 3600 + 30 * 60, s);
  TEST_ASSERT_EQUAL_UINT32(0, secondsUntilElevationAbove(1782043200u, 51.5, -0.13, -2.0));
}

// ---------------------------------------------------------------- charge
void test_charge_policy() {
  ChargePolicy p;
  TEST_ASSERT_FALSE(chargeAllowed(p, false, false, 20, 3700));  // invalid temp
  TEST_ASSERT_FALSE(chargeAllowed(p, true, false, 20, 3700));
  TEST_ASSERT_TRUE(chargeAllowed(p, false, true, 20, 3700));
  TEST_ASSERT_FALSE(chargeAllowed(p, false, true, 1.0f, 3700));  // below enable min
  TEST_ASSERT_TRUE(chargeAllowed(p, true, true, 1.0f, 3700));    // hysteresis keeps on
  TEST_ASSERT_FALSE(chargeAllowed(p, true, true, -0.5f, 3700));  // frost
  TEST_ASSERT_FALSE(chargeAllowed(p, false, true, 44.0f, 3700));
  TEST_ASSERT_TRUE(chargeAllowed(p, true, true, 44.0f, 3700));
  TEST_ASSERT_FALSE(chargeAllowed(p, true, true, 46.0f, 3700));
  TEST_ASSERT_FALSE(chargeAllowed(p, false, true, 20, 4150));  // full-ish, don't restart
  TEST_ASSERT_TRUE(chargeAllowed(p, true, true, 20, 4150));
  TEST_ASSERT_FALSE(chargeAllowed(p, true, true, 20, 4200));
}

// ---------------------------------------------------------------- schedule
void test_upload_slot() {
  const uint32_t day = 1782000000u - (1782000000u % 86400u);
  TEST_ASSERT_EQUAL_UINT32(day + 21 * 3600, uploadSlotAtOrBefore(day + 22 * 3600, 21));
  TEST_ASSERT_EQUAL_UINT32(day - 86400 + 21 * 3600, uploadSlotAtOrBefore(day + 3600, 21));
  TEST_ASSERT_TRUE(uploadDue(day + 21 * 3600, day - 3600, 21));
  TEST_ASSERT_FALSE(uploadDue(day + 21 * 3600 + 60, day + 21 * 3600 + 10, 21));
  TEST_ASSERT_TRUE(uploadDue(day + 3600, 0, 21));  // never uploaded
}

void test_next_wake() {
  ScheduleConfig c;
  c.lat = 51.5074;
  c.lon = -0.1278;
  const uint32_t noon = 1782043200u;  // daylight
  // Just uploaded, daylight -> next aligned minute.
  TEST_ASSERT_EQUAL_UINT32(60, secondsToNextWake(c, noon, noon));
  TEST_ASSERT_EQUAL_UINT32(45, secondsToNextWake(c, noon + 15, noon));
  // Upload overdue -> wake immediately.
  TEST_ASSERT_EQUAL_UINT32(1, secondsToNextWake(c, noon, 0));
  // Night (00:00 UTC), uploaded at 21:00 the previous day: sleep until near sunrise
  const uint32_t midnight = noon - 12 * 3600;
  uint32_t s = secondsToNextWake(c, midnight, midnight - 3 * 3600);
  TEST_ASSERT_TRUE(s > 3 * 3600 && s < 4 * 3600);
  // 2026-12-21 20:50 UTC (dark), last upload the previous evening:
  // the 21:00 upload slot comes before sunrise.
  const uint32_t decEvening = 1797811200u + 20 * 3600 + 50 * 60;
  const uint32_t lastUpload = decEvening - 86400 + 15 * 60;  // 21:05 the day before
  TEST_ASSERT_EQUAL_UINT32(10 * 60, secondsToNextWake(c, decEvening, lastUpload));
}

// ---------------------------------------------------------------- json
void test_record_json() {
  Record r;
  r.epoch = 1782043200u;
  r.isc = 1873;
  r.tcell = -525;
  r.tamb = TEMP_INVALID;
  r.vbat = 3987;
  r.flags = 9;
  char buf[96];
  size_t n = formatRecordJson(buf, sizeof(buf), 4000000000u, r);
  TEST_ASSERT_EQUAL_STRING("[4000000000,1782043200,1873,-525,null,3987,9]", buf);
  TEST_ASSERT_EQUAL_UINT32(strlen(buf), n);
  TEST_ASSERT_EQUAL_UINT32(0, formatRecordJson(buf, 10, 1, r));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_record_roundtrip);
  RUN_TEST(test_conversions_clamp);
  RUN_TEST(test_ringlog_append_peek_ack);
  RUN_TEST(test_ringlog_overflow_and_reload);
  RUN_TEST(test_ringlog_corrupt_header_formats);
  RUN_TEST(test_solar_elevation_london_solstice_noon);
  RUN_TEST(test_solar_elevation_edinburgh_winter);
  RUN_TEST(test_seconds_until_sunrise);
  RUN_TEST(test_charge_policy);
  RUN_TEST(test_upload_slot);
  RUN_TEST(test_next_wake);
  RUN_TEST(test_record_json);
  return UNITY_END();
}
