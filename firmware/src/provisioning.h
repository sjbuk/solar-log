// WiFi + device setup captive portal ("SolarLog-xxxxxx" access point).
#pragma once
#include "config.h"

// Blocks until the user saves the form or the timeout expires. Returns true if saved.
bool runSetupPortal(DeviceConfig& cfg, uint16_t timeoutS = 300);
