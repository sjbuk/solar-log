// Formatting of records for the upload JSON body (see docs/data-format.md).
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "record.h"

namespace solarlog {

// Writes "[seq,epoch,isc,tcell,tamb,vbat,flags]" (invalid temps as null).
// Returns number of chars written (excluding NUL), or 0 if it does not fit.
size_t formatRecordJson(char* out, size_t cap, uint32_t seq, const Record& r);

}  // namespace solarlog
