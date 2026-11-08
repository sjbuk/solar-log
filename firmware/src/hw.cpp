#include "hw.h"

#include <Adafruit_INA219.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <RTClib.h>
#include <Wire.h>
#include <driver/gpio.h>
#include <esp_sleep.h>

#include "board.h"

namespace {
Adafruit_INA219 ina(INA219_ADDR);
RTC_DS3231 rtc;
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature dallas(&oneWire);
bool railIsOn = false;
constexpr uint32_t MIN_VALID_EPOCH = 1735689600u;  // 2025-01-01
}  // namespace

namespace hw {

void initPins() {
  pinMode(PIN_RAIL_EN, OUTPUT);
  digitalWrite(PIN_RAIL_EN, HIGH);  // rail off
  pinMode(PIN_SHORT, OUTPUT);
  digitalWrite(PIN_SHORT, LOW);     // not shorted -> cell charges battery
  pinMode(PIN_CHG_STAT, INPUT);
  pinMode(PIN_BUTTON, INPUT);       // external pull-up
  analogSetPinAttenuation(PIN_VBAT, ADC_11db);
}

void railOn() {
  if (railIsOn) return;
  digitalWrite(PIN_RAIL_EN, LOW);
  delay(3);  // rail + module caps settle; DS3231 needs < 2 ms after VCC
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  railIsOn = true;
}

void railOff() {
  if (!railIsOn) return;
  Wire.end();
  // Float bus pins so sensors are not back-powered through their pull-ups.
  pinMode(PIN_SDA, INPUT);
  pinMode(PIN_SCL, INPUT);
  pinMode(PIN_ONEWIRE, INPUT);
  digitalWrite(PIN_RAIL_EN, HIGH);
  railIsOn = false;
}

IscReading readIsc() {
  IscReading r;
  if (!ina.begin(&Wire)) return r;
  ina.setCalibration_16V_400mA();  // 0.05 mA resolution, 400 mA range
  digitalWrite(PIN_SHORT, HIGH);
  delayMicroseconds(SHORT_SETTLE_US + INA219_CONV_US);  // first full conversion while shorted
  float sum = 0;
  float busV = 0;
  for (int i = 0; i < ISC_READS; ++i) {
    sum += ina.getCurrent_mA();
    busV = ina.getBusVoltage_V();
    delayMicroseconds(INA219_CONV_US);
  }
  digitalWrite(PIN_SHORT, LOW);
  r.mA = sum / ISC_READS;
  if (r.mA < 0 && r.mA > -1.0f) r.mA = 0;  // offset noise in darkness
  r.valid = busV < SHORT_MAX_BUS_V && r.mA >= 0;
  return r;
}

TempReading readTemps(bool swapProbes) {
  TempReading t;
  dallas.begin();
  dallas.setResolution(9);  // 0.5 degC, ~94 ms conversion (scratchpad only, no EEPROM wear)
  dallas.setWaitForConversion(false);
  dallas.requestTemperatures();
  // Light-sleep during the conversion instead of busy waiting; GPIO levels are kept.
  esp_sleep_enable_timer_wakeup(100 * 1000);
  esp_light_sleep_start();
  float a = dallas.getTempCByIndex(0);
  float b = dallas.getTempCByIndex(1);
  if (swapProbes) std::swap(a, b);
  t.cellValid = a != DEVICE_DISCONNECTED_C && a != 85.0f;  // 85 = power-on reset value
  t.ambValid = b != DEVICE_DISCONNECTED_C && b != 85.0f;
  t.cellC = a;
  t.ambC = b;
  return t;
}

uint16_t readVbatMv() {
  uint32_t sum = 0;
  for (int i = 0; i < 8; ++i) sum += analogReadMilliVolts(PIN_VBAT);
  return (uint16_t)((sum / 8) * VBAT_DIVIDER_RATIO);
}

bool chargerActive() { return digitalRead(PIN_CHG_STAT) == LOW; }

void setChargeEnable(bool on) {
  gpio_hold_dis((gpio_num_t)PIN_CHG_EN);
  pinMode(PIN_CHG_EN, OUTPUT);
  digitalWrite(PIN_CHG_EN, on ? HIGH : LOW);
  gpio_hold_en((gpio_num_t)PIN_CHG_EN);
#if !BUTTON_WAKE_EXT0
  gpio_deep_sleep_hold_en();  // ESP32-C3: digital pad hold during deep sleep
#endif
}

bool rtcBegin() { return rtc.begin(&Wire); }

uint32_t rtcNow() {
  uint32_t t = rtc.now().unixtime();
  return t >= MIN_VALID_EPOCH ? t : 0;
}

bool rtcLostPower() { return rtc.lostPower(); }

void rtcSet(uint32_t epoch) { rtc.adjust(DateTime(epoch)); }

bool buttonPressed() { return digitalRead(PIN_BUTTON) == LOW; }

}  // namespace hw
