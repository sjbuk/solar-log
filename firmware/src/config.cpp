#include "config.h"

#include <Preferences.h>

static const char* NS = "solarlog";

String defaultDeviceId() {
  uint64_t mac = ESP.getEfuseMac();
  char buf[24];
  snprintf(buf, sizeof(buf), "solarlog-%02x%02x%02x", (unsigned)((mac >> 24) & 0xFF),
           (unsigned)((mac >> 32) & 0xFF), (unsigned)((mac >> 40) & 0xFF));
  return String(buf);
}

bool loadConfig(DeviceConfig& c) {
  Preferences p;
  p.begin(NS, true);
  c.deviceId = p.getString("id", defaultDeviceId());
  c.serverUrl = p.getString("url", "");
  c.token = p.getString("token", "");
  c.lat = p.getDouble("lat", c.lat);
  c.lon = p.getDouble("lon", c.lon);
  c.tiltDeg = p.getFloat("tilt", c.tiltDeg);
  c.azimuthDeg = p.getFloat("azim", c.azimuthDeg);
  c.sampleIntervalS = p.getUShort("intv", c.sampleIntervalS);
  c.uploadHourUtc = p.getUChar("uphr", c.uploadHourUtc);
  c.tempEvery = p.getUChar("tevery", c.tempEvery);
  c.swapProbes = p.getBool("swap", c.swapProbes);
  p.end();
  if (c.sampleIntervalS < 10) c.sampleIntervalS = 10;
  if (c.uploadHourUtc > 23) c.uploadHourUtc = 21;
  if (c.tempEvery == 0) c.tempEvery = 1;
  return c.isComplete();
}

void saveConfig(const DeviceConfig& c) {
  Preferences p;
  p.begin(NS, false);
  p.putString("id", c.deviceId);
  p.putString("url", c.serverUrl);
  p.putString("token", c.token);
  p.putDouble("lat", c.lat);
  p.putDouble("lon", c.lon);
  p.putFloat("tilt", c.tiltDeg);
  p.putFloat("azim", c.azimuthDeg);
  p.putUShort("intv", c.sampleIntervalS);
  p.putUChar("uphr", c.uploadHourUtc);
  p.putUChar("tevery", c.tempEvery);
  p.putBool("swap", c.swapProbes);
  p.end();
}
