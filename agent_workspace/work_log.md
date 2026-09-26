# Work log

Newest first.

## 2026-09-25: link count, Python API, tests, README (owner request)

- Link count above 65 535 (B-06) fixed earlier; now also covered by a Python test on a 70 000-link network.
- New C interface `src/asynch_api.h/.c` (arrays + opaque handles, model specification). Fixed on the way:
  B-17..B-21. Model 190 re-implemented through it: bit-identical to built-in (np=1).
- Python package `python/asynch` (ctypes): Simulation, Model (C-code backend compiled/cached, Python backend),
  GlobalConfig, io, `python -m asynch`. Old py/ and asynchdist*.py removed (A-01 resolved).
  Measured: C-code model 0.12 s vs built-in 0.11 s vs Python 16 s (5 000 links, 2 h). Runs from Python are
  byte-identical to the CLI; custom model 191 port reproduces built-in 191 exactly.
- Tests: tests/check_asynch.c 22 unit tests (found B-22 DOPRI b' typo, B-23 param overflow in 263/601-603,
  B-24 models without equations + static shared RK tables); tests/python 62 tests; make check runs
  C + Python + regression (45 s). All clean in release and ASan builds; examples bit-identical to previous commit.
- Findings not fixed: .rec files hold 7 significant digits, so a restart from .rec is not exact (h5 is);
  documented in chapter 10 tests. Model 263 now needs 16 disk params per link (was declared 15).
- Docs: chapter 10 (Python), README rewritten, 01/03/07/08/09 updated, docs/python_api.rst rewritten,
  Dockerfile (ldconfig, PYTHONPATH).
- Verified: Docker image builds (make check inside passes; Python examples run as user hydro). Chapter 10 option (b)
  needed python3-setuptools python3-wheel + --no-build-isolation (pip otherwise downloads setuptools; in this sandbox
  PyPI TLS fails) - docs fixed, tested as normal user in the image.
- Coverage (tests/coverage_report.py): 35.9 % -> 66.5 % after adding every-model equation unit test (fork per model;
  exit() not _exit() so gcov flushes), test_all_models.py (52 models; 30/261/601-603 need realistic params) and
  test_forcings.py (found B-25: binary rain files off-by-one/overflow/crash; fixed).
- Found by all-models test and ruled out as test artefacts (not bugs): dam algebraic functions need state -1 from
  check_state; model 257 param 3 is a stream order; model 30 step collapse with generic params.

## 2026-09-25: owner feedback: clarity for non-programmers, plots, Docker, decision A

- Owner chose A: model 254 baseflow restored to 2015 form. All 6 original reference files now reproduced
  (clearcreek_2015 compared at solver tolerance 1e-4; peaks at 2e-4 because peaks are recorded at step ends).
- Owner feedback: work was not understandable to a non-coder; wanted severity classes, before/after plots,
  a clear overview, setup incl. Docker, teaching focus, "do not blindly write code".
  Done: guide reorganised as a learning path (00 overview, 01 setup, 02 running, 03-06 understanding,
  07 fixes explained with Critical/High/Medium/Low, 08-09 technical); figures via
  `tools/python/make_comparison_plots.py`; readers/plot helpers in `tools/python/`.
- Everything verified by running it: Dockerfile built and all tests run inside (found: gfortran needed,
  .dockerignore excluded reference .h5, uid 1000 clash with base image `ubuntu` user); chapter 1 option A
  run verbatim on fresh ubuntu:24.04 as sudo user, cloning from GitHub (found: apt instead of pip,
  ca-certificates, harness relative path bug). Chapter 2 exercise run for real (found B-15).
- B-15 found and fixed (missing output folder → results lost with exit 0).
- Sandbox notes: dockerd must be started manually (`dockerd &`); fresh containers need the sandbox proxy CA
  (/root/.ccr/ca-bundle.crt) for git; the Fedora registry is blocked.
- Next: B-06, B-10 indentation, M-01 attic, CI, B-11.

## 2026-09-25: Phase 2 (fix), first part

Owner instructions: develop only on `modernization`, never merge to `master`, no PRs; apply the
recommended option for every open decision; after every code change run all examples and compare
with the original code; keep user documentation current.

- Harness: `--compare-to` (every output file vs the original build), `build_original.sh`, `--timeout`.
  Finding: with 1 process the code is bit-reproducible; with ≥2 processes two runs of the *same* code
  differ by up to ~1e-6 relative. Standard adopted: bit-identical at np=1, within tolerance at np≥2.
- Fixed, each verified bit-identical to the original at np=1 (except where noted) and sanitizer-clean:
  B-01, B-03, B-02+B-07+B-08, B-04, B-12, B-13, B-14+B-05.
- New bugs found while fixing:
  - B-13: RK 3(2)/RK 4(3) Butcher tables were stack locals (methods 0 and 1 unusable, hang).
  - B-14: `.rkd` reader had 5 defects (endless loop, wrong broadcast, no allocation, ...).
  - B-12 revealed that models 258/259 read an uninitialised 4th initial state from `common/test.uini`.
- Helper used for every change (scratchpad, not in repo): rebuild release + ASan builds, run the
  harness with `--compare-to` at np 1, 2, 4 and ASan np 1, and grep the ASan np 2 logs for reports.
- Also fixed: B-09, B-10 (except the `riversys.c` indentation).
- Owner clarified: the benchmark is the example results of the original repository. Found the 2015
  configurations behind `examples/results/` (commit `b73fc2d`: 300 / 6000 min from 2014-05-01) and
  added them as `examples/test_2015.gbl`, `examples/clearcreek_2015.gbl`. The `test` references are
  reproduced. The `clearcreek` references are reproduced only without the 2021 baseflow floor in model 254
  (commit `93241a3`). Decision asked (S-02).
- Tolerance policy measured: two 4-process runs of the original differ by up to 1.15e-4 on the
  6000-minute run, so atol is 1e-3 for np>1. Peak times get their own 20-minute tolerance.
- Next: B-06 (`unsigned short` link count), B-10 indentation, M-01 attic, CI (GitHub Actions on
  `modernization`), then B-11 (unchecked `fscanf`).
- Noted for later: neither the `.gbl` path nor any other code checks that the number of tolerances
  covers the model's states (the check in `riversys.c` is commented out); `find_link_by_idtoloc` is a
  hand-written binary search (TODO says replace by `bsearch`).

## 2026-09-25: Phase 1 (understand)

- Built on Ubuntu 24.04 (GCC 13.3, OpenMPI 4.1.6, HDF5 1.10.10). Ran every example with
  release, debug and ASan/UBSan builds.
- Confirmed by running: B-01 (heap overflow, clearcreek crashes on 1 process), B-03 (double
  `fclose`), B-04 (solver index 3/4 segfault), B-08 (misaligned access). Others found by code reading.
- R-03: built commit `cba763b` (2018). Model 259 output is identical to today's, so the
  benchmark was made with inputs that are not in the repository.
- Fixed the example paths for models 258/259; model 258 is now bit-identical to its benchmark.
- Wrote `tests/regression/run_examples.py`, `docs/guide/`, `CHANGELOG.md`.
- Housekeeping: a PR was opened on upstream by mistake and closed (Iowa-Flood-Center/asynch#78).
  The work branch was renamed to `modernization`, which is now the fork's default branch.
  Plans and status live only in `agent_workspace/` from now on.
- Waiting on: the open decisions in [roadmap.md](roadmap.md).
