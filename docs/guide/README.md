# ASYNCH developer & learner guide

This guide is written for someone who knows hydrology and some Python, but little C,
and wants to **run, read, verify and improve** ASYNCH. It complements the original
reference documentation in `docs/*.rst` (file formats, list of models, C API), which is
still valid and is linked where needed.

## Read in this order

| # | Page | You will be able to... |
|---|---|---|
| 1 | [Build and run](01_build_and_run.md) | install dependencies, compile, run the examples, read the outputs in Python |
| 2 | [Code map](02_code_map.md) | find your way in the source tree; follow a run from `main()` to the output files |
| 3 | [How the solver works](03_how_the_solver_works.md) | understand the asynchronous Runge–Kutta scheme and its error control |
| 4 | [Model 254 explained](04_model_254_explained.md) | check every equation of the Top Layer model against its C code, with units |
| 5 | [Known issues](05_known_issues.md) | see every bug, risk and open scientific question found in the audit |
| 6 | [Reproducibility](06_reproducibility.md) | run the regression tests; verify that a change is (or is not) scientific |
| 7 | [C primer](07_c_primer.md) | read the C in this repository (pointers, structs, memory, MPI), with real examples |
| 8 | [Prompts for the next phases](08_prompts_for_next_phases.md) | hand the next tasks to an AI assistant (or a colleague) precisely |

Every change to the code is recorded in [`CHANGELOG.md`](../../CHANGELOG.md) at the root of the repository.

## Project roadmap

| Phase | Goal | Status |
|---|---|---|
| **1. Understand** | build, run all examples, audit the code, regression harness, this guide | **done** (Sept. 2026) |
| **2. Fix** | fix confirmed bugs one per commit, each verified with the harness; working CI; remove dead code | next |
| **3. Python API** | new, small, stable C API + Python binding (the old one is unrepairable, A-01) | |
| **4. Performance & structure** | profile on a large network (P-*), one descriptor per model (M-02) | |
| **5. Science** | discuss S-* items, model improvements, new features | |

### Rules we follow in every phase

1. **One logical change per commit**, with a `CHANGELOG.md` entry that says *what*, *why*, and
   *whether results change*.
2. **Run `tests/regression/run_examples.py` before and after.** If results move beyond
   the tolerance, the change is scientific: it is explained, and benchmarks are regenerated
   only deliberately, in the same commit.
3. **Never mix a refactoring with a behaviour change.** A refactoring must leave results
   *bit-identical*.
4. Document as you go: if you had to figure something out, write it in this guide.

## Decisions needed before Phase 2

These are choices for the model's owner, not for the programmer:

1. **R-02 / R-03:** may the `clearcreek` and `model_259` reference results be regenerated
   (after B-01 is fixed) from the current code and repository inputs? The alternative is to
   try to recover the original inputs.
2. **B-03:** keep "production build = `-DNDEBUG`" or make both builds clean? (Recommended: both.)
3. **S-02 / S-06 (model 254 water balance):** keep the current behaviour, documenting it, or change the
   model? Any change here alters operational results and needs a scientific justification.
4. **M-01:** delete the dead source files or move them to an `attic/` folder?
