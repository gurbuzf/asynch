# Work log

Newest first.

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
