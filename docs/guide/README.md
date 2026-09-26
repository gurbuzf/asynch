# ASYNCH guide: learn, run, understand

This guide is also part of the documentation website, <https://gurbuzf.github.io/asynch/>, with search and the
reference manual. It is for people who know hydrology but not necessarily programming. It takes you from
"what is this model?" to installing it, running it, reading its equations and its C code. It
complements the original reference manual in `docs/*.rst` (every file format, every model).

## Learning path

**Use the model** (no programming needed)

| # | Chapter | You will be able to... |
|---|---|---|
| 0 | [What ASYNCH is](00_what_is_asynch.md) | explain what the model computes, what a run is, and the vocabulary |
| 1 | [Setting up](01_setup.md) | install everything on Ubuntu/WSL or with Docker, and run a first simulation |
| 2 | [Running the model](02_running_the_model.md) | understand every input, run the examples, change a parameter, read and plot results |
| 10 | [Using ASYNCH from Python](10_python.md) | run and control simulations from Python, write global files, **create new models** (at C speed with Numba), use MPI |

**Understand the science and the code**

| # | Chapter | You will be able to... |
|---|---|---|
| 3 | [Code map](03_code_map.md) | find your way in the source code; follow a run from start to the output files |
| 4 | [How the solver works](04_how_the_solver_works.md) | understand the asynchronous Runge–Kutta scheme and its error control |
| 5 | [Model 254, equation by equation](05_model_254_explained.md) | check every equation of the Top Layer model against its code, with units |
| 6 | [Just enough C](06_c_primer.md) | read the C of this repository: pointers, structures, memory, MPI, with real examples |

**What changed, and how it is verified**

| # | Chapter | You will be able to... |
|---|---|---|
| 7 | [What was fixed, and why it matters](07_improvements_explained.md) | see every problem found, how serious it was, and before/after results |
| 8 | [Known issues (technical)](08_known_issues.md) | the detailed record: file, line, evidence, status |
| 9 | [Reproducibility](09_reproducibility.md) | check with one command that results still match the reference results |

Every change to the code is recorded in [`CHANGELOG.md`](../../CHANGELOG.md).

## Quick start

With Docker installed (any system):

```bash
git clone https://github.com/gurbuzf/asynch.git && cd asynch && git checkout modernization
docker build -t asynch .
docker run --rm -it asynch
mpirun -n 2 asynch clearcreek.gbl        # inside the container
```

On Ubuntu 24.04 without Docker, follow [chapter 1, option A](01_setup.md#option-a-native-install-on-ubuntu-2404).

## Conventions for changing the code

1. **One logical change per commit**, with a `CHANGELOG.md` entry that says *what*, *why*, and
   *whether results change*.
2. **Run `make check` (all tests) and `tests/regression/run_examples.py --compare-to <previous build>` before and after.** The reference results of the original
   repository are never modified. If results move beyond the tolerance, the change is scientific and
   must be explained.
3. **Never mix a reorganisation of the code with a change of behaviour.** A reorganisation must leave results
   identical to the last digit.
4. Document what you learn: if you had to figure something out, write it in this guide.
