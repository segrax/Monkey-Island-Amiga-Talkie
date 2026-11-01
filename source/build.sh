#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SOURCE/.." && pwd)
cmake -S "$SOURCE" -B "$ROOT/build/linux" -DCMAKE_BUILD_TYPE=Release
cmake --build "$ROOT/build/linux" --parallel
ctest --test-dir "$ROOT/build/linux" --output-on-failure
cp "$ROOT/build/linux/build-amiga-talkie" "$ROOT/build-amiga-talkie"
printf '%s\n' 'Ready: build-amiga-talkie'
