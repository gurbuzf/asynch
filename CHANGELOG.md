# Changelog

All notable changes to ASYNCH are recorded here, newest first.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Every entry says **whether numerical results change**. Results are checked with
`tests/regression/run_examples.py` (see `docs/guide/09_reproducibility.md`).

## [Unreleased]

### Fix B-06: link count wrong above 65 535 links

*Results:* unchanged (bit-identical to the previous commit with 1 process).

#### Fixed
- `src/asynch_interface.h/.c`: `Asynch_Get_Num_Links` returned an `unsigned short` (at most 65 535), so for larger
  networks programs using the library got a wrong number (70 000 links reported as 4 464). It returns `unsigned int`.
  The command-line program never used this function.

#### Added
- `tests/data_generators/make_synthetic_network.py`: writes a complete model-190 setup for a synthetic network of
  any size, used to test networks with more than 65 535 links.

### Fix B-15: a missing output folder no longer loses results silently

*Results:* unchanged. Every output file is bit-identical to the previous commit (1 process); the sanitizer build is clean.

#### Fixed
- `src/config_gbl.c`: before computing, ASYNCH checks that the folders of the hydrograph, peak-flow, snapshot and
  temporary files exist and are writable. If not, it stops at once with
  `Error: cannot write the hydrographs: the folder "X" does not exist or is not writable. Create it before running.`
  Before, it computed the whole simulation, printed errors while writing, and ended with exit code 0 and no results.
- `src/asynch_cli.c`: if writing the final results fails anyway (a folder removed during the run, a full disk),
  `asynch` ends with an error exit code and `Error: some results could not be written.`
- Tested: a missing folder stops in 0.4 s with exit code 1; a read-only folder (as a normal user, in Docker) stops
  likewise; a folder deleted during a run gives exit code 1 at the end.

### Guide reorganised as a learning path, for readers who do not program

*Results:* no change to the model.

#### Added
- `docs/guide/00_what_is_asynch.md`: what the model computes, what a run is, and the vocabulary, without code.
- `docs/guide/02_running_the_model.md`: the command and its options, the examples, every block of the global
  file, the input files, an exercise (change the runoff coefficient and compare), reading and plotting results,
  and the messages ASYNCH prints, with what to do.
- `docs/guide/07_improvements_explained.md`: every problem found, in plain words, classified as Critical / High /
  Medium / Low with the reason, and before/after figures.
- `tools/python/plot_hydrographs.py`: plot one link from up to three hydrograph files (`.dat`, `.csv`, `.h5`).
- `docs/guide/figures/exercise_runoff_coefficient.png`.

#### Changed
- `docs/guide/01_setup.md` (was `01_build_and_run.md`): step-by-step setup with three options: Ubuntu 24.04 or
  WSL2, Docker, other systems. Each step says what success looks like, and there is a troubleshooting table.
  **Option A was tested by running its commands verbatim on a fresh Ubuntu 24.04 container**, as a normal user
  with sudo. That test found two problems, now fixed. The Python packages must come from `apt` (Ubuntu 24.04
  refuses `pip install` into the system Python). `ca-certificates` must be installed on minimal systems, for `git clone`.
- Chapters renumbered to follow the learning path: code map 3, solver 4, model 254 5, C primer 6, known issues 8,
  reproducibility 9. All links were updated.
- `README.md`: points newcomers to the guide.

#### Fixed
- `tests/regression/run_examples.py`: a relative path given to `--asynch` or `--compare-to` failed, because the
  examples run in other folders. Paths are now made absolute. Found by the fresh-machine test.

#### Known issue recorded
- B-15 (High, open): if an output folder does not exist, ASYNCH prints errors but finishes with a success exit
  code and writes no results.

### Working Docker image

*Results:* no change to the model.

#### Changed
- `Dockerfile`: rewritten on Ubuntu 24.04. The old one used Fedora 34, which reached end-of-life in 2022;
  it could not be tested here because this environment's network blocks the Fedora registry. The new
  image installs all dependencies, compiles ASYNCH, runs `make check`, installs `asynch`, and works as a
  normal user with id 1000. Tested here: the image builds; the examples run inside it; the full regression
  suite passes with 1 and 2 processes; results written into a mounted folder belong to the host user
  (also with `--user <uid>:<gid>`).
- `.dockerignore`: replaced a generic template with rules for this project (no host build files, no
  output files; the reference results are always included).

#### Removed
- `docker_config_files/`: helper for the old Dockerfile, no longer used.

#### Fixed (documentation)
- The build needs a **Fortran compiler** (`gfortran`): `configure` checks BLAS with a small Fortran program.
  The package list in `docs/guide/01_setup.md` did not include it, and a clean Docker build failed
  without it.

### Model 254: original baseflow equation restored (S-02) — **results change**

*Results:* **model 254 results change** (intended). All other models are unchanged: bit-identical to the
original code with 1 process. With this change, **all six reference result files shipped with the original
ASYNCH repository are reproduced**:
- `test`: hydrographs, peaks and final states. This was already the case.
- `clearcreek`: hydrographs within 9.5e-5 m³/s, final states within 1.5e-5, peaks within 1.7e-4 m³/s.
  Before this change the hydrographs differed by up to 0.085 m³/s.

