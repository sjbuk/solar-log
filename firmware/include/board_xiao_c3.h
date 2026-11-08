// Seeed XIAO ESP32-C3 alternative. Deep-sleep GPIO wake is only possible on GPIO0-5;
// ADC1 is GPIO0-4. Strapping pins 8/9 are left unused.
#pragma once

#define PIN_SDA 6             // D4
#define PIN_SCL 7             // D5
#define PIN_ONEWIRE 10        // D10
#define PIN_RAIL_EN 20        // D7 (UART RX, unused: console is USB-CDC)
#define PIN_SHORT 21          // D6 (UART TX)
#define PIN_CHG_EN 5          // D3, held in deep sleep
#define PIN_CHG_STAT 4        // D2
#define PIN_VBAT 3            // D1, ADC1
#define PIN_BUTTON 2          // D0, strapping pin: pulled up, do not hold during reset
#define BUTTON_WAKE_EXT0 0
