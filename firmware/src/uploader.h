// Daily WiFi upload of the ring log + NTP time sync.
#pragma once
#include <Arduino.h>

#include "config.h"
#include "ringlog.h"

struct UploadResult {
  bool wifiOk = false;
  bool ntpOk = false;
  uint32_t ntpEpoch = 0;
  uint32_t sent = 0;       // records acknowledged by the server
  bool complete = false;   // log fully drained
  int rssi = 0;
};

// Connects, syncs time, posts unsent records in batches, acks them in the log, disconnects.
// Bounded by a hard timeout to protect the battery.
UploadResult uploadLog(const DeviceConfig& cfg, solarlog::RingLog& log, uint16_t vbatMv,
                       uint32_t timeoutMs = 20000);
