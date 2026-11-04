# Mask-plane byte RLE

The generated decoder preserves every source BYTE read and destination BYTE write in order. Literal packets retain the scalar loop. Repeat packets shorter than eight bytes retain the scalar loop; longer packets use eight ordered BYTE stores at forty-byte strides. There are no WORD/LONG data accesses, prefetch reads, allocation, persistent cache or new save-frame writes. Thus source/output overlap and volatile byte I/O retain the original bus-operation sequence; operation timing changes with the optimization.

Height zero and packet count zero both represent 256 rows in the original instructions. The last decrement returns D1=0 and CCR Z=1, N/V/C/X=0. Literal packets leave D0 unchanged; repeat packets replace only its low byte. D2-D4 and the original twelve-byte stack frame are preserved.

The patch appends one code HUNK, gives its three absolute operands H2 relocations, and retargets the existing terminal JMP at H0+4DE2. H0+15338 and all direct callers of that original decoder remain intact. The generator checks the exact gateway bytes and rejects interior branch or relocated code-pointer entries.

`test_kernel.py`, `test_flags.py`, and `test_linked.py` use generated synthetic inputs. The linked test executes actual H0+4B80 -> H0+4DE2, loads all real HUNK relocations and verifies ordered byte I/O, including a volatile FIFO model. Optional `test_corpus.py <native-planar.dat>` uses a privately generated artifact; it does not contain artwork.

Short repeat packets pay two additional dispatch instructions. Synthetic all-one-repeat streams can regress by 16.6% in instruction count. The bounded prepared-image corpus measured 2,859 columns across 514 objects: 49.4% fewer instructions overall, 506 objects improved and eight regressed (worst object +4.35%). Five columns whose decoded source prefix exceeded the declared OI span were excluded. This is one execution per column, not gameplay frequency weighting or an exhaustive whole-game claim.
