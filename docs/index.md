# ASYNCH

<div class="hero">
<div class="hero-text">
<p class="hero-title">ASYNCH</p>
<p class="tagline">River networks, solved asynchronously.</p>
<p>ASYNCH computes how much water flows in every stream of a river basin, from the rain that falls on it. It cuts
the river network into thousands of links, lets every link advance with its own time step, and shares the work
between processors with MPI. More than 50 hydrological models are built in, including the Top Layer model (254) of
the Iowa Flood Center, and you can add your own, in C or in Python.</p>
<div class="buttons">
<a class="primary" href="guide/00_what_is_asynch.html">Start here</a>
<a class="secondary" href="guide/01_setup.html">Install</a>
<a class="secondary" href="guide/10_python.html">Python library</a>
</div>
</div>
<div class="hero-art" aria-hidden="true">
<svg viewBox="0 0 240 200" xmlns="http://www.w3.org/2000/svg">
<g fill="none" stroke="var(--d-water)" stroke-linecap="round">
<path d="M20 24L62 52L100 96" stroke-width="3"/><path d="M40 92L100 96" stroke-width="3"/><path d="M92 20L62 52" stroke-width="3"/>
<path d="M24 160L70 140L100 96" stroke-width="3"/><path d="M60 184L70 140" stroke-width="3"/>
<path d="M100 96L150 112" stroke-width="6"/><path d="M172 30L160 70L150 112" stroke-width="4"/><path d="M210 60L160 70" stroke-width="3"/>
<path d="M150 112L200 150L228 190" stroke-width="8"/><path d="M130 176L200 150" stroke-width="4"/>
</g>
<g stroke="var(--color-background-primary)" stroke-width="3">
<circle cx="20" cy="24" r="7" fill="var(--d-p0)"/><circle cx="92" cy="20" r="7" fill="var(--d-p0)"/><circle cx="62" cy="52" r="7" fill="var(--d-p0)"/>
<circle cx="40" cy="92" r="7" fill="var(--d-p0)"/><circle cx="24" cy="160" r="7" fill="var(--d-p1)"/><circle cx="60" cy="184" r="7" fill="var(--d-p1)"/>
<circle cx="70" cy="140" r="7" fill="var(--d-p1)"/><circle cx="100" cy="96" r="8" fill="var(--d-p2)"/><circle cx="172" cy="30" r="7" fill="var(--d-p1)"/>
<circle cx="210" cy="60" r="7" fill="var(--d-p1)"/><circle cx="160" cy="70" r="7" fill="var(--d-p1)"/><circle cx="150" cy="112" r="9" fill="var(--d-p2)"/>
<circle cx="130" cy="176" r="7" fill="var(--d-p2)"/><circle cx="200" cy="150" r="9" fill="var(--d-p2)"/>
</g>
</svg>
</div>
</div>

::::{tab-set}

:::{tab-item} Command line
```console
$ mpirun -n 4 asynch clearcreek.gbl
```
A global file (`.gbl`) names the model, the dates, the network, the rain and the outputs.
[Running the model](guide/02_running_the_model.md) explains each part.
:::

:::{tab-item} Python
```python
from asynch import Simulation

with Simulation("clearcreek.gbl") as sim:
    sim.run()
    peak_time, peak_q = sim.peaks          # every link, as NumPy arrays
```
Change parameters, read states while the model runs, write new models: [Using ASYNCH from Python](guide/10_python.md).
:::

:::{tab-item} A new model
```python
from asynch import Model

model = Model(states=["q"], global_params=["k"], params=["A_h"], forcings=["rain"],
              param_factors={"A_h": 1e6})
model.equations = """
    d_q = (upstream_q + rain * A_h * (0.001 / 3600.0) - q) / k;
"""
```
Your equations run in the C solver, as fast as a built-in model: [A new model](guide/10_python.md#107-a-new-model).
:::
::::

<div class="stats">
<div><p>50+</p><p>built-in hydrological models</p></div>
<div><p>400 000</p><p>links: the whole state of Iowa</p></div>
<div><p>2.9×</p><p>faster on 4 processes (Clear Creek)</p></div>
<div><p>93</p><p>automatic tests, run on every change</p></div>
</div>

## Find your way

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

Run and control simulations from Python, and write new models in Python at C speed (Numba).
:::

:::{grid-item-card} {octicon}`book` Understand
:link: guide/04_how_the_solver_works
:link-type: doc

The asynchronous solver, model 254 equation by equation, a map of the code, just enough C.
:::

:::{grid-item-card} {octicon}`list-unordered` Reference
:link: input_output
:link-type: doc

Every file format, every option of the global file, every built-in model, the C and Python APIs.
:::

:::{grid-item-card} {octicon}`shield-check` Quality
:link: guide/07_improvements_explained
:link-type: doc

What was found and fixed, how serious it was, and how every result is checked against the references.
:::

:::{grid-item-card} {octicon}`history` Changes
:link: changelog
:link-type: doc

Every change to the code, and whether it changes numerical results.
:::
::::

## How a run works

![A model run: the input files, the three stages inside ASYNCH, the output files](guide/diagrams/run_pipeline.svg)

## What's new in 1.5

<div class="steps">

1. **A Python library that works.** `pip install` it, run and change simulations, write models in C, Numba or plain
   Python, use MPI: [chapter 10](guide/10_python.md).
2. **Two critical and ten high-severity bugs fixed**, among them wrong coefficients in solver methods 0 and 1, and
   memory overwritten by the main example: [what was fixed](guide/07_improvements_explained.md).
3. **Networks larger than 65 535 links** are counted correctly through the library.
4. **Every result is checked** against the reference results of the original ASYNCH: `make check` runs 93 tests,
   and GitHub Actions run them on every change: [reproducibility](guide/09_reproducibility.md).
5. **This website**, with search, diagrams and a light and dark theme.

</div>

The complete list, with the effect of each change on numerical results, is the [changelog](changelog.md).

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