The same holds at 1, 2 and 4 processes.

#### Changed
- `src/models/equations.c` (`model254`): the baseflow outflow used `max(0.001, q_b)` instead of `q_b`.
  That line was added in January 2021 in a commit titled "added model 194" (`93241a3`); it is not in the
  original model or in its documentation. When baseflow fell below 0.001 m³/s, the channel lost baseflow
  as if it were 0.001 m³/s, so baseflow emptied too fast and was then forced to 0. Decision of the model
  owner: restore the 2015 equation, `q_b = y[6]`.
- `tests/regression/run_examples.py`: the case `clearcreek, 2015 configuration` now passes. It is compared
  with its reference at the solver's own tolerance (1e-4), and peak values at 2e-4. Peaks are recorded only
  at the end of solver steps, so 9 of 6 359 links, whose crest fell between steps, differ by up to 1.7e-4.
  Cases can declare an intended difference from the original code (`changed_vs_original`); the difference
  is then reported without failing.

### Fix B-09, B-10: debug output of models 402/403, missing prototype

*Results:* unchanged. Every example is bit-identical to the original code with 1 process.

#### Fixed
- `src/models/check_state.c`: the dam checks of models 402 and 403 had `debug = 1` and printed a line
  at every call (every time step of every dam link), flooding the output and slowing runs. Debugging is
  now off by default; the `printf` of an `unsigned int` with `%f` was corrected (B-09, B-10).
- `src/forcings_io.h`: `Create_Rain_Data_Par_IBin` (binary forcing files, flag 2) was called without a
  prototype, so the compiler could not check its arguments. The prototype is now declared (B-10).
  No compiler warnings remain in these two files.

### Regression tests against all reference results of the original repository

*Results:* no change to the model (examples and tests only).

#### Added
- `examples/test_2015.gbl`, `examples/clearcreek_2015.gbl`, `examples/out_2015/`: the configurations
  that produced the reference results shipped with ASYNCH (`examples/results/*.dat`, `*.pea`, `*.rec`,
  commit `b73fc2d`, May 2015), written in today's global file format: 300 and 6000 minutes from
  2014-05-01, `.dat` hydrographs every 5 minutes, `.rec` final states. The input files are unchanged
  since 2015.
- Two regression cases running them. All six original reference files are now checked:
  - `test`: `.dat`, `.pea` and `.rec` are **reproduced** (largest hydrograph difference 5e-7).
  - `clearcreek`: **not reproduced**, known mismatch. Restoring one line of model 254 to its 2015 form
    reproduces them within the solver tolerance (largest difference 9.4e-5, solver abs tolerance 1e-4).
    The floor `max(0.001, q_b)` in the baseflow equation was added in January 2021 (commit `93241a3`,
    "added model 194") and changed model 254's results. The model code is left unchanged: whether to keep
    the floor is a modelling decision (issue S-02).

#### Changed
- `tests/regression/run_examples.py`:
  - compares `.dat` and `.rec` files;
  - compares the time of each peak with its own tolerance (`--peak-time-atol`, default 20 min), because
    the minute of a flat maximum is ill-conditioned; peak values keep the normal tolerance;
  - uses `atol` 1e-3 by default with several MPI processes (1e-5 with one). Three 4-process runs of the
    unchanged original code differed from each other by up to 1.15e-4 on the 6000-minute clearcreek run.
    The strict test stays the 1-process run, which must be bit-identical;
  - creates the output directories of each case.
- `docs/guide/09_reproducibility.md`: the reference files of the original repository are the benchmark
  and are never modified. It also documents the 2015 configurations and the tolerance policy.
- `docs/guide/08_known_issues.md`: R-02 explained, S-02 history. R-03 unchanged (benchmark kept).

### Fix B-14 and B-05: `.rkd` files (tolerances and method per link) work again

*Results:* unchanged for every existing example (bit-identical to the original code with 1 process,
within tolerance with 2). The `.rkd` option, which never finished before, now works. An `.rkd` file
repeating the global settings gives bit-identical results to the global file (1 process).

#### Fixed
- `src/riversys.c` (`Build_RKData`): reading an `.rkd` file hung in an endless loop (`j` loop
  incrementing `i`). The method-index array was too small, the wrong variable was broadcast to the
  other processes, the per-link tolerance structure was never allocated, and link ids were ignored.
  The reader was rewritten: rows are matched to links by id, and every value is checked with a clear
  error message.
- `src/system.c` (`Destroy_ErrorData`): freed the addresses of struct fields instead of the arrays
  (B-05). It now frees the arrays and the structure.

#### Added
- `docs/input_output.rst`: the `.rkd` format, which was undocumented.
- `examples/test_rkd.gbl`, `examples/test.rkd`: the `test` example with tolerances from an `.rkd` file.
  It is a new regression case, checked against `examples/results/test.pea`.
- `tests/regression/run_examples.py`: `--timeout` (default 600 s) kills a run that does not finish and
  reports it as a failure. Cases can declare that the original code cannot run them.

### Fix B-12: `.uini` files with too few values used uninitialised memory

