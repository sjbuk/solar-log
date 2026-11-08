// Original ESP32 DevKitC / NodeMCU-32S (ESP32-WROOM-32), low-power modified.
#pragma once

#define PIN_SDA 21
#define PIN_SCL 22
#define PIN_ONEWIRE 4
#define PIN_RAIL_EN 25        // LOW = sensor rail on (P-MOSFET), 10k pull-up
#define PIN_SHORT 26          // HIGH = reference cell shorted through shunt, 100k pull-down
#define PIN_CHG_EN 27         // HIGH = charging allowed, 100k pull-down, held in deep sleep
#define PIN_CHG_STAT 34       // LOW = charging (CN3791 CHRG), external pull-up
#define PIN_VBAT 35           // ADC1, 1M/1M divider
#define PIN_BUTTON 33         // LOW = pressed, external pull-up, ext0 wake
#define BUTTON_WAKE_EXT0 1
