#!/bin/sh
set -eu
if [ "$#" -ne 5 ]; then
    printf '%s\n' 'Usage: sh tests/smoke.sh /path/to/build-amiga-talkie /Amiga/data /monster.sou /disk1.adf /new/test/folder'
    exit 2
fi
BUILDER=$1
AMIGA=$2
SOU=$3
ENGINE=$4
WORK=$5
if [ -e "$WORK" ]; then printf '%s\n' 'Choose a new test folder.' >&2; exit 1; fi
mkdir -p "$WORK"
cp "$BUILDER" "$WORK/Standalone Builder"
BUILDER="$WORK/Standalone Builder"
chmod +x "$BUILDER"
"$BUILDER" --self-test
OUTPUT="$WORK/Game output with spaces"
"$BUILDER" --amiga "$AMIGA" --sou "$SOU" --engine "$ENGINE" --output "$OUTPUT"
if grep -q '"engine_planar_cache"' "$OUTPUT/module.json"; then
    test -s "$OUTPUT/native-planar.dat"
fi
find "$OUTPUT" -type f -exec sha256sum '{}' \; > "$WORK/before.sha256"
if "$BUILDER" --amiga "$AMIGA" --sou "$SOU" --engine "$ENGINE" --output "$OUTPUT" >/dev/null 2>&1; then
    printf '%s\n' 'ERROR: existing output was accepted.' >&2; exit 1
fi
sha256sum --check --status "$WORK/before.sha256"
printf '%s\n' 'not an archive' > "$WORK/invalid.sou"
if "$BUILDER" --amiga "$AMIGA" --sou "$WORK/invalid.sou" --engine "$ENGINE" --output "$WORK/rejected" >/dev/null 2>&1; then
    printf '%s\n' 'ERROR: invalid speech archive was accepted.' >&2; exit 1
fi
if "$BUILDER" --amiga "$AMIGA" --sou "$SOU" --engine "$WORK/invalid.sou" --output "$WORK/rejected" >/dev/null 2>&1; then
    printf '%s\n' 'ERROR: invalid executable was accepted.' >&2; exit 1
fi
test ! -e "$WORK/rejected"
printf '%s\n' 'PASS: standalone Linux builder; generated file checksums; existing output preserved; invalid inputs rejected.'
