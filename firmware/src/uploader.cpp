#include "uploader.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#include "upload_json.h"

#ifndef SOLARLOG_FW_VERSION
#define SOLARLOG_FW_VERSION "dev"
#endif

namespace {
constexpr uint32_t BATCH = 100;

bool timedOut(uint32_t start, uint32_t timeoutMs) { return millis() - start > timeoutMs; }

// Extract "last_seq": N from a small JSON response without a JSON library.
bool parseLastSeq(const String& body, uint32_t& out) {
  int i = body.indexOf("\"last_seq\"");
  if (i < 0) return false;
  i = body.indexOf(':', i);
  if (i < 0) return false;
  out = (uint32_t)strtoul(body.c_str() + i + 1, nullptr, 10);
  return true;
}

String buildBody(const DeviceConfig& cfg, solarlog::RingLog& log, uint32_t n, int rssi,
                 uint16_t vbatMv) {
  String s;
  s.reserve(256 + n * 48);
  char head[320];
  snprintf(head, sizeof(head),
           "{\"device\":\"%s\",\"fw\":\"%s\",\"rssi\":%d,\"vbat_mV\":%u,"
           "\"site\":{\"lat\":%.5f,\"lon\":%.5f,\"tilt\":%.1f,\"azimuth\":%.1f},\"records\":[",
           cfg.deviceId.c_str(), SOLARLOG_FW_VERSION, rssi, (unsigned)vbatMv, cfg.lat, cfg.lon,
           cfg.tiltDeg, cfg.azimuthDeg);
  s += head;
  char rec[64];
  solarlog::Record r;
  uint32_t seq;
  bool first = true;
  for (uint32_t i = 0; i < n; ++i) {
    if (!log.peek(i, r, &seq)) break;  // unreadable slot: stop; it will be retried
    if (!solarlog::formatRecordJson(rec, sizeof(rec), seq, r)) continue;
    if (!first) s += ',';
    s += rec;
    first = false;
  }
  s += "]}";
  return s;
}
}  // namespace

UploadResult uploadLog(const DeviceConfig& cfg, solarlog::RingLog& log, uint16_t vbatMv,
                       uint32_t timeoutMs) {
  UploadResult res;
  const uint32_t start = millis();

  WiFi.mode(WIFI_STA);
  WiFi.begin();  // credentials saved by the provisioning portal
  while (WiFi.status() != WL_CONNECTED && !timedOut(start, 10000)) delay(50);
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    return res;
  }
  res.wifiOk = true;
  res.rssi = WiFi.RSSI();

  configTime(0, 0, "pool.ntp.org", "time.google.com");
  while (!timedOut(start, 14000)) {
    time_t now = time(nullptr);
    if (now > 1735689600) {  // 2025-01-01
      res.ntpOk = true;
      res.ntpEpoch = (uint32_t)now;
      break;
    }
    delay(50);
  }

  const String url = cfg.serverUrl + "/api/v1/upload";
  WiFiClient plain;
  WiFiClientSecure secure;
  // Self-hosted server on the LAN: plain HTTP is expected. For HTTPS we do not pin
  // a certificate (no CA store on device); traffic is encrypted but not authenticated.
  secure.setInsecure();
  const bool https = url.startsWith("https://");

  while (log.count() > 0 && !timedOut(start, timeoutMs)) {
    // Drop an unreadable (corrupt) oldest slot so it cannot block the queue forever.
    solarlog::Record probe;
    if (!log.peek(0, probe)) {
      log.ack(log.headSeq());
      continue;
    }
    uint32_t n = log.count() < BATCH ? log.count() : BATCH;
    String body = buildBody(cfg, log, n, res.rssi, vbatMv);
    HTTPClient http;
    if (https ? !http.begin(secure, url) : !http.begin(plain, url)) break;
    http.setTimeout(5000);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer " + cfg.token);
    int code = http.POST(body);
    if (code != 200) {
      http.end();
      break;
    }
    uint32_t lastSeq;
    bool ok = parseLastSeq(http.getString(), lastSeq);
    http.end();
    if (!ok) break;
    uint32_t before = log.count();
    log.ack(lastSeq);
    res.sent += before - log.count();
    if (log.count() == before) break;  // no progress; avoid looping
  }
  res.complete = log.count() == 0;

  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  return res;
}
