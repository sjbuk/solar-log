#include "solar.h"

#include <math.h>

namespace solarlog {

static constexpr double kPi = 3.14159265358979323846;
static inline double rad(double d) { return d * kPi / 180.0; }
static inline double deg(double r) { return r * 180.0 / kPi; }

double solarElevationDeg(uint32_t epoch, double latDeg, double lonDeg) {
  // NOAA solar calculator (spreadsheet) formulation based on Julian centuries.
  const double days = epoch / 86400.0;            // days since 1970-01-01
  const double jd = days + 2440587.5;             // Julian day
  // Day of year and hour (UTC).
  const double dayFrac = days - floor(days);
  const double hourUtc = dayFrac * 24.0;
  const double t = (jd - 2451545.0) / 36525.0;    // Julian centuries since J2000

  const double L0 = fmod(280.46646 + t * (36000.76983 + t * 0.0003032), 360.0);
  const double M = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const double e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const double C = sin(rad(M)) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
                   sin(rad(2 * M)) * (0.019993 - 0.000101 * t) + sin(rad(3 * M)) * 0.000289;
  const double trueLong = L0 + C;
  const double omega = 125.04 - 1934.136 * t;
  const double appLong = trueLong - 0.00569 - 0.00478 * sin(rad(omega));
  const double eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0;
  const double eps = eps0 + 0.00256 * cos(rad(omega));
  const double decl = deg(asin(sin(rad(eps)) * sin(rad(appLong))));

  const double y = tan(rad(eps / 2)) * tan(rad(eps / 2));
  const double eqTime = 4.0 * deg(y * sin(2 * rad(L0)) - 2 * e * sin(rad(M)) +
                                  4 * e * y * sin(rad(M)) * cos(2 * rad(L0)) -
                                  0.5 * y * y * sin(4 * rad(L0)) -
                                  1.25 * e * e * sin(2 * rad(M)));  // minutes

  double trueSolarTime = fmod(hourUtc * 60.0 + eqTime + 4.0 * lonDeg, 1440.0);
  if (trueSolarTime < 0) trueSolarTime += 1440.0;
  double hourAngle = trueSolarTime / 4.0 - 180.0;

  const double cosZen = sin(rad(latDeg)) * sin(rad(decl)) +
                        cos(rad(latDeg)) * cos(rad(decl)) * cos(rad(hourAngle));
  const double zen = deg(acos(fmax(-1.0, fmin(1.0, cosZen))));
  return 90.0 - zen;
}

uint32_t secondsUntilElevationAbove(uint32_t epoch, double latDeg, double lonDeg,
                                    double thresholdDeg, uint32_t stepS, uint32_t maxS) {
  if (solarElevationDeg(epoch, latDeg, lonDeg) > thresholdDeg) return 0;
  for (uint32_t dt = stepS; dt <= maxS; dt += stepS) {
    if (solarElevationDeg(epoch + dt, latDeg, lonDeg) > thresholdDeg) {
      // Back off one step so we wake slightly before the crossing (never return 0 here).
      return dt == stepS ? stepS : dt - stepS;
    }
  }
  return maxS;
}

}  // namespace solarlog
