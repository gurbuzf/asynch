# 8. Prompts for the next phases

Ready-to-use task descriptions for an AI coding assistant (or a human contributor).
They are designed to be **self-contained, verifiable and hard to misread**. Each one
states the context to load, the exact scope, the constraints, the verification and
the definition of done. Copy one, adjust the bracketed parts, and paste it.

Why they are written this way:
* **Context by file path, not by summary.** The assistant reads the audit itself instead of trusting a paraphrase.
* **Explicit non-goals.** They prevent "helpful" extra changes in scientific code.
* **Verification is part of the task.** A fix without a before/after harness run is not done.
* **One issue per prompt.** Small, reviewable commits, and an easy revert if needed.

---

## P2-a. Fix one confirmed bug

```text
Role: careful C maintainer of a scientific hydrological model (ASYNCH, C99 + MPI).

Context to read first:
- docs/guide/05_known_issues.md, item [B-01]   <- change the id
- docs/guide/06_reproducibility.md (regression harness and rules)
- the source lines cited in that item

Task: fix [B-01] only.

Constraints:
- Minimal diff; do not reformat, rename or refactor anything else.
- Do not change equations, parameters or numerical methods.
- If the fix could change numerical results, stop and explain why before editing.

Verification (paste outputs in your final message):
1. Build a release build (-O3 -DNDEBUG) and an ASan build
   (-O1 -g -fsanitize=address,undefined) in separate directories.
2. Run `python3 tests/regression/run_examples.py --np 1`, `--np 2` and `--np 4` with the release build,
   and `--np 1` with the ASan build, BEFORE and AFTER the fix.
3. Show that the targeted failure disappears and that no other result changes
   (max abs/rel diffs must be unchanged or identical).

Deliverables:
- The code change.
- A CHANGELOG.md entry under "Unreleased > Fixed": what, why, file:line, "results unchanged" or the measured change.
- Mark the item as fixed in docs/guide/05_known_issues.md (status + commit).
- One commit: "Fix [B-01]: <short description>".
```

## P2-b. Regenerate a benchmark (only after an explicit decision)

```text
Context: docs/guide/05_known_issues.md items R-02/R-03; docs/guide/06_reproducibility.md.
Decision recorded by the model owner: [paste decision, date].

Task: regenerate examples/[more/model_259/results_benchmark] from the current code.
- Use a release build, --np 1, and record compiler, MPI and HDF5 versions and the git commit.
- Before overwriting, write a table comparing old vs new benchmark (per file: max abs/rel diff,
  outlet peak value and time).
- Add examples/[...]/results_benchmark/PROVENANCE.md with the command, versions, commit and decision.
- Remove the XFAIL for this case in tests/regression/run_examples.py; the harness must PASS.
- CHANGELOG entry under "Changed", with the comparison table.
```

## P2-c. Continuous integration

```text
Task: add a GitHub Actions workflow (.github/workflows/ci.yml) for ASYNCH.
- ubuntu-24.04; apt install: gcc make autoconf automake libtool pkg-config openmpi-bin
  libopenmpi-dev libhdf5-dev hdf5-tools libpq-dev zlib1g-dev check; pip install h5py.
- Steps: autoreconf --install; configure (-O2 -DNDEBUG) in build/; make -j; make check;
  python3 tests/regression/run_examples.py --np 1 and --np 2.
- Second job: same with -fsanitize=address,undefined (ASAN_OPTIONS=detect_leaks=0).
- Remove .travis.yml and update the README badge.
Non-goals: do not fix failing cases inside this task; report them.
```

## P3. Design the new Python API (design first, no code)

```text
Context: docs/guide/05_known_issues.md [A-01], src/asynch_interface.h, src/asynch_cli.c (main),
docs/guide/02_code_map.md §2.3.

Task: write docs/guide/design_python_api.md proposing a new Python binding. Requirements:
- C side: a small stable API with opaque handles only (no struct layouts exposed to Python),
  explicit error codes, no global state other than MPI.
- Python side: ctypes or cffi (justify), Python >= 3.9, NumPy arrays for states/parameters/outputs,
  optional mpi4py; runnable as `mpirun -n 4 python run.py`.
- Minimum use cases: run a .gbl end to end; change global parameters between runs
  (calibration loop); read/set link states at time t; get hydrographs as arrays.
- Build/packaging plan (shared library from autotools, pip-installable wrapper).
- Test plan: the Python run must reproduce the CLI run of every example bit-for-bit.
Deliver the document only; wait for approval before implementing.
```

## P4. Profile before optimising

```text
Task: measure, do not change code. Build with -O2 -g. On [a large network: path to .gbl],
profile with `perf record -g` (1 process) and with 4 and 16 processes (wall time per phase,
from the --more output). Report the top 15 functions by self time and the time split between
initialisation, Advance, and output. Relate the findings to P-01..P-03 in
docs/guide/05_known_issues.md, and propose at most 3 optimisations, ranked by expected gain vs risk.
```
