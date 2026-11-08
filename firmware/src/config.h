// Persistent device configuration (NVS). WiFi credentials are stored separately by
// the ESP32 WiFi stack (set via the WiFiManager portal).
#pragma once
#include <Arduino.h>

struct DeviceConfig {
  String deviceId;            // default "solarlog-xxxxxx" from MAC
  String serverUrl;           // e.g. http://192.168.1.10:8000
  String token;               // bearer token configured on the server
  double lat = 51.5;
  double lon = -0.12;
  float tiltDeg = 35;
  float azimuthDeg = 180;     // compass degrees, 180 = south
  uint16_t sampleIntervalS = 60;
  uint8_t uploadHourUtc = 21;
  uint8_t tempEvery = 5;      // read temperatures every Nth sample
  bool swapProbes = false;    // DS18B20 index 0 is ambient instead of cell

  bool isComplete() const { return serverUrl.length() > 0 && token.length() > 0; }
};

String defaultDeviceId();
bool loadConfig(DeviceConfig& c);   // returns isComplete()
void saveConfig(const DeviceConfig& c);
