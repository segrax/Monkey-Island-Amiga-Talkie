# Validation

The C++ builder was compiled with MSVC 19.50 on Windows x64 and GCC 11.4 on Ubuntu 22.04 x64. Both passed the CTest payload and binary-format self-tests.

Both platforms generated the expanded and standard profiles from the owned original Amiga data, original executable/disk 1 ADF, and corresponding SOU. The engine, loader, worker, map, prepared speech and room files match the pinned reference hashes. The expanded profile reproduces the user-tested hybrid package. Paths containing spaces and Unicode were exercised.

The Windows smoke script checks every output manifest hash, verifies the pinned engine/map/PCM/worker/room files, and rejects existing outputs, unsupported speech archives and invalid executable inputs. The Linux smoke script runs an isolated copy of the executable, checks output file hashes and exercises the same rejection paths. Invalid inputs are rejected before a playable output folder is created.

Windows dependency inspection shows only system DLLs; no .NET, Python, Visual C++ redistributable or separate patch files are required at runtime. The Linux executable uses the normal glibc/libstdc++/libgcc/libm system libraries.

These checks validate the builder and byte-identical generated game files. They are not a new game playthrough, GUI usability test, or claim of stock A500 performance. The standard SOU profile intentionally omits the 16 supplemental mapping keys absent from its source archive.

Run `ctest --test-dir <build-folder> -C Release --output-on-failure` for source self-tests. Use `source/tests/Smoke.ps1` on Windows or `source/tests/smoke.sh` on Linux for integration checks with your own supported game inputs. No proprietary fixtures are needed for the C++ builder tests.
