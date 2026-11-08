// Board selection. Pin maps documented in docs/hardware.md.
#pragma once

#if defined(SOLARLOG_BOARD_ESP32DEV)
#include "board_esp32dev.h"
#elif defined(SOLARLOG_BOARD_XIAO_C3)
#include "board_xiao_c3.h"
#else
#error "Define SOLARLOG_BOARD_ESP32DEV or SOLARLOG_BOARD_XIAO_C3 (see platformio.ini)"
#endif

// Common electrical constants
#define VBAT_DIVIDER_RATIO 2.0f  // 1M / 1M
#define INA219_ADDR 0x40
#define SHORT_SETTLE_US 600      // after closing the short before first conversion
#define INA219_CONV_US 600       // 12-bit conversion is 532 us
#define ISC_READS 4
#define SHORT_MAX_BUS_V 0.25f    // cell voltage above this while shorted => short failed
