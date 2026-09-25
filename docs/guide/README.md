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
| 5 | [Known issues](05_known_issues.md) | see known bugs, risks and open scientific questions |
| 6 | [Reproducibility](06_reproducibility.md) | run the regression tests; verify that a change is (or is not) scientific |
| 7 | [C primer](07_c_primer.md) | read the C in this repository (pointers, structs, memory, MPI), with real examples |

Every change to the code is recorded in [`CHANGELOG.md`](../../CHANGELOG.md) at the root of the repository.

## Conventions for changing the code

1. **One logical change per commit**, with a `CHANGELOG.md` entry that says *what*, *why*, and
   *whether results change*.
2. **Run `tests/regression/run_examples.py` before and after.** If results move beyond
   the tolerance, the change is scientific: it is explained, and benchmarks are regenerated
   only deliberately, in the same commit.
3. **Never mix a refactoring with a behaviour change.** A refactoring must leave results
   *bit-identical*.
4. Document what you learn: if you had to figure something out, write it in this guide.
