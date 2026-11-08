// Li-ion charge lock-out policy (with hysteresis). See docs/hardware.md.
#pragma once
#include <stdint.h>

namespace solarlog {

struct ChargePolicy {
  float enableMinC = 2.0f;     // enable only at/above this temperature
  float enableMaxC = 43.0f;
  float disableMinC = 0.0f;    // disable below this
  float disableMaxC = 45.0f;   // disable above this
  uint16_t enableBelowMv = 4100;
  uint16_t disableAboveMv = 4190;
};

// Decide whether the charger input should be enabled.
// tempValid=false always disables (fail-safe).
bool chargeAllowed(const ChargePolicy& p, bool currentlyEnabled, bool tempValid, float tempC,
                   uint16_t vbatMv);

}  // namespace solarlog
