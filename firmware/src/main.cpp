// Solar-Log main: every wake is a short run-to-completion cycle, then deep sleep.
//
//   wake ─► rail on ─► read RTC ─► [daylight] sample Isc/temps/Vbat ─► charge policy
//        ─► stage record in RTC RAM ─► [batch full / upload due] flush to flash log
//        ─► [upload due / button] WiFi upload + NTP ─► rail off ─► deep sleep
#include <Arduino.h>
#include <esp_sleep.h>

#include "board.h"
#include "charge.h"
#include "config.h"
#include "fs_storage.h"
#include "hw.h"
#include "provisioning.h"
#include "record.h"
#include "ringlog.h"
#include "schedule.h"
#include "uploader.h"

using namespace solarlog;

namespace {
constexpr uint32_t RTC_MAGIC = 0x534C5231;  // "SLR1"
constexpr uint8_t STAGE_CAP = 30;
constexpr uint32_t LOG_CAPACITY = 90000;    // ~1.44 MB, ~3 months of daylight minutes
constexpr uint32_t RETRY_S = 3600;
constexpr uint8_t MAX_RETRIES = 3;
constexpr uint32_t PORTAL_HOLD_MS = 3000;

struct RtcState {
  uint32_t magic;
  Record staged[STAGE_CAP];
  uint8_t nStaged;
  uint32_t lastUploadEpoch;
  uint32_t retryAt;
  uint8_t retries;
  bool chargeEnabled;
  uint32_t sampleCounter;
  int16_t lastTcell;
  int16_t lastTamb;
};
RTC_DATA_ATTR RtcState st;

DeviceConfig cfg;

void resetState() {
  memset(&st, 0, sizeof(st));
  st.magic = RTC_MAGIC;
  st.lastTcell = TEMP_INVALID;
  st.lastTamb = TEMP_INVALID;
}

ScheduleConfig scheduleCfg() {
  ScheduleConfig s;
  s.lat = cfg.lat;
  s.lon = cfg.lon;
  s.sampleIntervalS = cfg.sampleIntervalS;
  s.uploadHourUtc = cfg.uploadHourUtc;
  return s;
}

void sample(uint32_t now, bool timeUnsynced) {
  Record r;
  r.epoch = now;
  if (timeUnsynced) r.flags |= FLAG_TIME_UNSYNCED;

  IscReading isc = hw::readIsc();
  r.isc = iscFromMilliamps(isc.valid ? isc.mA : 0);
  if (!isc.valid) r.flags |= FLAG_ISC_INVALID;

  // Temperatures change slowly: read every Nth sample, otherwise carry the last value.
  if (st.sampleCounter % cfg.tempEvery == 0 || st.lastTcell == TEMP_INVALID) {
    TempReading t = hw::readTemps(cfg.swapProbes);
    st.lastTcell = tempFromCelsius(t.cellC, t.cellValid);
    st.lastTamb = tempFromCelsius(t.ambC, t.ambValid);
  }
  ++st.sampleCounter;
  r.tcell = st.lastTcell;
  r.tamb = st.lastTamb;
  if (r.tcell == TEMP_INVALID) r.flags |= FLAG_TCELL_INVALID;
  if (r.tamb == TEMP_INVALID) r.flags |= FLAG_TAMB_INVALID;

  r.vbat = hw::readVbatMv();

  // Charge policy: the battery sits between the two probes thermally (cell is hottest in
  // sun, ambient coldest at night), so both limits must pass using the lower and the
  // higher of the valid readings respectively.
  bool tValid = r.tcell != TEMP_INVALID || r.tamb != TEMP_INVALID;
  float tc = tempToCelsius(r.tcell), ta = tempToCelsius(r.tamb);
  float tLow = isnan(tc) ? ta : (isnan(ta) ? tc : fminf(tc, ta));
  float tHigh = isnan(tc) ? ta : (isnan(ta) ? tc : fmaxf(tc, ta));
  ChargePolicy policy;
  bool allowLow = chargeAllowed(policy, st.chargeEnabled, tValid, tLow, r.vbat);
  bool allowHigh = chargeAllowed(policy, st.chargeEnabled, tValid, tHigh, r.vbat);
  st.chargeEnabled = allowLow && allowHigh;
  hw::setChargeEnable(st.chargeEnabled);
  if (!st.chargeEnabled) r.flags |= FLAG_CHARGE_LOCKOUT;
  if (hw::chargerActive()) r.flags |= FLAG_CHARGING;

  if (st.nStaged < STAGE_CAP) st.staged[st.nStaged++] = r;
}

bool flushStaged(RingLog& log) {
  if (st.nStaged == 0) return true;
  log.append(st.staged, st.nStaged);
  st.nStaged = 0;
  return true;
}

void goToSleep(uint32_t seconds) {
  hw::railOff();
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
#if BUTTON_WAKE_EXT0
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_BUTTON, 0);
#else
  esp_deep_sleep_enable_gpio_wakeup(1ULL << PIN_BUTTON, ESP_GPIO_WAKEUP_GPIO_LOW);
#endif
  Serial.flush();
  esp_deep_sleep_start();
}

