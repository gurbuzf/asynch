# Work log

Newest first.

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
