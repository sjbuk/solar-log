// Wake scheduling: sample in daylight, sleep through the night, upload once a day.
#pragma once
#include <stdint.h>

namespace solarlog {

struct ScheduleConfig {
  double lat = 51.5;
  double lon = -0.12;
  uint32_t sampleIntervalS = 60;
  uint8_t uploadHourUtc = 21;      // daily upload time (UTC, avoids DST handling)
  double daylightThresholdDeg = -2.0;
};

// Start of the most recent upload slot at or before `now`.
uint32_t uploadSlotAtOrBefore(uint32_t now, uint8_t uploadHourUtc);

// True if an upload slot has passed since the last successful/attempted upload.
bool uploadDue(uint32_t now, uint32_t lastUploadEpoch, uint8_t uploadHourUtc);

bool isDaylight(const ScheduleConfig& c, uint32_t now);

// Seconds to sleep until the next thing to do (sample or upload). Always >= 1.
uint32_t secondsToNextWake(const ScheduleConfig& c, uint32_t now, uint32_t lastUploadEpoch);

}  // namespace solarlog