uint32_t buttonHoldMs() {
  uint32_t t0 = millis();
  while (hw::buttonPressed() && millis() - t0 < PORTAL_HOLD_MS + 100) delay(10);
  return millis() - t0;
}
}  // namespace

void setup() {
  hw::initPins();
#ifdef SOLARLOG_SLEEP_TEST
  // Low-power mod verification (docs/esp32-devkit-mod.md): nothing on, sleep 1 h.
  hw::setChargeEnable(false);
  goToSleep(3600);
#endif
  Serial.begin(115200);

  const esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  const bool coldBoot = cause == ESP_SLEEP_WAKEUP_UNDEFINED || st.magic != RTC_MAGIC;
  if (coldBoot) {
    resetState();
    hw::setChargeEnable(false);  // fail-safe until the first temperature reading
  }

  const bool configured = loadConfig(cfg);
  bool buttonWake = cause == ESP_SLEEP_WAKEUP_EXT0 || cause == ESP_SLEEP_WAKEUP_GPIO;
  bool forceUpload = false;
  if (buttonWake || (coldBoot && hw::buttonPressed())) {
    if (buttonHoldMs() >= PORTAL_HOLD_MS) {
      runSetupPortal(cfg);
    } else {
      forceUpload = true;  // short press: upload now (also a WiFi/RSSI check)
    }
  } else if (!configured) {
    runSetupPortal(cfg);
  }
  if (!cfg.isComplete()) goToSleep(3600);  // nothing useful to do until configured

  hw::railOn();
  bool rtcOk = hw::rtcBegin();
  uint32_t now = rtcOk ? hw::rtcNow() : 0;
  bool timeUnsynced = !rtcOk || now == 0 || hw::rtcLostPower();

  if (coldBoot) {
    Serial.printf("Solar-Log %s id=%s rtc=%s\n", SOLARLOG_FW_VERSION, cfg.deviceId.c_str(),
                  timeUnsynced ? "UNSYNCED" : "ok");
    TempReading t = hw::readTemps(cfg.swapProbes);
    Serial.printf("probe0(cell)=%.2f probe1(amb)=%.2f  (warm the cell probe to identify)\n",
                  t.cellC, t.ambC);
  }

  const ScheduleConfig sc = scheduleCfg();
  // Cold boot always uploads once (NTP sync + connectivity check). An unsynced clock does
  // not force uploads on later wakes: the hourly retry logic handles that without
  // draining the battery.
  bool doUpload = forceUpload || coldBoot || now == 0 ||
                  uploadDue(now, st.lastUploadEpoch, cfg.uploadHourUtc) ||
                  (st.retryAt != 0 && now >= st.retryAt);

  if (now != 0 && isDaylight(sc, now)) sample(now, timeUnsynced);

  if (st.nStaged >= STAGE_CAP || doUpload) {
    FsStorage storage("/log.bin");
    if (storage.open()) {
      RingLog log(storage);
      log.begin(LOG_CAPACITY);
      flushStaged(log);
      if (doUpload) {
        UploadResult res = uploadLog(cfg, log, hw::readVbatMv());
        if (res.ntpOk) {
          uint32_t drift = res.ntpEpoch > now ? res.ntpEpoch - now : now - res.ntpEpoch;
          if (now == 0 || timeUnsynced || drift > 2) {
            hw::rtcSet(res.ntpEpoch);
          }
          now = res.ntpEpoch;
        }
        Serial.printf("upload wifi=%d ntp=%d rssi=%d sent=%u left=%u\n", res.wifiOk, res.ntpOk,
                      res.rssi, (unsigned)res.sent, (unsigned)log.count());
        if (now != 0) {
          st.lastUploadEpoch = now;  // this slot is done either way
          if (res.complete) {
            st.retries = 0;
            st.retryAt = 0;
          } else if (st.retries < MAX_RETRIES) {
            ++st.retries;
            st.retryAt = now + RETRY_S;
          } else {
            st.retryAt = 0;  // give up until tomorrow's slot; data stays in flash
            st.retries = 0;
          }
        }
      }
      storage.close();
    }
  }

  if (now == 0) goToSleep(RETRY_S);  // no valid time at all: try again in an hour

  uint32_t sleepS = secondsToNextWake(sc, now, st.lastUploadEpoch);
  if (st.retryAt > now && st.retryAt - now < sleepS) sleepS = st.retryAt - now;
  goToSleep(sleepS);
}

void loop() {}  // never reached
