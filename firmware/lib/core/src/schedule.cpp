#include "schedule.h"

#include "solar.h"

namespace solarlog {

uint32_t uploadSlotAtOrBefore(uint32_t now, uint8_t uploadHourUtc) {
  const uint32_t day = now - (now % 86400u);
  const uint32_t slot = day + (uint32_t)uploadHourUtc * 3600u;
  return slot <= now ? slot : slot - 86400u;
}

bool uploadDue(uint32_t now, uint32_t lastUploadEpoch, uint8_t uploadHourUtc) {
  return lastUploadEpoch < uploadSlotAtOrBefore(now, uploadHourUtc);
}

bool isDaylight(const ScheduleConfig& c, uint32_t now) {
  return solarElevationDeg(now, c.lat, c.lon) > c.daylightThresholdDeg;
}

uint32_t secondsToNextWake(const ScheduleConfig& c, uint32_t now, uint32_t lastUploadEpoch) {
  uint32_t toSample;
  if (isDaylight(c, now)) {
    // Align to interval boundaries so samples land on whole minutes.
    toSample = c.sampleIntervalS - (now % c.sampleIntervalS);
  } else {
    toSample = secondsUntilElevationAbove(now, c.lat, c.lon, c.daylightThresholdDeg);
  }

  uint32_t toUpload;
  if (uploadDue(now, lastUploadEpoch, c.uploadHourUtc)) {
    toUpload = 1;
  } else {
    toUpload = uploadSlotAtOrBefore(now, c.uploadHourUtc) + 86400u - now;
  }

  uint32_t s = toSample < toUpload ? toSample : toUpload;
  return s == 0 ? 1 : s;
}

}  // namespace solarlog
