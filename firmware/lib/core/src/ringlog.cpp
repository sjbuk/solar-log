#include "ringlog.h"

#include <string.h>

namespace solarlog {

namespace {
struct Header {
  uint32_t magic;
  uint32_t capacity;
  uint32_t headSeq;
  uint32_t count;
  uint32_t overwritten;
  uint32_t checksum;
  uint32_t reserved[2];
};
static_assert(sizeof(Header) == RingLog::HEADER_SIZE, "header size");

uint32_t headerChecksum(const Header& h) {
  return h.magic ^ (h.capacity * 2654435761u) ^ (h.headSeq * 40503u) ^ (h.count + 0x9E3779B9u) ^
         h.overwritten;
}
}  // namespace

bool RingLog::begin(uint32_t capacity) {
  Header h;
  if (storage_.read(0, &h, sizeof(h)) && h.magic == MAGIC && h.capacity == capacity &&
      h.count <= capacity && h.checksum == headerChecksum(h)) {
    capacity_ = h.capacity;
    headSeq_ = h.headSeq;
    count_ = h.count;
    overwritten_ = h.overwritten;
    return true;
  }
  format(capacity);
  return false;
}

void RingLog::format(uint32_t capacity, uint32_t firstSeq) {
  capacity_ = capacity;
  headSeq_ = firstSeq;
  count_ = 0;
  overwritten_ = 0;
  writeHeader();
  storage_.flush();
}

bool RingLog::writeHeader() {
  Header h;
  memset(&h, 0, sizeof(h));
  h.magic = MAGIC;
  h.capacity = capacity_;
  h.headSeq = headSeq_;
  h.count = count_;
  h.overwritten = overwritten_;
  h.checksum = headerChecksum(h);
  return storage_.write(0, &h, sizeof(h));
}

uint32_t RingLog::append(const Record* recs, size_t n) {
  uint8_t buf[RECORD_SIZE];
  for (size_t i = 0; i < n; ++i) {
    uint32_t seq = nextSeq();
    Record r = recs[i];
    r.seqLo = (uint16_t)(seq & 0xFFFF);
    encodeRecord(r, buf);
    storage_.write(slotOffset(seq), buf, RECORD_SIZE);
    if (count_ == capacity_) {
      ++headSeq_;  // oldest overwritten
      ++overwritten_;
    } else {
      ++count_;
    }
  }
  writeHeader();
  storage_.flush();
  return nextSeq() - 1;
}

bool RingLog::peek(uint32_t i, Record& out, uint32_t* seqOut) {
  if (i >= count_) return false;
  uint32_t seq = headSeq_ + i;
  uint8_t buf[RECORD_SIZE];
  if (!storage_.read(slotOffset(seq), buf, RECORD_SIZE)) return false;
  if (!decodeRecord(buf, out)) return false;
  if (out.seqLo != (uint16_t)(seq & 0xFFFF)) return false;  // slot inconsistent
  if (seqOut) *seqOut = seq;
  return true;
}

void RingLog::ack(uint32_t lastSeq) {
  if (count_ == 0) return;
  // Signed distance copes with 32-bit wrap (practically never reached).
  int32_t drop = (int32_t)(lastSeq - headSeq_) + 1;
  if (drop <= 0) return;
  if ((uint32_t)drop > count_) drop = (int32_t)count_;
  headSeq_ += (uint32_t)drop;
  count_ -= (uint32_t)drop;
  writeHeader();
  storage_.flush();
}

}  // namespace solarlog