*Results:* unchanged. Bit-identical to the original code with 1 process (clearcreek: bit-identical
to the previous commit, since the original cannot run it on 1 process). Within tolerance with 2.

#### Fixed
- `src/riversys.c` (`Load_Initial_Conditions_Uini`): the check for missing values tested
  `fscanf(...) == 0`, but at end of file `fscanf` returns `EOF`. A short file was silently accepted and
  the missing states kept uninitialised memory. Now: the values start at 0, a short file gives a
  warning (`Warning: clearcreek.uini gives 4 initial value(s), model 254 has 7. ...`), a non-number is an
  error, and a model number in the file that differs from the `.gbl` gives a warning.
- This affected the examples: models 258 and 259 read 4 values from `examples/more/common/test.uini`,
  which has 3. Their 4th state was uninitialised memory that happened to be 0. It is now 0 by design.

#### Changed
- `examples/clearcreek.uini`: model number corrected (252 → 254) and all 7 states given. Model 254
  computes states 4–6 itself, so results are identical.
- `docs/guide/01_setup.md`: explains the `.uini` format.

### Fix B-13: solver methods 0 and 1 used freed memory

*Results:* **unchanged for method 2** (Dormand–Prince, used by all examples): bit-identical to the
original code with 1 process, within tolerance with 2. **Methods 0 (RK 3(2)) and 1 (RK 4(3)) change
completely:** they used to produce unreliable results or run forever, and now work.

#### Fixed
- `src/solvers/rk3_2_dense.c`, `src/solvers/rk4_3_dense.c`: the Butcher tables (`A`, `b`, `c`, `d`, `e`)
  were local arrays, but the method kept pointers to them after the function returned
  (AddressSanitizer: `stack-use-after-return`). Every step then read leftover stack memory. With
  method 1, `examples/test.gbl` hung in most runs, in the original code too. The tables are now `static`.
- Verification: `test` and `clearcreek` with methods 0, 1 and 2, on 1 and 2 processes, release and
  sanitizer builds: all 24 runs finish, with no sanitizer reports. Methods 0 and 1 are bit-reproducible
  with 1 process. Against method 2, peak discharges agree within 7.7e-4 m³/s (median relative
  difference ~0.1 % on clearcreek), the expected accuracy for solvers of order 3, 4 and 5 at these tolerances.

### Fix B-04: invalid numerical solver index crashed ASynch

*Results:* unchanged (bit-identical to the original code with 1 process, within tolerance with 2).

#### Fixed
- `src/riversys.c` (`Build_RKData`): the numerical solver index read from the global file (or from a
  `.rkd` file) was never checked. Indices 3 and above caused a segmentation fault. ASYNCH now stops
  with: `Error: numerical solver index 4 in the global file is not valid. Use 0 (RK 3(2)), 1 (RK 4(3))
  or 2 (Dormand-Prince 5(4)).` Index 3 (Radau IIA) is refused because its implicit solver is not compiled.

#### Changed
- The comment `%Numerical solver index (0-3 explicit, 4 implicit)` in all example `.gbl` files and in
  `docs/input_output.rst` was wrong. It now reads `(0 = RK 3(2), 1 = RK 4(3), 2 = Dormand-Prince 5(4))`.
  `docs/builtin_options.rst` explains that index 3 cannot be selected.

### Fix B-02, B-07, B-08: HDF5 snapshot writer

*Results:* unchanged with 1 process (every example bit-identical to the original code). With 2 or
more processes, **snapshot** values below 1e-12 computed by processes other than 0 are now set to 0,
as they already were on process 0. Snapshots no longer depend on the number of processes. Hydrographs
and peak flows are not affected. All differences from the original are below 1e-5 (absolute).

#### Fixed
- `src/processdata.c` (`DumpStateH5`):
  - the model's output filter (`OutputConstrainsHdf5`) was applied only to the links owned by
    process 0; it is now applied to every link (B-02). In a 2-process clearcreek run, 4 values
    in (0, 1e-12) were left unfiltered before; none are now.
  - the filter worked directly on packed records, i.e. on misaligned `double`s (undefined
    behaviour, 21 UBSan reports over the examples). States are now filtered in an aligned array
    and then copied into the record (B-08). UBSan reports: 0.
  - the search for process 0's first link could run past the end of the array, and the packing
    buffer was never freed (a leak at every recurrent snapshot). Both are fixed (B-07).
  - links with a different number of states now stop the run with a clear error instead of
    writing past the record.

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
- `docs/guide/09_reproducibility.md`: how to use it, and what to expect. With 1 MPI process
  the same code is bit-for-bit reproducible. With 2 or more processes, two runs of the same
  code differ by up to ~1e-6 (relative), because of the asynchronous scheduling.

### 2026-09-25: documentation, regression tests, example fixes

No change to the C source code: the model computes exactly what it computed before.

#### Added
- `docs/guide/`: a learner/developer guide covering building and running, a code map,
  the numerical method, model 254 equation by equation, a C primer and reproducibility.
- `docs/guide/08_known_issues.md`: known issues. 12 bugs (4 confirmed by running the code,
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
