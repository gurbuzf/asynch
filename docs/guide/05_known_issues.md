# 5. Known issues: code audit (Phase 1)

This is the result of the Phase 1 audit (September 2026). **Nothing here has been
fixed yet.** The list comes first so that every future fix can be
discussed, prioritised and verified against the regression harness
([06_reproducibility.md](06_reproducibility.md)) one by one.

How each item was established:

* **Confirmed**: reproduced by running the code. The evidence is quoted: a crash,
  an AddressSanitizer report, a comparison.
* **Code reading**: visible in the source, but not (yet) triggered by an example.
* **For discussion**: a scientific or design question, not necessarily a bug.
  These need a hydrologist's judgement (yours), not just a programmer's.

Severity scale: **critical** (memory corruption / wrong results / crash in normal
use), **high** (crash or wrong result in a plausible configuration), **medium**,
**low** (cosmetic, or only in unusual situations).

Line numbers refer to commit `84da43a` (the state of `master` at the time of the audit).

---

## Summary table

| ID | Severity | Status | One-line description |
|----|----------|--------|----------------------|
| [B-01](#b-01) | critical | confirmed | Model 254 uses model 256's snapshot filter: heap buffer overflow, crashes clearcreek on 1 process |
| [B-02](#b-02) | high | code reading | Snapshot values are filtered only for links owned by MPI rank 0: output depends on process count |
| [B-03](#b-03) | high | confirmed | Output file closed twice at shutdown: every debug build aborts at the end of a run |
| [B-04](#b-04) | high | confirmed | Solver index 3 or 4 (advertised as "implicit") segfaults; the index is never validated |
| [B-05](#b-05) | medium | code reading | `Destroy_ErrorData` frees addresses of struct fields instead of the pointers |
| [B-06](#b-06) | medium | code reading | `Asynch_Get_Num_Links` returns `unsigned short`: wrong for networks > 65 535 links |
| [B-07](#b-07) | medium | code reading | `DumpStateH5` loops past the array end if rank 0 owns no link; leaks its buffer |
| [B-08](#b-08) | medium | confirmed (UB sanitizer) | Misaligned `double` reads/writes in snapshot filters (undefined behaviour) |
| [B-09](#b-09) | low | code reading | Model 402 dam check prints a debug line on every call |
| [B-10](#b-10) | low | compiler | Missing prototype for `Create_Rain_Data_Par_IBin`; wrong `printf` format in `check_state.c` |
| [B-11](#b-11) | low | code reading | ~75 `fscanf`/`fread` return values ignored: malformed input files are not detected |
| [B-12](#b-12) | medium | code reading | `.uini` reader misses "not enough values" (checks `== 0`, `fscanf` returns `EOF`); clearcreek.uini is short |
| [R-01](#r-01) | high | confirmed | No automated regression tests; only one unit test (`days_in_month`) |
| [R-02](#r-02) | medium | confirmed | `examples/results/clearcreek.pea` (2015) does not match today's `clearcreek.gbl` |
| [R-03](#r-03) | medium | confirmed | Model 259 benchmark cannot be reproduced from the files in the repository |
| [R-04](#r-04) | fixed | confirmed | Examples 258/259 pointed to a file on the original developers' cluster |
| [R-05](#r-05) | info | confirmed | Results change at noise level with the number of MPI processes |
| [A-01](#a-01) | high | confirmed | Python API is broken beyond repair (Python 2, not built, ABI out of sync) |
| [M-01](#m-01) | medium | confirmed | ~6 500 lines (15 %) of C are never compiled |
| [M-02](#m-02) | medium | code reading | A model is defined in 7 different places; duplicated unreachable code |
| [M-03](#m-03) | low | confirmed | CI (Travis) is dead; build docs mention obsolete steps |
| [P-01](#p-01) | low | confirmed | CLI sleeps 1 s during initialisation |
| [P-02](#p-02) | medium | code reading | Snapshots gather every link through rank 0 one message at a time |
| [P-03](#p-03) | ? | hypothesis | Scheduler, barriers and step-size resets in `Advance`: needs profiling |
| [S-01](#s-01) | for discussion | code reading | Parent states indexed with `dim` instead of `max_dim` in the equations |
| [S-02](#s-02) | for discussion | code reading | Model 254 baseflow uses `max(0.001, q_b)` in its sink term |
| [S-03](#s-03) | for discussion | code reading | Potential evaporation assumes a 30-day month |
| [S-04](#s-04) | for discussion | code reading | Models 400–405: `temperature == 0` treated as "no snow" |
| [S-05](#s-05) | for discussion | code reading | Snapshot filter rewrites cumulative states with `fmod(x, 1e200)` |
| [S-06](#s-06) | for discussion | code reading | Model 254 evaporation always runs at the full potential rate; clamping then creates water |
| [D-01..03](#d-01-to-d-03) | low | code reading | `docs/builtin_models.rst` disagrees with the model 254 code in 3 places |

---

## Bugs

### B-01
**Model 254 uses the snapshot filter of model 256: heap buffer overflow.** *Critical, confirmed.*

`SetOutputConstraints` in `src/models/definitions.c:885-893` has no `break;` after
`case 254:`. Execution *falls through* into `case 256:` (a classic C pitfall: a
`switch` keeps executing the following cases until it meets a `break`). Model 254
therefore gets `OutputConstraints_Model256_Hdf5`, which reads and writes `states[7]`.
Model 254 only has 7 states (`states[0]` … `states[6]`).

The filter runs on a packed buffer (`src/processdata.c:1892-1910`): each record is a
4-byte link id followed by `dim` doubles. `states[7]` is the first 8 bytes of the
*next* link's record. For the last link it is 8 bytes past the end of the `malloc`
(a heap buffer overflow).

Evidence:
```
==7192==ERROR: AddressSanitizer: heap-buffer-overflow ... READ of size 8
    #0 OutputConstraints_Model256_Hdf5 src/models/output_constraints.c:60
    #1 DumpStateH5 src/processdata.c:1910
    #2 Advance src/advance.c:108
0x... is located 0 bytes after 381540-byte region  (allocated at processdata.c:1892)
```
With a normal (non-sanitizer) build, `examples/clearcreek.gbl` **crashes on 1 MPI process**:
```
Fatal glibc error: malloc.c:2599 (sysmalloc): assertion failed ...
```
It "works" with `mpirun -n 4` (as in the README) only because the last link then
belongs to another process, so the overflowing write never happens (see B-02).
Adding the missing `break;` was verified (temporarily) to remove the crash.

**Proposed fix:** add `break;`. Additionally make every filter receive `dim` and
never index beyond it.

### B-02
**Snapshot values are filtered only on rank 0.** *High, code reading (consistent with B-01 crashing only on 1 process).*

In `DumpStateH5` (`src/processdata.c:1903-1911`) the output filter
(`OutputConstrainsHdf5`) is applied only to links that live on process 0. Values
received from other processes (`MPI_Recv` branch) are written unfiltered. The same
simulation therefore writes a *different* snapshot file depending on the number of
MPI processes. That is a reproducibility problem, because snapshots are used as
initial conditions for the next run.

**Proposed fix:** apply the filter after `MPI_Recv` too (or on the sending side).

### B-03
**`outputfile` is closed twice.** *High, confirmed.*

`Asynch_Delete_Temporary_Files` (`src/asynch_interface.c:1077-1078`) calls
`fclose(asynch->outputfile)` but does not set it to `NULL`. `Asynch_Free`
(`src/asynch_interface.c:442-443`) then closes it again. Closing a `FILE*` twice is
undefined behaviour. glibc detects it and aborts:
```
free(): double free detected in tcache 2
... exited on signal 6 (Aborted)
```
`Asynch_Free` is only called when `NDEBUG` is *not* defined (`src/asynch_cli.c:351-353`),
so this only hits debug builds. That is probably why the README tells you to compile with
`-DNDEBUG`. Every example currently exits with code 134 in a debug build, even though
the results were written correctly.

**Proposed fix:** `asynch->outputfile = NULL;` after the `fclose`, and call `Asynch_Free`
in all builds.

### B-04
**Solver index 3/4 crashes.** *High, confirmed.*

The global file comment says `%Numerical solver index (0-3 explicit, 4 implicit)`.
In reality (`src/riversys.c:686-690`) the table contains:

| index | method | type |
|---|---|---|
| 0 | RK3(2) dense ("RKDense3_2") | explicit |
| 1 | RK4(3) dense ("TheRKDense4_3") | explicit |
| 2 | Dormand–Prince 5(4) dense ("DOPRI5_dense") | explicit |
| 3 | Radau IIA order 3 | **implicit, but its stepper `steppers/implicit.c` is not compiled** |

The index read in `src/config_gbl.c:628-630` is never validated. Running `examples/test.gbl` with index 3,
4 or 7 gives a segmentation fault (exit 139). With index 3 you first see
`Warning: No solver selected for link ID 1`.

**Proposed fix:** validate the index (0–2) with a clear error message; fix the comments in all `.gbl` files and docs.

### B-05
**`Destroy_ErrorData` frees the wrong addresses.** *Medium, code reading + compiler warning.*

`src/system.c:204-207`: `free(&error->abstol)` frees the *address of the field*
(inside a struct) instead of the memory the field points to. It should be
`free(error->abstol)`. It is reached only when tolerances come from an `.rkd` file and
the solver is freed (debug builds).

### B-06
**`Asynch_Get_Num_Links` truncates.** *Medium, code reading.*

`src/asynch_interface.c:500` returns `unsigned short` (max 65 535). State-wide
networks (e.g. Iowa, ~400 000 links) are silently truncated. The CLI does not use it,
but any external program (and a future Python API) would.

### B-07
**`DumpStateH5` edge cases.** *Medium, code reading.*

`src/processdata.c:1861-1863`: `while (assignments[i] != my_rank) i++;` runs past the
end of the array if process 0 owns no link (possible with many processes and a small
network). The buffer `data_storage` allocated at line 1892 is never freed (a memory
leak at every recurrent snapshot).

### B-08
**Misaligned `double` access.** *Medium, confirmed by UndefinedBehaviorSanitizer.*

Snapshot records are packed as `uint32 + doubles`, so the doubles sit at addresses
that are not multiples of 8, and the filters access them through `double*`
(`src/models/output_constraints.c`). This is undefined behaviour in C. x86 tolerates it,
but other architectures (and optimisers) may not. **Fix:** filter a properly aligned
copy before packing it.

### B-09
**Debug print in model 402.** *Low.* `src/models/check_state.c:48-55` has `int debug = 1;`
and prints `found dam_check_qvs_402` on every call. That floods the output and slows runs with dams.

### B-10
**Compiler-detected mistakes.** *Low.*
* `src/forcings.c:176` calls `Create_Rain_Data_Par_IBin` without a prototype (implicit
  declaration). The call works only by luck of the calling convention.
* `src/models/check_state.c:84` prints an `unsigned int` with `%f`.
* `src/riversys.c:361-363`: misleading indentation. The second `printf` runs on all processes.

### B-11
**Unchecked input reading.** *Low → medium for users.* About 75 calls to `fscanf`/`fread`
(mostly `src/riversys.c`, `src/processdata.c`) ignore the return value. A truncated or
malformed `.rvr`/`.prm` file is not reported and leaves variables uninitialised.

### B-12
**`.uini` reader does not detect missing values.** *Medium, code reading.*
`src/riversys.c:1163-1170` reads `no_ini_start` values and checks
`if (fscanf(...) == 0)`. At end of file `fscanf` returns `EOF` (−1), not 0, so a file
with too few values is accepted, and the missing states keep whatever was in memory
(`malloc` does not zero). The header's model id (`%*i`) is ignored as well.
`examples/clearcreek.uini` is such a file: its header says model **252** and it gives
**4** values, while model 254 reads 7 (`no_ini_start = dim`). It works only because
`ReadInitData` for model 254 happens to overwrite exactly the 3 missing states (4, 5, 6).
**Fix:** check `!= 1`, and warn when the model id differs.

---

## Reproducibility

### R-01
**No regression testing.** *High.* `make check` runs a single unit test (`days_in_month`).
Nothing checks that the model still produces the same hydrographs. **Done in this
phase:** `tests/regression/run_examples.py` (see [06_reproducibility.md](06_reproducibility.md)).

### R-02
**Clearcreek reference is from another configuration.** *Medium, confirmed.*
`examples/results/clearcreek.pea` was committed in 2015 (commit `f02517e`, the first
import), by code and inputs that have changed a lot since. 5 013 of the 6 359 links
still match it within tolerance. For the outlet (link 2527), however, the reference peak is
at **3001 min**, while `clearcreek.gbl` only simulates **1440 min** (one day), so the
reference was produced with a longer simulation, and today's outlet "peak" is simply the last value
of the run. The reference cannot be used to validate the current example.
**Needs a decision:** regenerate the reference (after fixing B-01), or restore the original configuration.

### R-03
**Model 259 benchmark cannot be reproduced.** *Medium, confirmed.* The 2018 commit that
added the benchmark (`cba763b`) was built and run: it produces output **bit-identical to
today's code**, and both differ from the benchmark (outlet peak 0.696 vs 0.755 m³/s).
So the code has *not* changed. The benchmark was produced with an input that is not
in the repository, most likely model 259's own `evap.mon` on the original cluster
(`/Dedicated/IFC/.../mdl259a/evap.mon`). With zero evaporation the peak is 0.845, so the
original file lies between the two. **Needs a decision:** regenerate the benchmark with
the repository's `evap.mon`.

### R-04
**Examples 258/259 referenced a cluster path.** *Fixed in this phase.* Their `.gbl`
files pointed to `/Dedicated/IFC/projects/asynch_1_4_3b/tests/mdl25Xa/evap.mon`. They now
use `../common/evap.mon`, like the other examples. With this change, model 258 reproduces its
benchmark **bit for bit**.

### R-05
**Results depend (slightly) on the number of processes.** *Information.* ASYNCH is
asynchronous: each link has its own adaptive time step, and with several processes the
order of computation and the data available from upstream change. Observed differences:
relative ≤ 3·10⁻⁴ on small values, ≤ 10⁻⁵ on peaks. That is below the solver
tolerances, so it is not a bug, but it means results should be compared **with a
tolerance**, never byte by byte.

---

## Python API

### A-01
**The Python API does not work and cannot be repaired incrementally.** *High, confirmed.*
* `py/` is not part of the build (`SUBDIRS = src tests tools` in `Makefile.am`).
* `py/asynch_interface_py.c` does not compile against the current headers
  (`unknown type name 'MPI_Comm'`, `incomplete typedef 'AsynchSolver'`, …).
* `py/asynch_interface.py` and `asynchdist.py` use Python 2 syntax (`print 'x'`).
* The library path is hard-coded: `ASYNCH_LIBRARY_LOCATION = '/home/ssma/NewAsynchVersion/libs/libasynch_py.so'`.
* 14 of the 60 C functions it calls no longer exist (for example `Asynch_Get_Number_Links`,
  `Asynch_Set_Output`, `Asynch_Get_Total_Simulation_Time`).
* It re-declares C structs (`UnivVars`, …) in `ctypes` with the *old* field layout.
  Even if it loaded, it would read and write memory at the wrong offsets.

**Recommendation (for discussion):** rewrite it as a thin binding over a small, stable
C API that exposes only *opaque handles* and getter/setter functions (never struct
layouts). Build it as a shared library and wrap it with `ctypes` or `cffi`. A first useful scope:
run a `.gbl`, get/set states and parameters, read hydrographs into NumPy.

---

## Maintainability

### M-01
**Dead code.** These files are in the repository but **not compiled** (`src/Makefile.am`):

| file | lines | what it is |
|---|---|---|
| `src/rkmethods.c` | 3132 | old version of solvers/steppers (old `VEC`/`MAT` API) |
| `src/rainfall.c` | 1215 | old forcing reader |
| `src/asynchdist_custom.c` | 666 | old custom-model example |
| `src/steppers/explicit_discont.c` | 477 | stepper for discontinuous models |
| `src/steppers/implicit.c` | 464 | Radau implicit stepper (see B-04) |
| `src/steppers/assim.c` | 279 | data-assimilation stepper |
| `src/modeloutputs.c` | 239 | old output routines |
| `src/models/model.c` | 47 | |

That is about 6 500 lines, 15 % of the C code. Also in `src/models/definitions.c`,
`ReadInitData`, the branches for models 200, 254, 255, 256 and 257 at lines 3629-3704
are **unreachable duplicates**, because the same `if/else` chain already matched those models above.
Recommendation: move the dead files to an `attic/` folder (or delete them; git keeps the history).

### M-02
**A model is spread over 7 places.** Adding or reading model *N* means finding its
`case`/`if` in `SetParamSizes`, `SetOutputConstraints`, `ConvertParams`,
`InitRoutines`, `Precalculations`, `ReadInitData` (all in `definitions.c`, 4 063
lines), plus its equations in `equations.c` (6 293 lines). Mistakes like B-01 are a
direct consequence. Recommendation (later phase): one descriptor per model (struct
with sizes + function pointers) in one file per model family.

### M-03
**Tooling.** `.travis.yml` targets travis-ci.org, which shut down in 2021, so there
is no working CI. Recommendation: GitHub Actions running the build and the regression harness.
The root `.gitignore` also lists `examples` (and `*.rvr`, `*.str`, …), although those files
are tracked. `git add examples/...` therefore refuses to stage changes to the examples, and
`git add -u` (or `-f`) is needed. Recommendation: ignore only generated outputs (`examples/**/results/`).

---

## Performance

These are hypotheses from reading the code. They must be **measured** (profiling a large
network) before anything is changed.

### P-01
`src/asynch_cli.c:320` sleeps for 1 s (`ASYNCH_SLEEP(1)`) before the computation.
Negligible for large runs, but it makes up 99 % of the runtime of the small examples.
(On Windows the same macro sleeps 1 ms, because `Sleep` takes milliseconds.)

### P-02
Recurrent HDF5 snapshots (`DumpStateH5`, `src/processdata.c:1893-1936`) send **one
synchronous MPI message per link** to process 0. For 400 000 links that is 400 000
round-trips per snapshot. A single `MPI_Gatherv` would do the same work in one collective call.

### P-03
In `Advance` (`src/advance.c`):
* the next link to compute is found with a linear scan (`around` loop), `O(my_N)`;
* two `MPI_Barrier`s plus a duplicated `Transfer_Data_Finish` run at every forcing
  period (the code itself says "This is sloppy");
* `InitialStepSize` is recomputed for *every* link at every forcing period.

---

## Scientific review items (for discussion)

These are not necessarily bugs. They are places where a modelling choice is hidden in the
code and should be written down, and possibly revisited, by a hydrologist.

### S-01
In the model equations, the parents' states are read as `y_p[i * dim]`
(e.g. `model254`, `src/models/equations.c:1667-1684`), but the solver stores them with
stride `max_dim` (`src/steppers/explicit.c`, `stages_parents_approx + i * max_dim`).
Both are equal as long as every link has the same number of states, which is true today.
It becomes silently wrong if links with different dimensions are ever mixed (for example
reservoirs or coupled models). Recommendation: use `max_dim` (it is already passed to every function).

### S-02
Model 254's baseflow equation uses `q_b = max(0.001, y[6])` in its outflow term
(`equations.c:1638`). The baseflow state can therefore never drain below 0.001 m³/s
through that term. This is a numerical safeguard (it avoids `q_b → 0` problems), but it
changes the water balance at low flow and should be documented as part of the model.

### S-03
Potential evapotranspiration is converted from mm/month to m/min with a fixed 30-day
month (`equations.c:1621`). February and 31-day months are off by up to 7 %.

### S-04
Models 400–405 test `if (temperature != 0 & temperature < temp_thres)`
(`equations.c:2514`, 2676, 2834, 3029, 3296, 3437). A temperature of exactly 0 °C
(probably used as "no data") is never treated as snow. `&` (bitwise) is used instead
of `&&` (logical); the result is the same here, but it looks accidental.

### S-05
The snapshot filters (`src/models/output_constraints.c`) set values below 10⁻¹² to 0
and replace values above 10²⁰⁰ with `fmod(x, 1e200)`. Snapshots are used as initial
conditions, so this silently changes the state of the next run. That is fine for
round-off negatives, but the `fmod` behaviour should be justified or removed.

### S-06
In model 254 (`equations.c:1642-1654`) evaporation is split between the storages in
proportion to their relative fullness, so `e_p + e_t + e_s = e_pot` **whenever any
storage holds water, however little**. Near-empty storages are then over-drawn,
become negative, and are clamped back to 0 by `CheckConsistency_Nonzero_AllStates_q`,
which silently *adds* water. The water balance does not close in dry periods. A
common remedy is to scale actual ET by availability (e.g. `min(e_pot, storage/Δt)` or
a smooth factor `s/(s+ε)`), but this changes the model and must be a deliberate,
documented decision.

---

## Documentation errors

### D-01 to D-03
`docs/builtin_models.rst`, section *Top Layer Hydrological Model* (model 254):
* **D-01** 1/τ shows `L · 10⁻³` with L in km. It should be `L · 10³`. The code is correct.
* **D-02** the baseflow equation shows `+ q_b,in(t)`. The code has `+ 60·q_b,in` (dimensionally
  consistent) and the floor `max(0.001, q_b)` (S-02).
* **D-03** V_r is described as m³/s. It is an accumulated depth in m.

Details: [04_model_254_explained.md §4.7](04_model_254_explained.md#47-documentation-discrepancies-found-while-writing-this-page).
