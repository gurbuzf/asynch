# Work log

Newest first.

## 2026-09-28: release 1.7.0, solver how-to, GitHub Pages source

- 1.7.0 released (run 36394890399): stiff solver, no start-up pause. Version 1.7.0 not 1.6.1 (new feature).
- Owner: docs never said how to switch solvers ("index 2" unexplained). Added guide section 2.4 (what the index is,
  table, before/after .gbl, tolerances / 100, Python), links from ch. 4, references, release notes, home page.
- Docs site broken: Pages source was "Deploy from a branch", so a Jekyll build of the raw branch raced the Sphinx
  deployment on every push. Owner switched Source to "GitHub Actions" (not root, not /docs: the HTML is only built
  by the Documentation workflow). Check after each push that no "pages build and deployment" run appears.

## 2026-09-27 (later): P-01, stiff solver, Tiger/HydroLegion review

- P-01 removed (48b2b40): init 1.3 s -> 0.27 s, examples bit-identical np=1.
- Solver index 4 = Rodas5P (14e4a92). Model 254, 6 359 links, 100 h, errors vs tol 1e-8 run:
  DOPRI 11.3 s / 5.44 M steps / 21 % rejected / err 4.0e-5; Rodas5P same tol 0.69 s / 189 k / 5.4 % / 5.6e-3;
  Rodas5P tol x0.01 1.71 s / 465 k / 2.2 % / 7.8e-5 (peak err 6.7e-5 vs 3.4e-4). Guidance: divide tolerances by 100.
- CI: wheel job (Ubuntu 20.04, libcheck 0.10) lacked ck_assert_ptr_nonnull -> use ck_assert_ptr_ne(.., NULL).
- Tiger-HLM (MIT, Princeton): GPU runoff only (own Runoff5 model, RK45 + Radau per hillslope, NetCDF/YAML);
  routing separate CPU/OpenMP repo, channel RHS same form as 254 link equation. HydroLegion-HLM (MIT, Perez,
  v0.3.0): pure Python; GPU tier = fixed-step RK4 or exponential/IMEX step, float32 default, families 204/205
  only, sparse-matmul routing, ensemble axis. Neither implements ASYNCH 254 as-is; reuse = ideas, not code.
- GPU prototype on hold (owner).

## 2026-09-27: units audit fixes, 1.6.0, GPU investigation

- Units audit of every model (report delivered to the owner as PDF, not in the repo). Owner: "fix all as you
  suggested". Fixed B-28..B-35; open items recorded B-36, S-08..S-12; docs D-01..D-07 fixed. 21 new unit checks
  (fail on old code exactly for the affected models). np=1 bit-identical except 258/259 (declared intended).
- Owner rules added: (1) release texts (GitHub release, PyPI page, release notes, home page "what's new") give a
  general summary only; specifics only in CHANGELOG entries. The first paragraph of each CHANGELOG version is the
  public summary (release.yml and setup.py publish only it). (2) Do not name Clear Creek in general docs/code; only
  in test/evaluation contexts. Use my_basin.gbl in examples.
- PyPI 1.5.0 was published by the owner's run 3 (pypi_only). 1.6.0: pip install asynch-hlm everywhere.
- Speed measurements (4-core sandbox, model 254, 6 359 links, 100 h): computation 6.3 s np1, 3.4 s np2, 2.0 s np4;
  init ~1.3 s of which 1 s sleep (P-01). Callgrind: solver bookkeeping ~67 %, model equations ~28 % (pow ~17 %),
  I/O+MPI < 2 %. -march=native / LTO: 9 % slower and not bit-identical. Tolerance 1e-4 -> 1e-2: only 9 % fewer
  steps; 21 % of steps undone: step size limited by stiffness, not accuracy -> implicit / exponential methods are
  the big algorithmic lever. GPU precedent: Tiger-HLM (hillslopes on GPU, routing on CPU OpenMP); HydroLegion-HLM
  (full GPU, ensemble axis; could not open Zenodo from sandbox).
- GPU plan (not started, owner to decide): see answer of 2026-09-27; hillslope/routing split for models where the
  hillslope does not depend on the channel (254 and most Top Layer models); level-synchronous routing; ensemble axis.

## 2026-09-26: parallel runs from Python, PyPI (owner question)

