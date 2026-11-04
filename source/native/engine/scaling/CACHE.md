# Costume draw cache

The hybrid candidate build enables this optional CPU optimization. Use
`--without-costume-cache` with `engine/build.py` to build the comparison engine.
This disables caching while retaining the other engine optimizations.

The core entry adapter starts the cache after audio startup, before the original
main function allocates its resource heap. One optional 65536-byte
`MEMF_PUBLIC | MEMF_FAST | MEMF_CLEAR` allocation holds metadata, generated drawing code and source copies.
On the target machine Exec classifies Slow RAM as FAST. Allocation never falls
back to Chip RAM; failure uses the existing optimized renderer. The exported
loader cleanup endpoint frees the exact allocation once, including when called
again after cleanup. No additional loader ABI is required.

Only fresh, fully onscreen one-mask draws in either direction qualify. Other draws use
the existing optimized loops. The current costume pointer comes from G59b4.
Its six-byte header contains little-endian allocation size, type 2, and costume
ID. Every lookup validates the current G2778 costume-table ownership, G235c
count, current allocation bounds, actual Exec RAM regions and disjoint ranges.
The cached source span must fit the current allocation before any comparison.
An exact byte comparison then handles changed resource contents, including
same-address reallocation. Neither a previous allocation size nor a hash is
trusted. Resource relocation changes the key; eviction clears the owner slot
before freeing the block in the original engine.

The key contains source, allocation base/end, raw dimensions/scales, initial X
and Y phases, reset Y phase, X modulo 8 and draw direction. The fixed original scaling table
is the same table already validated by the prefix renderer. The manager rejects
framebuffer overlap with source, masks, original globals, cache arena or control
storage. Source/mask overlap with cache control storage is also rejected before
any manager write. Mask and palette values are deliberately absent from the key.

Each entry starts with a source-copy pointer/length and a reserved width word,
then a small 68000 drawing routine. A column selects its mask bit; each candidate
conditionally copies one byte from the live palette to the live framebuffer.
Destination addresses use a 32512-byte bias so offsets from -255 through 63935
fit signed instruction displacements. Leftward validation includes the bytes
before the initial destination and mask pointers. Clear replay uses the current guard's
zero-mask proof and the same routine as masked replay. Mask tests and palette
reads retain their original order; changing the destination, mask or palette
does not require recompilation.

The first encounter records only a bounded warm-history key. A repeated miss
records during the existing optimized draw. Per-column worst-case reservations
avoid a bounds branch at every pixel. Overflow finishes the current frame using
the pristine renderer; it never redraws a frame. An entry is published only after
complete rendering, exact consumed-source copying, parity/alignment checks and
final validation. Entries use bounded LRU metadata and physically contiguous
holes; no heap compaction or second decode is required.
Reservation demand is capped by the key's geometric worst case, so a previous
large pose does not force eviction for a small one. Two failed recording attempts
make a resident warm-history key negative; repeated oversized poses then use the
pristine optimized renderer. Changed source bytes with the same negative key can
remain uncached, which only forgoes a performance gain. Replacing that bounded
history slot permits admission again.

`cache_patch.py` resolves ordinary object HUNK_EXT references against actual
core exports, and emits real BSS/code HUNK relocations. No original-global
scratch pointer or fixed test address is used. On 68000/68010 the completed routine can execute directly. On later CPUs,
Exec V37 or newer must flush it with CacheClearU before the entry is published,
including when an evicted address is reused. Later CPUs on older Exec retain
the ordinary renderer; old ROM CPU flags cannot identify every cache type.
No privileged cache instructions are embedded in the generated code.

`test_cache.py` builds synthetic RLE streams, ownership tables, masks, palettes
and Exec stubs and compares with the original executable under a 68000 guest.
It checks registers, CCR, framebuffer, globals, masks, palette read order,
two load layouts, odd input, full height, overflow, lifecycle, failed allocation,
source changes, shorter reallocation, and aliases. It needs no captured RAM or
previous build directory. Forty CPU/Exec profiles also check API availability,
flush-before-publication and address reuse. `test_cache_extended.py` compares
moved destinations, random masks/palettes and resource address reuse with the
original, including ordered writes and destination bounds.

The prefix scaling tables use one 257-byte period per scale rather than two.
All three readers account for phase wrap. This saves 65536 bytes, more than
the extra cache allocation, and keeps the tested 1 MiB Chip + 1 MiB Slow RAM
configuration. `test_prefix_counts.py` checks every scale, phase and byte-sized
run length (16,777,216 combinations).

The exported context's first 28 bytes are recorder/replay state. Diagnostics
begin at offset 28: arena pointer, valid begins, hits, successful builds, cold
encounters, evictions, overflows, live entries, occupied bytes, and reservation
high-water mark. These update only at draw boundaries. A hard validation
rejection leaves context unchanged, so `begins` counts valid qualifying calls.
Offsets 68 and 72 hold negative-admission skips and recording attempts armed.
