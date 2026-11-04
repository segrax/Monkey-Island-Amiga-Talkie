# Prepared image data

`native-planar.dat` is generated from the verified original Amiga resources.
It contains data, not executable code. All integers below are big endian;
offsets in the outer directory are relative to the file, and payload offsets
are relative to that payload. Payloads, dictionaries, indices, strip descriptors
and dependency masks start on even addresses. A version 2 source reference
starts on an odd address.

## Directory

The 32-byte header contains:

| Offset | Type | Value |
| --- | --- | --- |
| 0 | 8 bytes | `NVPART01` |
| 8 | u16 | Version 1 |
| 10 | u16 | Directory entry size 24 |
| 12 | u32 | Entry count |
| 16 | u32 | Directory offset 32 |
| 20 | u32 | Data offset `32 + count * 24` |
| 24 | u32 | Complete file size |
| 28 | u32 | Zero |

Entries are sorted by `(room, object)` with no duplicate keys. Identical room
copies on multiple original disks produce one entry; conflicting copies fail
the build.

| Offset | Type | Value |
| --- | --- | --- |
| 0, 2 | u16, u16 | Room and object ID |
| 4, 8 | u32, u32 | Payload file offset and length |
| 12 | u32 | Original OI chunk length |
| 16, 18 | u16, u16 | Pixel width and height |
| 20 | u32 | Fletcher32 of the complete payload |

Fletcher32 uses big-endian 16-bit words, starting both sums at 65535. For each
word, add the word to the first sum and the first sum to the second, modulo
65535. Zero residues use the representation 65535. Return the second sum in
the high word and the first in the low word. Padding participates in the sum.
The native end-around-carry implementation and the host block implementation
produce identical results.

## Payload

The 64-byte header contains:

| Offset | Type | Value |
| --- | --- | --- |
| 0 | 4 bytes | `NPD1` |
| 4, 6 | u16, u16 | Version 1 or 2, header length 64 |
| 8 | u32 | Complete payload length, at most 32768 |
| 12, 14 | u16, u16 | Width (8..320, multiple of 8), height (1..200) |
| 16, 18 | u16, u16 | Dictionary count, record size 14 |
| 20 | u32 | Row count `(width / 8) * height` |
| 24, 28 | u32, u32 | Dictionary and row-index offsets |
| 32, 36 | u32, u32 | Original source offset and length |
| 40 | u32 | Strip descriptor offset 64 |
| 44, 46 | u16, u16 | Strip count `width / 8`, flags 3 |
| 48 | 16 bytes | Expected native decode palette |

Packing is header, strip descriptors, dictionary, row indices, complete original
OI chunk, zero alignment padding, history-dependency masks, final zero alignment
padding. Version 2 inserts exactly one zero byte between the row indices and
the OI chunk; version 1 inserts none. Flags 1 and 2 mean that the source
reference and dependency masks are present. Other flag bits are reserved.

The builder chooses the version from the OI chunk's offset within its original
room resource. This matches the reference's byte alignment to the live source
in an even resource allocation, allowing long-word comparisons after an
optional leading byte. Both versions preserve the complete original OI bytes;
unexpected live alignment retains the byte comparison path.

Each dictionary record contains eight mapped pixel bytes, five plane bytes in
the original store order (bits 0, 1, 3, 4, 2), and a zero pad byte. Row indices
are u16 byte offsets into the dictionary, in strip-major order `strip * height
+ y`. They refer to record starts, rather than record numbers.

Each eight-byte strip descriptor contains an original codec offset (u32),
consumed source length including the codec byte (u16), and a flags word (u16).
Only bit 7 is set when any first-column pixel depends on prior decoder history.
Admitted decoding fuses backup and history updates with the masked primary
copy, preserving the original caller state. Rejected cases run the original
decoder and post-decode tail.

Dependency masks follow the aligned end of the source reference. Each strip
has `ceil(height / 8)` bytes. Bit `7 - (y & 7)` identifies a first-column COPY
pixel: its live history byte must equal the predicted row's first pixel before
the decoder shortcut may run. The source reference and live palette must also
match. Other cases retain the original decoder.

The builder verifies the derived data offline and pins the complete generated
file's SHA-256 in the engine manifest. Runtime admission trusts those prepared
pixels, as it trusts prepared voice PCM. It checks structural bounds, alignment
and row-index limits without repeating the payload checksum or decoding the
whole source. The directory checksum remains available for offline diagnostics.
An in-bounds change to prepared pixels is not guaranteed to disable the cache.

Decode admission compares the live compressed source, palette and COPY history.
Plane conversion additionally compares each live eight-pixel row with its
immutable reference. Missing data, failed allocation or rejected admission
retains the original rendering path.

The compiled costume arena is allocated before ART and the original game's
resources. Shutdown clears ART admission before releasing that arena. Guard
memos retain whole-allocation proofs only while live resource headers, owners,
LUT, caller stack and image generation still match. This relies on Exec keeping
simultaneously live allocations disjoint; tests do not invent overlapping OS
allocations after admission.
