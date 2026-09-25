# Changelog

All notable changes to ASYNCH are recorded here, newest first.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Every entry says **whether numerical results change**. Results are checked with
`tests/regression/run_examples.py` (see `docs/guide/06_reproducibility.md`).

## [Unreleased]

### Fix B-03: output file closed twice at shutdown

*Results:* unchanged. Bit-identical to the original code with 1 process for every example;
within tolerance with 2 and 4 processes.

#### Fixed
- `src/asynch_interface.c` (`Asynch_Delete_Temporary_Files`, `Asynch_Free`): the temporary output
  file was closed twice (undefined behaviour), so every debug build (compiled without `-DNDEBUG`)
  aborted at the very end of a run with `free(): double free detected` (exit code 134). The
  pointer is now reset after closing. Debug builds, and the AddressSanitizer build, now run all
  examples cleanly.

### Fix B-01: heap buffer overflow in model 254 snapshots

*Results:* unchanged. Checked against the original code (commit `84da43a`) with
`run_examples.py --compare-to`: every example is bit-identical with 1 process (27/27 files for
`test`, 3/3 for models 192, 196, 258, 259), and within tolerance with 2 and 4 processes. For
`clearcreek` with 2 processes, all 27 output files are bit-identical. With 1 process the original
crashes. Instead, the new 1-process run was compared with the original 2-process run: all 27
files are within tolerance.

#### Fixed
- `src/models/definitions.c` (`SetOutputConstraints`): `case 254` had no `break;` and fell through
  to `case 256`, so model 254 used the 8-state snapshot filter on 7-state records. That wrote
  past the end of the snapshot buffer (heap buffer overflow, found with AddressSanitizer).
  `examples/clearcreek.gbl` crashed on 1 MPI process (`Fatal glibc error: malloc.c`); it now runs.

#### Changed
- `tests/regression/run_examples.py`: when the original executable crashes, the files it left
  half-written are skipped instead of being reported as differences.

### Regression harness: comparison with the original code

*Results:* no change to the model (test tooling only).

#### Added
- `tests/regression/run_examples.py --compare-to ASYNCH`: runs a second executable (normally
  the original code) on identical copies of the examples and compares **every** output file
  (peak flows, hydrographs in `.csv`/`.dat`/`.h5`, all snapshots). Reports bit-identical files
  and the largest difference of the others. `--verbose` lists each non-identical file.
- `tests/regression/build_original.sh [COMMIT] [DEST]`: builds an unmodified copy of a commit
  (default `84da43a`, the original code) to compare with.
- `docs/guide/06_reproducibility.md`: how to use it, and what to expect. With 1 MPI process
  the same code is bit-for-bit reproducible. With 2 or more processes, two runs of the same
  code differ by up to ~1e-6 (relative), because of the asynchronous scheduling.

### 2026-09-25: documentation, regression tests, example fixes

No change to the C source code: the model computes exactly what it computed before.

#### Added
- `docs/guide/`: a learner/developer guide covering building and running, a code map,
  the numerical method, model 254 equation by equation, a C primer and reproducibility.
- `docs/guide/05_known_issues.md`: known issues. 12 bugs (4 confirmed by running the code,
  including a heap buffer overflow in the flagship `clearcreek` example), 5
  reproducibility issues, the broken Python API, dead code, performance hypotheses,
  6 scientific review items and 3 documentation errors, each with file:line and evidence.
- `tests/regression/run_examples.py`: runs every example and compares hydrographs,
  peak flows and snapshots with the stored benchmarks, using a tolerance (atol 1e-5,
  rtol 1e-4). It reports max abs/rel differences, treats crashes as failures, and marks
  the two unreproducible references as known mismatches (XFAIL).
- `CHANGELOG.md` (this file).

#### Fixed
- `examples/more/model_258/test258.gbl`, `examples/more/model_259/test259.gbl`: the
  evaporation file pointed to an absolute path on the original developers' cluster
  (`/Dedicated/IFC/...`). It now points to `../common/evap.mon`, like the other examples.
  *Results:* model 258 now runs and reproduces its benchmark bit for bit. Model 259
  runs, but does not match its benchmark (issue R-03: the 2018 code gives the same
  output as today's, so the benchmark was produced with inputs that are not in the repository).

#### Baseline
Release build `-O3 -DNDEBUG`, GCC 13.3, OpenMPI 4.1.6, HDF5 1.10.10, commit `84da43a` + the fix above:

| case | np=1 | np=2 | np=4 |
|---|---|---|---|
| test (190) | PASS | PASS | PASS |
| clearcreek (254) | FAIL: crash, B-01 | XFAIL, R-02 | XFAIL, R-02 |
| model_192 | PASS | PASS | PASS |
| model_196 | PASS | PASS | PASS |
| model_258 | PASS | PASS | PASS |
| model_259 | XFAIL, R-03 | XFAIL, R-03 | XFAIL, R-03 |

## [1.4.3] and earlier
See `docs/release_notes.rst`.