- Parallel already worked (mpiexec -n N python script.py); added asynch.run_parallel / run_script_parallel for
  notebooks (start mpiexec). Found: multi-process tests compared printed lines, which Open MPI can cut into each
  other (likely the unexplained single failure earlier): tests now read one file per process.
- PyPI: "asynch" is taken (ClickHouse driver) -> distribution renamed asynch-hlm (import asynch). Trusted
  Publishing job in release.yml, gated by repo variable PUBLISH_TO_PYPI; setup steps in docs/contribute.rst (owner
  must create the PyPI account / pending publisher). twine check passes.

## 2026-09-26: ready-made Linux wheel (owner: "serve it built in")

- Wheel carries libasynch.so + the asynch program + HDF5/libpq/... (auditwheel); MPI from PyPI `mpich` (dependency,
  gives mpiexec). Ubuntu's MPICH is PMIx-built (singleton only with hydra) and Open MPI loads plugins: both unusable.
- Built in ubuntu:20.04 (manylinux_2_31); quay.io and AlmaLinux mirrors are blocked in the sandbox, so manylinux_2_28
  (RHEL 8) was not possible to test. Tested in bare containers: Ubuntu 20.04/24.04, Debian 11/12; with gcc+numba+mpi4py
  all 70 tests pass.
- Found A-02 (RTLD_GLOBAL made HDF5 symbols global: h5py import failed). Fixed. Test fixes: Open MPI-only flags,
  HDF5 compare by content (creation times).
- One unexplained failure in a first venv test run (not saved); not reproduced in 23 runs.

## 2026-09-26: documentation redesign and release 1.5.0 (owner request)

- Pages deployment verified (run 36223745641, attempt 2, deploy job succeeded after Pages was enabled).
- Owner: docs hard to follow, text drawings and symbols unreadable; make it modern, then release with a tag.
- 13 SVG diagrams in `docs/guide/diagrams/` (built from scratch-pad generator scripts, checked in light and dark by
  screenshots); `_ext/asynch_docs.py` inlines them so they follow the theme. CSS components: meta row, lead, steps,
  timeline, "You should see", C lesson, badges, stat tiles, cards, hero. Maths typeset (verified with a local MathJax 4,
  the CDN is blocked in the sandbox).
- Found and fixed while reviewing: the built-in models table rendered as raw text; LaTeX leftovers
  (`[sec: ...]`); chapter 8 table had status in the Severity column; stale counts (68 -> 70 Python tests; 22 -> 23 C
  tests; 43 000 -> 36 000 lines); `make dist` omitted `python/` (Python tests failed from the tarball).
- While testing the release archive, one `make check` run (-O2 build) never finished in the all-models loop. Valgrind:
  B-26 (models 105, 263 leave derivatives unset; values from the work array) and B-27 (consistency check reads
  non-dense parent states uninitialised). Fixed; unit test now fills `ans` with NaN and flags unset derivatives (finds
  exactly 105 and 263). Open question S-07 (intended equations). np=1 bit-identical; ASan clean; valgrind clean.
- Release 1.5.0: version bump, CHANGELOG section, release notes, `.github/workflows/release.yml` (tag -> build, test,
  tarball + wheel + docs zip, GitHub release). np=1 bit-identical to the previous build; make check passes; the
  tarball builds and passes make check on its own.

## 2026-09-26: Python speed, MPI, library packaging, cleanup, documentation website (owner request)

- Profiled Python models: 21 us/call, of which ~17 us building NumPy views (ctypes); user code 3 us. Cached views by
  address (bounded cache) -> 4x faster. Added jit="numba" (numba.cfunc with the C signatures): 0.13 s vs 0.10 s
  built-in on bench5k, bit-identical. Tests include numba when installed.
- MPI from Python measured (4 cores): Clear Creek 8.0 -> 2.75 s; 50k fishbone 2.0-2.8x. mpi4py test added.
- Library: make install-python target, pyproject extras; explained design (thin ctypes layer over libasynch.so).
- Cleanup: M-01 dead code + ide/, conda/, travis, rtd, workspace, cluster scripts, LaTeX manual, tracked Makefile.in,
  pycache; fresh copy builds and passes make check.
- Docs site: Sphinx + furo + MyST + autodoc + breathe (Doxygen), 0 warnings; GitHub Pages workflow and tests workflow
  (not run yet: they run on GitHub after push; Pages must be enabled by the owner: Settings > Pages > GitHub Actions).
- Needed from owner: enable Pages; check the first Actions runs.

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
