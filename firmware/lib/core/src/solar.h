// Solar position (NOAA approximation, ~0.1 deg accuracy — ample for scheduling).
#pragma once
#include <stdint.h>

namespace solarlog {

// Solar elevation in degrees above the horizon for a UTC unix time.
// lonDeg: east positive (UK is negative west of Greenwich).
double solarElevationDeg(uint32_t epoch, double latDeg, double lonDeg);

// Seconds from `epoch` until the sun first rises above `thresholdDeg`, searched
// in `stepS` steps up to `maxS`. Returns 0 if already above, maxS if not found.
uint32_t secondsUntilElevationAbove(uint32_t epoch, double latDeg, double lonDeg,
                                    double thresholdDeg, uint32_t stepS = 300,
                                    uint32_t maxS = 2 * 86400);

}  // namespace solarlog
