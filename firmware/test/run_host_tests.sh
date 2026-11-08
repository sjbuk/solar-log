#!/usr/bin/env bash
# Build and run the core unit tests with the host C++ compiler, without PlatformIO.
# (With PlatformIO available, prefer: pio test -e native)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
core="$here/../lib/core/src"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
"${CXX:-g++}" -std=gnu++17 -Wall -Wextra -Werror -O1 \
  -I "$here/host_shim" -I "$core" \
  "$here/test_core/test_main.cpp" "$core"/*.cpp -o "$out/test_core" -lm
"$out/test_core"
