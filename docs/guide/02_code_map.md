# 2. Code map: where everything lives

ASYNCH is about 43 000 lines of C. You do **not** need to read them all. About 80 % of
the scientific behaviour lives in **four files**. This page tells you which ones, and
in which order to read them.

## 2.1 The shortest reading path

| Order | File | What you learn | Size |
|---|---|---|---|
| 1 | `src/asynch_cli.c` → `main()` | the life of a run, step by step | 360 lines |
| 2 | `src/structs.h` | the data: what a *link*, the *globals*, a *solution list* are | 600 lines |
| 3 | `src/models/equations.c` → `model254()` | what a model *is*: one C function computing dy/dt | 80 lines |
| 4 | `src/advance.c` → `Advance()` | how links are scheduled asynchronously | 420 lines |
| 5 | `src/steppers/explicit.c` → `ExplicitRKSolver()` | one time step of one link | 350 lines |
| 6 | `src/models/definitions.c` | how a model id is wired to its equations, sizes, parameters | 4 000 lines (read only your model's `case`) |

## 2.2 Directory layout

```
asynch/
├── configure.ac, Makefile.am      build system (autotools), see 01_build_and_run.md
├── src/
│   ├── asynch_cli.c               main(): the `asynch` command-line program
│   ├── asynch_interface.c/.h      the public C API: Asynch_Init, Asynch_Parse_GBL, Asynch_Advance, ...
│   ├── structs.h                  all core data structures
│   ├── config_gbl.c               parser for the .gbl global file
│   ├── riversys.c                 reads topology (.rvr), parameters (.prm), initial states; builds the Link array
│   ├── partition.c                splits the network between MPI processes
│   ├── forcings.c, forcings_io.c  rain / evaporation / other forcings (files, binaries, database)
│   ├── advance.c                  THE MAIN LOOP (asynchronous scheduler)
│   ├── rksteppers.c               initial step size, helpers shared by the steppers
│   ├── steppers/                  one time step of one link
│   │   ├── explicit.c             standard explicit Runge–Kutta step with dense output
│   │   ├── explicit_index1*.c     variants for models with algebraic variables / dams
│   │   └── forced.c               links whose discharge is imposed (reservoirs, observed data)
│   ├── solvers/                   the Runge–Kutta *coefficients* (Butcher tableaus + dense output)
│   │   ├── rk3_2_dense.c          method 0
│   │   ├── rk4_3_dense.c          method 1
│   │   ├── dopri5_dense.c         method 2 (Dormand–Prince 5(4), the usual choice)
│   │   └── radau.c                method 3 (implicit, NOT usable, see issue B-04)
│   ├── models/
│   │   ├── definitions.c          model registry: sizes, unit conversions, precalculations, initial states
│   │   ├── equations.c            the right-hand sides dy/dt of every model
│   │   ├── check_consistency.c    clamps states (e.g. no negative storage)
│   │   ├── check_state.c          discontinuity "state" detection (dams)
│   │   └── output_constraints.c   filters applied to snapshot outputs
│   ├── comm.c                     MPI messages between processes
│   ├── processdata.c, outputs.c, io.c   writing hydrographs, peak flows, snapshots
│   ├── db.c                       PostgreSQL access
│   ├── blas.c                     small vector helpers (daxpy, dcopy, norms)
│   └── assim/, assim_cli.c        data assimilation (built only if PETSc is found)
├── py/                            Python API (BROKEN, see issue A-01)
├── tests/check_asynch.c           C unit tests (one test at the moment)
├── tests/regression/              example-based regression harness (see 06_reproducibility.md)
├── examples/                      runnable examples + reference results
├── docs/*.rst                     original Sphinx documentation (formats, models, API)
└── docs/guide/                    this guide
```

Files in `src/` that are **not compiled** (dead code, ignore them): `rkmethods.c`,
`rainfall.c`, `asynchdist_custom.c`, `modeloutputs.c`, `models/model.c`,
`steppers/implicit.c`, `steppers/explicit_discont.c`, `steppers/assim.c`.

## 2.3 The life of a run

`main()` in `src/asynch_cli.c` is a straight sequence of calls to the public API
(`src/asynch_interface.c`). Each call prints one of the lines you see on screen:

```
Asynch_Init                      create the AsynchSolver object, MPI rank/size
Asynch_Parse_GBL                 "Reading global file..."        config_gbl.c: Read_Global_Data
Asynch_Load_Network              "Loading network..."            riversys.c: read .rvr, build Link array, parents/child pointers
Asynch_Partition_Network         "Partitioning network..."       partition.c: which process owns which link
Asynch_Load_Network_Parameters   "Loading parameters..."         riversys.c: read .prm → link->params ; ConvertParams (units)
Asynch_Load_Dams                 "Reading dam and reservoir..."
Asynch_Load_Numerical_Error_Data "Setting up numerical error..." tolerances; builds the RK method table
Asynch_Initialize_Model          "Initializing model..."         definitions.c: InitRoutines (sets link->differential, dim, ...) + Precalculations
Asynch_Load_Initial_Conditions   "Loading initial conditions..." .ini/.uini/.rec/.h5/db → y(t0) ; ReadInitData fills derived states
Asynch_Load_Forcings             "Loading forcings..."
Asynch_Load_Save_Lists           "Loading output data..."        which links write hydrographs/peaks
Asynch_Finalize_Network          "Finalizing network..."         allocate per-link solution lists, MPI buffers
Asynch_Calculate_Step_Sizes      "Calculating initial step..."   first h for every link
Asynch_Prepare_*                 open temporary output files
Asynch_Advance                   ======== THE SIMULATION ======== advance.c: Advance()
Asynch_Take_System_Snapshot      final snapshot
Asynch_Create_Output             merge temporary files into the final .h5/.csv/.dat/database
Asynch_Create_Peakflows_Output   write .pea
Asynch_Delete_Temporary_Files, Asynch_Free
```

Because it is a sequence of API calls, you can write your own `main()` (or, in the
future, a Python script) that does the same thing and changes something in between,
e.g. overwriting parameters after `Asynch_Load_Network_Parameters`.

## 2.4 The core data structures (`src/structs.h`)

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

## 2.5 How a model plugs in

A model is identified by its number (`model_uid` in the code, first entry of the `.gbl`).
For model 254 you find it in these places:

| function (`src/models/definitions.c`) | what it sets for model 254 |
|---|---|
| `SetParamSizes` (line ~572) | 12 global params, 8 params per link of which 3 are read from `.prm`, 3 forcings |
| `SetOutputConstraints` (line ~885) | snapshot filter, **buggy fall-through, issue B-01** |
| `ConvertParams` (line ~1011) | `.prm` units → SI: L km→m, A_h km²→m² |
| `InitRoutines` (line ~1756) | `dim = 7`, dense output on states 0 and 6, `differential = model254`, `check_consistency` |
| `Precalculations` (line ~3036) | derived parameters `invtau`, `k_2`, `k_i`, `c_1`, `c_2` |
| `ReadInitData` (line ~3573) | derived initial states: `s_precip = 0`, `V_r = 0`, `q_b = q` |
| `src/models/equations.c` → `model254` (line 1609) | the ODEs themselves |

[04_model_254_explained.md](04_model_254_explained.md) walks through each of these
with the physics.

## 2.6 Parallelism in one paragraph

With `mpirun -n P` there are `P` independent copies of the program (MPI *processes*),
each with its own memory. `partition.c` gives each process a set of links: whole
sub-basins, starting from the headwater links ("leaves"), so that most parent → child
connections stay inside one process. When a link's parent belongs to another process,
the parent's recent solution steps are sent over MPI (`comm.c: Transfer_Data`). Output
files are written by process 0 after gathering data from the others.
