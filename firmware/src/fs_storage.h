// LittleFS-backed Storage for the ring log.
#pragma once
#include <LittleFS.h>

#include "ringlog.h"

class FsStorage : public solarlog::Storage {
 public:
  explicit FsStorage(const char* path) : path_(path) {}

  bool open() {
    if (!LittleFS.begin(true)) return false;  // format on first use
    if (!LittleFS.exists(path_)) {
      File f = LittleFS.open(path_, "w");
      if (!f) return false;
      f.close();
    }
    file_ = LittleFS.open(path_, "r+");
    return (bool)file_;
  }

  void close() {
    if (file_) file_.close();
    LittleFS.end();
  }

  bool read(uint32_t off, void* buf, size_t len) override {
    if (!file_ || off + len > file_.size()) return false;
    return file_.seek(off) && file_.read((uint8_t*)buf, len) == len;
  }

  bool write(uint32_t off, const void* buf, size_t len) override {
    if (!file_) return false;
    // Grow the file lazily (pad with 0xFF) instead of pre-allocating megabytes.
    if (off > file_.size()) {
      file_.seek(file_.size());
      uint8_t pad[64];
      memset(pad, 0xFF, sizeof(pad));
      size_t todo = off - file_.size();
      while (todo) {
        size_t n = todo < sizeof(pad) ? todo : sizeof(pad);
        if (file_.write(pad, n) != n) return false;
        todo -= n;
      }
    }
    return file_.seek(off) && file_.write((const uint8_t*)buf, len) == len;
  }

  bool flush() override {
    if (file_) file_.flush();
    return true;
  }

 private:
  const char* path_;
  File file_;
};
