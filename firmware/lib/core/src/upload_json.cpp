#include "upload_json.h"

#include <stdio.h>

namespace solarlog {

static int fmtTemp(char* out, size_t cap, int16_t t) {
  if (t == TEMP_INVALID) return snprintf(out, cap, "null");
  return snprintf(out, cap, "%d", (int)t);
}

size_t formatRecordJson(char* out, size_t cap, uint32_t seq, const Record& r) {
  char tc[8], ta[8];
  fmtTemp(tc, sizeof(tc), r.tcell);
  fmtTemp(ta, sizeof(ta), r.tamb);
  int n = snprintf(out, cap, "[%lu,%lu,%u,%s,%s,%u,%u]", (unsigned long)seq,
                   (unsigned long)r.epoch, (unsigned)r.isc, tc, ta, (unsigned)r.vbat,
                   (unsigned)r.flags);
  if (n < 0 || (size_t)n >= cap) return 0;
  return (size_t)n;
}

}  // namespace solarlog
