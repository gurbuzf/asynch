# 3. Code map: where everything lives

<div class="meta-row"><span class="audience">Code readers</span><span>Some C helps (chapter 6)</span><span>15 minutes</span></div>

<p class="lead">ASYNCH is about 36 000 lines of C. You do not need to read them all: about 80 % of the scientific
behaviour lives in four files. This page tells you which ones, and in which order to read them.</p>

## 3.1 The shortest reading path

| Order | File | What you learn | Size |
|---|---|---|---|
| 1 | `src/asynch_cli.c` → `main()` | the life of a run, step by step | 360 lines |
| 2 | `src/structs.h` | the data: what a *link*, the *globals*, a *solution list* are | 600 lines |
| 3 | `src/models/equations.c` → `model254()` | what a model *is*: one C function computing dy/dt | 80 lines |
| 4 | `src/advance.c` → `Advance()` | how links are scheduled asynchronously | 420 lines |
| 5 | `src/steppers/explicit.c` → `ExplicitRKSolver()` | one time step of one link | 350 lines |
| 6 | `src/models/definitions.c` | how a model id is wired to its equations, sizes, parameters | 4 000 lines (read only your model's `case`) |

## 3.2 Directory layout

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} {octicon}`rocket` Entry points and data
- `src/asynch_cli.c`: `main()`, the `asynch` command-line program
- `src/asynch_interface.c/.h`: the public C API (`Asynch_Init`, `Asynch_Parse_GBL`, `Asynch_Advance`, ...)
- `src/asynch_api.c/.h`: the C API for other languages: plain arrays and handles, custom models (chapter 10)
- `src/structs.h`: all core data structures
- `src/globals.c`: `my_rank`, `np`, the two global variables of the library
:::

:::{grid-item-card} {octicon}`download` Reading the inputs
- `src/config_gbl.c`: the `.gbl` global file
- `src/riversys.c`: topology (`.rvr`), parameters (`.prm`), initial states; builds the `Link` array
- `src/partition.c`: splits the network between MPI processes
- `src/forcings.c`, `forcings_io.c`: rain, evaporation and other forcings (files, binaries, database)
:::

:::{grid-item-card} {octicon}`sync` The solver
- `src/advance.c`: **the main loop**, the asynchronous scheduler (chapter 4)
- `src/rksteppers.c`: initial step size, helpers shared by the steppers
- `src/steppers/`: one time step of one link: `explicit.c` (the standard one), `explicit_index1*.c` (dams),
  `forced.c` (imposed discharge)
- `src/solvers/`: the Runge-Kutta coefficients: `rk3_2_dense.c` (method 0), `rk4_3_dense.c` (1),
  `dopri5_dense.c` (2, the usual choice), `radau.c` (3, refused with an error)
:::

:::{grid-item-card} {octicon}`beaker` The models
- `src/models/definitions.c`: the registry: sizes, unit conversions, precalculations, initial states
- `src/models/equations.c`: the right-hand sides dy/dt of every model
- `src/models/check_consistency.c`: clamps states (e.g. no negative storage)
- `src/models/check_state.c`: discontinuity "state" detection (dams)
- `src/models/output_constraints.c`: filters applied to snapshot outputs
:::

:::{grid-item-card} {octicon}`upload` Outputs and communication
- `src/comm.c`: MPI messages between processes
- `src/processdata.c`, `outputs.c`, `io.c`: hydrographs, peak flows, snapshots
- `src/db.c`: PostgreSQL access
- `src/blas.c`: small vector helpers (daxpy, dcopy, norms)
- `src/assim/`, `assim_cli.c`: data assimilation (built only if PETSc is found)
:::

:::{grid-item-card} {octicon}`package` Around the code
- `python/asynch/`: the Python package (chapter 10): `solver.py`, `model.py`, `config.py`, `io.py`, `_lib.py`
- `tests/`: C unit tests (`check_asynch.c`), Python tests, the regression harness (chapter 9)
- `examples/`: runnable examples and their reference results; `examples/python/`: Python examples
- `docs/`: this documentation (guide in Markdown, reference manual in reStructuredText)
:::
::::

Every `.c` file in `src/` is compiled: about 6 500 lines of old code that were not (issue M-01, chapter 8) were
removed in 2026; they remain in the git history.

## 3.3 The life of a run

`main()` in `src/asynch_cli.c` is a straight sequence of calls to the public API
(`src/asynch_interface.c`). Each call prints one of the lines you see on screen:

<div class="timeline">

