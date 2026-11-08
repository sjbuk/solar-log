// Fixed-capacity ring log of records on an abstract block storage.
// Header (32 bytes) followed by `capacity` 16-byte slots; record with sequence
// number s lives in slot s % capacity. See docs/data-format.md.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "record.h"

namespace solarlog {

class Storage {
 public:
  virtual ~Storage() = default;
  virtual bool read(uint32_t offset, void* buf, size_t len) = 0;
  virtual bool write(uint32_t offset, const void* buf, size_t len) = 0;
  virtual bool flush() { return true; }
};

class RingLog {
 public:
  static constexpr uint32_t MAGIC = 0x31474C53;  // "SLG1"
  static constexpr uint32_t HEADER_SIZE = 32;

  explicit RingLog(Storage& storage) : storage_(storage) {}

  // Load an existing log; if missing/corrupt or capacity differs, format a new one.
  // Returns true if an existing log was loaded.
  bool begin(uint32_t capacity);
  void format(uint32_t capacity, uint32_t firstSeq = 0);

  // Append records (sets seqLo). Overwrites oldest when full. Returns seq of last appended.
  uint32_t append(const Record* recs, size_t n);
  uint32_t append(const Record& r) { return append(&r, 1); }

  // i in [0, count): i-th oldest unacknowledged record.
  bool peek(uint32_t i, Record& out, uint32_t* seqOut = nullptr);

  // Drop all records with seq <= lastSeq.
  void ack(uint32_t lastSeq);

  uint32_t count() const { return count_; }
  uint32_t headSeq() const { return headSeq_; }
  uint32_t nextSeq() const { return headSeq_ + count_; }
  uint32_t capacity() const { return capacity_; }
  uint32_t overwritten() const { return overwritten_; }

  static uint32_t storageBytes(uint32_t capacity) { return HEADER_SIZE + capacity * RECORD_SIZE; }

 private:
  bool writeHeader();
  uint32_t slotOffset(uint32_t seq) const {
    return HEADER_SIZE + (seq % capacity_) * (uint32_t)RECORD_SIZE;
  }

  Storage& storage_;
  uint32_t capacity_ = 0;
  uint32_t headSeq_ = 0;
  uint32_t count_ = 0;
  uint32_t overwritten_ = 0;  // total records lost to overflow (diagnostic)
};

}  // namespace solarlog
