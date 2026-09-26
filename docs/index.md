# ASYNCH

**Hydrological models on river networks, solved asynchronously.** ASYNCH integrates the ordinary differential
equations of a river network cut into thousands of links (hillslope-link models). Each link has its own adaptive
time step, and the network can be shared between processors with MPI. It ships with more than 50 hydrological
models, including the Top Layer model (254) used by the Iowa Flood Center, and you can add your own: in C, or in
Python.

```{code-block} console
$ mpirun -n 4 asynch clearcreek.gbl                  # the command-line program
$ python3 -c "import asynch; print(asynch.__version__)"   # the Python library
```

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} {octicon}`rocket` Start here
:link: guide/00_what_is_asynch
:link-type: doc

What the model computes, how to install it (Ubuntu, WSL or Docker) and run a first simulation.
:::

:::{grid-item-card} {octicon}`code` Python library
:link: guide/10_python
:link-type: doc

Run and control simulations from Python, and write **new models in Python at C speed** (Numba).
:::

:::{grid-item-card} {octicon}`book` Understand
:link: guide/04_how_the_solver_works
:link-type: doc

The asynchronous Runge-Kutta solver, model 254 equation by equation, a map of the code, just enough C.
:::

:::{grid-item-card} {octicon}`list-unordered` Reference
:link: input_output
:link-type: doc

Every file format, every option of the global file, every built-in model, the C and Python APIs.
:::

:::{grid-item-card} {octicon}`shield-check` Quality
:link: guide/07_improvements_explained
:link-type: doc

What was found and fixed, how serious it was, and how every result is checked against the reference results.
:::

:::{grid-item-card} {octicon}`history` Changes
:link: changelog
:link-type: doc

Every change to the code, and whether it changes numerical results.
:::
::::

## In one minute

- **Run a global file**: `asynch my_basin.gbl` (or `mpirun -n 4 asynch ...`). A global file (`.gbl`) names the network,
  the parameters, the initial state, the rain and the outputs: [Running the model](guide/02_running_the_model.md).
- **From Python**: `with asynch.Simulation("my_basin.gbl") as sim: sim.run()`, then read `sim.states`, change
  `sim.global_params`, advance step by step: [Using ASYNCH from Python](guide/10_python.md).
- **A new model**: name the states and parameters, write `d_q = ...` in C, or a Python function:
  [A new model](guide/10_python.md#107-a-new-model).
- **Is it right?** `make check` runs the C unit tests, the Python tests and every example against the reference
  results: [Reproducibility](guide/09_reproducibility.md).

```{toctree}
:hidden:
:caption: Start here

guide/00_what_is_asynch
guide/01_setup
guide/02_running_the_model
```

```{toctree}
:hidden:
:caption: Python library

guide/10_python
python_api
```

```{toctree}
:hidden:
:caption: Understand the model and the code

guide/03_code_map
guide/04_how_the_solver_works
guide/05_model_254_explained
guide/06_c_primer
terminology
internal
```

```{toctree}
:hidden:
:caption: Reference manual

input_output
builtin_options
builtin_models
custom_models
c_api
assim
cookbook
```

```{toctree}
:hidden:
:caption: Quality and changes

guide/07_improvements_explained
guide/08_known_issues
guide/09_reproducibility
changelog
```

```{toctree}
:hidden:
:caption: Project

about
contribute
release_notes
```
