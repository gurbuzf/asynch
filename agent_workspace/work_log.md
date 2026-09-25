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
- In progress: B-09/B-10 (debug prints in `check_state.c`, missing prototype in `forcings_io.h`), then
  B-06, B-10 indentation in `riversys.c`, R-02/R-03 references, M-01 attic, CI.
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
