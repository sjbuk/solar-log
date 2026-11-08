#include "provisioning.h"

#include <WiFiManager.h>

namespace {
bool saved = false;
void onSave() { saved = true; }
}  // namespace

bool runSetupPortal(DeviceConfig& cfg, uint16_t timeoutS) {
  char lat[16], lon[16], tilt[8], azim[8], intv[8], uphr[4], tevery[4];
  snprintf(lat, sizeof(lat), "%.5f", cfg.lat);
  snprintf(lon, sizeof(lon), "%.5f", cfg.lon);
  snprintf(tilt, sizeof(tilt), "%.1f", cfg.tiltDeg);
  snprintf(azim, sizeof(azim), "%.1f", cfg.azimuthDeg);
  snprintf(intv, sizeof(intv), "%u", cfg.sampleIntervalS);
  snprintf(uphr, sizeof(uphr), "%u", cfg.uploadHourUtc);
  snprintf(tevery, sizeof(tevery), "%u", cfg.tempEvery);

  WiFiManager wm;
  WiFiManagerParameter pId("id", "Device ID", cfg.deviceId.c_str(), 32);
  WiFiManagerParameter pUrl("url", "Server URL (http://host:8000)", cfg.serverUrl.c_str(), 96);
  WiFiManagerParameter pTok("token", "Device token", cfg.token.c_str(), 64);
  WiFiManagerParameter pLat("lat", "Latitude (deg N)", lat, 15);
  WiFiManagerParameter pLon("lon", "Longitude (deg E, west negative)", lon, 15);
  WiFiManagerParameter pTilt("tilt", "Panel tilt (deg from horizontal)", tilt, 7);
  WiFiManagerParameter pAzim("azim", "Panel azimuth (compass deg, 180=S)", azim, 7);
  WiFiManagerParameter pIntv("intv", "Sample interval (s)", intv, 7);
  WiFiManagerParameter pUphr("uphr", "Daily upload hour (UTC)", uphr, 3);
  WiFiManagerParameter pTev("tevery", "Read temperatures every N samples", tevery, 3);
  WiFiManagerParameter pSwap("swap", "Swap probes (1=yes)", cfg.swapProbes ? "1" : "0", 2);
  WiFiManagerParameter* params[] = {&pId,  &pUrl,  &pTok, &pLat, &pLon, &pTilt,
                                    &pAzim, &pIntv, &pUphr, &pTev, &pSwap};
  for (auto* p : params) wm.addParameter(p);

  saved = false;
  wm.setSaveParamsCallback(onSave);
  wm.setSaveConfigCallback(onSave);
  wm.setBreakAfterConfig(true);
  wm.setConfigPortalTimeout(timeoutS);
  String ap = "SolarLog-" + cfg.deviceId.substring(cfg.deviceId.length() - 6);
  wm.startConfigPortal(ap.c_str());

  if (saved) {
    cfg.deviceId = pId.getValue();
    cfg.serverUrl = pUrl.getValue();
    while (cfg.serverUrl.endsWith("/")) cfg.serverUrl.remove(cfg.serverUrl.length() - 1);
    cfg.token = pTok.getValue();
    cfg.lat = atof(pLat.getValue());
    cfg.lon = atof(pLon.getValue());
    cfg.tiltDeg = atof(pTilt.getValue());
    cfg.azimuthDeg = atof(pAzim.getValue());
    cfg.sampleIntervalS = (uint16_t)atoi(pIntv.getValue());
    cfg.uploadHourUtc = (uint8_t)atoi(pUphr.getValue());
    cfg.tempEvery = (uint8_t)atoi(pTev.getValue());
    cfg.swapProbes = atoi(pSwap.getValue()) == 1;
    saveConfig(cfg);
    loadConfig(cfg);  // re-apply validation/clamping
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  return saved;
}
