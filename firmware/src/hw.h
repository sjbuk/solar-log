// Hardware access: sensor rail, reference cell Isc, temperatures, battery, charger, RTC.
#pragma once
#include <Arduino.h>

struct IscReading {
  float mA = NAN;
  bool valid = false;
};

struct TempReading {
  float cellC = NAN;
  float ambC = NAN;
  bool cellValid = false;
  bool ambValid = false;
};

namespace hw {

void initPins();               // safe defaults after any wake
void railOn();                 // power sensors + start I2C
void railOff();                // stop buses, float pins, power sensors down

IscReading readIsc();          // momentary short of the reference cell
TempReading readTemps(bool swapProbes);
uint16_t readVbatMv();
bool chargerActive();          // CN3791 CHRG asserted

void setChargeEnable(bool on); // applies level and holds it through deep sleep

// DS3231. now() returns 0 if the RTC is not running/valid.
bool rtcBegin();
uint32_t rtcNow();
bool rtcLostPower();
void rtcSet(uint32_t epoch);

bool buttonPressed();

}  // namespace hw
