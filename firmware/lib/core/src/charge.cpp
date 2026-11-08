#include "charge.h"

namespace solarlog {

bool chargeAllowed(const ChargePolicy& p, bool currentlyEnabled, bool tempValid, float tempC,
                   uint16_t vbatMv) {
  if (!tempValid) return false;
  if (currentlyEnabled) {
    return tempC >= p.disableMinC && tempC <= p.disableMaxC && vbatMv <= p.disableAboveMv;
  }
  return tempC >= p.enableMinC && tempC <= p.enableMaxC && vbatMv < p.enableBelowMv;
}

}  // namespace solarlog