- `Asynch_Init`: create the solver object; MPI rank and size
- `Asynch_Parse_GBL`: read the global file · screen: *Reading global file...* · `config_gbl.c: Read_Global_Data`
- `Asynch_Load_Network`: read the .rvr, build the Link array and the parent/child pointers · screen: *Loading network...* · `riversys.c`
- `Asynch_Partition_Network`: decide which process owns which link · screen: *Partitioning network...* · `partition.c`
- `Asynch_Load_Network_Parameters`: read the .prm into link->params, convert units (ConvertParams) · screen: *Loading parameters...* · `riversys.c`
- `Asynch_Load_Dams`: dams and reservoirs · screen: *Reading dam and reservoir data...*
- `Asynch_Load_Numerical_Error_Data`: tolerances; builds the Runge-Kutta method table · screen: *Setting up numerical error data...*
- `Asynch_Initialize_Model`: set link->differential, dim, ... (InitRoutines), then the Precalculations · screen: *Initializing model...* · `definitions.c`
- `Asynch_Load_Initial_Conditions`: y(t0) from .ini/.uini/.rec/.h5/database; ReadInitData fills derived states · screen: *Loading initial conditions...*
- `Asynch_Load_Forcings`: rain, evaporation, ... · screen: *Loading forcings...*
- `Asynch_Load_Save_Lists`: which links write hydrographs and peaks · screen: *Loading output data...*
- `Asynch_Finalize_Network`: allocate per-link solution lists, MPI buffers · screen: *Finalizing network...*
- `Asynch_Calculate_Step_Sizes`: the first step size h of every link · screen: *Calculating initial step sizes...*
- `Asynch_Prepare_*`: open the temporary output files
- `Asynch_Advance`: **the simulation itself** (chapter 4) · `advance.c: Advance()`
- `Asynch_Take_System_Snapshot`: the final snapshot
- `Asynch_Create_Output`: merge the temporary files into the final .h5/.csv/.dat/database
- `Asynch_Create_Peakflows_Output`: write the .pea
- `Asynch_Delete_Temporary_Files, Asynch_Free`: clean up

</div>

Because it is a sequence of API calls, you can write your own `main()` that does the same thing and changes something in between,
e.g. overwriting parameters after `Asynch_Load_Network_Parameters`.

## 3.4 The core data structures (`src/structs.h`)

**`Link`**: one river link (channel segment + its hillslope). Everything is attached to it:

| field | meaning |
|---|---|
| `ID`, `location` | id used in input files; index in the `sys` array |
| `parents[num_parents]`, `child` | the tree: upstream links and the downstream link (`NULL` at the outlet) |
| `dim` | number of states (unknowns) of the ODE at this link (7 for model 254) |
| `params[num_params]` | local parameters: read from `.prm`, then converted and extended by precalculations |
| `differential` | **function pointer** to the model's right-hand side, e.g. `model254` |
| `solver`, `method` | which stepper and which Runge–Kutta coefficients are used |
| `h`, `last_t` | current step size, and time up to which the solution is known [min] |
| `my->list` | the stored solution: a linked list of recent steps (see below) |
| `my->forcing_values[]` | current value of each forcing (rain, evaporation, ...) |
| `peak_value`, `peak_time` | running maximum for the `.pea` output |

`my` points to data that exists only on the MPI process that *owns* the link.

**`RKSolutionList` / `RKSolutionNode`**: every accepted step of a link is stored as a node:
time `t`, state `y_approx`, and the RK stage values `k`. With the `k` values the solution
can be evaluated at **any time inside the step** ("dense output"). This is what makes
the asynchronous scheme possible: a downstream link can ask "what was the discharge of
my parent at t = 12.37 min?" even though the parent never stopped at that time. Nodes
are freed once every child has used them.

**`GlobalVars`**: everything from the `.gbl` file: model id, simulation time
(`maxtime`, in minutes), global parameters, file names, output settings.

**`AsynchSolver`**: the object that owns all of the above for one simulation (`sys`,
`globals`, `my_sys` = the links owned by this process, forcings, MPI buffers).

## 3.5 How a model plugs in

A model is identified by its number (`model_uid` in the code, first entry of the `.gbl`).
For model 254 you find it in these places:

| function (`src/models/definitions.c`) | what it sets for model 254 |
|---|---|
| `SetParamSizes` (line ~572) | 12 global params, 8 params per link of which 3 are read from `.prm`, 3 forcings |
| `SetOutputConstraints` (line ~885) | snapshot filter (its missing `break` was bug B-01, fixed) |
| `ConvertParams` (line ~1011) | `.prm` units → SI: L km→m, A_h km²→m² |
| `InitRoutines` (line ~1756) | `dim = 7`, dense output on states 0 and 6, `differential = model254`, `check_consistency` |
| `Precalculations` (line ~3036) | derived parameters `invtau`, `k_2`, `k_i`, `c_1`, `c_2` |
| `ReadInitData` (line ~3573) | derived initial states: `s_precip = 0`, `V_r = 0`, `q_b = q` |
| `src/models/equations.c` → `model254` (line 1609) | the ODEs themselves |

[05_model_254_explained.md](05_model_254_explained.md) walks through each of these
with the physics.

## 3.6 Parallelism in one paragraph

![Links shared between processes: whole sub-basins per process; messages only where a parent is elsewhere](diagrams/mpi_split.svg)

With `mpirun -n P` there are `P` independent copies of the program (MPI *processes*),
each with its own memory. `partition.c` gives each process a set of links: whole
sub-basins, starting from the headwater links ("leaves"), so that most parent → child
connections stay inside one process. When a link's parent belongs to another process,
the parent's recent solution steps are sent over MPI (`comm.c: Transfer_Data`). Output
files are written by process 0 after gathering data from the others.
