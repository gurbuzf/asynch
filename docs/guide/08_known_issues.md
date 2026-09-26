# 8. Known issues

Known bugs, risks and open scientific questions in ASYNCH, found by building and running
the code and by reading it (September 2026). Any fix should be verified with the regression
harness ([09_reproducibility.md](09_reproducibility.md)).

How each item was established:

* **Confirmed**: reproduced by running the code. The evidence is quoted: a crash,
  an AddressSanitizer report, a comparison.
* **Code reading**: visible in the source, but not (yet) triggered by an example.
* **Open question**: a scientific or design question, not necessarily a bug.
  These need a hydrologist's judgement, not just a programmer's.

Severity scale: **critical** (memory corruption / wrong results / crash in normal
use), **high** (crash or wrong result in a plausible configuration), **medium**,
**low** (cosmetic, or only in unusual situations).

Line numbers refer to commit `84da43a` (the state of `master` at the time of writing).

---

## Summary table

| ID | Severity | Status | One-line description |
|----|----------|--------|----------------------|
| [B-01](#b-01) | **fixed** | confirmed | Model 254 uses model 256's snapshot filter: heap buffer overflow, crashes clearcreek on 1 process |
| [B-02](#b-02) | **fixed** | code reading | Snapshot values are filtered only for links owned by MPI rank 0: output depends on process count |
| [B-03](#b-03) | **fixed** | confirmed | Output file closed twice at shutdown: every debug build aborts at the end of a run |
| [B-04](#b-04) | **fixed** | confirmed | Solver index 3 or 4 (advertised as "implicit") segfaults; the index is never validated |
| [B-05](#b-05) | **fixed** | code reading | `Destroy_ErrorData` frees addresses of struct fields instead of the pointers |
| [B-06](#b-06) | **fixed** | confirmed | `Asynch_Get_Num_Links` returns `unsigned short`: wrong for networks > 65 535 links |
| [B-07](#b-07) | **fixed** | code reading | `DumpStateH5` loops past the array end if rank 0 owns no link; leaks its buffer |
| [B-08](#b-08) | **fixed** | confirmed (UB sanitizer) | Misaligned `double` reads/writes in snapshot filters (undefined behaviour) |
| [B-09](#b-09) | **fixed** | code reading | Model 402 dam check prints a debug line on every call |
| [B-10](#b-10) | **fixed** (except riversys.c indentation) | compiler | Missing prototype for `Create_Rain_Data_Par_IBin`; wrong `printf` format in `check_state.c` |
| [B-11](#b-11) | low | code reading | ~75 `fscanf`/`fread` return values ignored: malformed input files are not detected |
| [B-12](#b-12) | **fixed** | code reading | `.uini` reader misses "not enough values" (checks `== 0`, `fscanf` returns `EOF`); clearcreek.uini is short |
| [B-13](#b-13) | **fixed** | confirmed (ASan) | Solver methods 0 and 1 used Butcher coefficients from freed stack memory: random results or endless runs |
| [B-14](#b-14) | **fixed** | confirmed | Reading an `.rkd` file (per-link tolerances) never finished: 5 defects in `Build_RKData` |
| [B-15](#b-15) | **fixed** | confirmed | A missing output folder loses all results, yet the run ends with a success exit code |
| [B-16](#b-16) | **fixed** | confirmed (ASan) | Links with more than 8 parents overflowed memory; reader and solver disagreed on the limit |
| [B-17](#b-17) | **fixed** | confirmed | Library functions that crashed with built-in models or were missing (global parameters, duration, init file) |
| [B-18](#b-18) | **fixed** | code reading | `.ini` readers stored the discontinuity state on the wrong link; other readers passed it as the dam flag |
| [B-19](#b-19) | **fixed** | code reading | Model 190 read a third forcing value that does not exist (unused, no effect on results) |
| [B-20](#b-20) | **fixed** | confirmed | Custom outputs of non-interpolated states were written as 0 / memory contents |
| [B-21](#b-21) | **fixed** | code reading | Custom models inherited the snapshot filter of the built-in model with the same number |
| [B-22](#b-22) | **fixed** | unit test | Wrong constant in the Dormand-Prince dense-output derivative (no effect: multiplied by 0) |
| [B-23](#b-23) | **fixed** | unit test | Models 263 and 601-603 wrote/read one or two parameters past the per-link array |
| [B-24](#b-24) | **fixed** | unit test | 7 model numbers without equations crashed; RK tables shared by all solvers of a program |
| [B-25](#b-25) | **fixed** | test | Binary rain files: file past the range read, last file lasted 0.0001 min, overflow, crash on a missing file |
| [R-01](#r-01) | fixed | confirmed | No automated regression tests; only one unit test (`days_in_month`) |
| [R-02](#r-02) | **resolved** | confirmed | clearcreek references (2015) differ: another configuration, and a 2021 change to model 254 |
| [R-03](#r-03) | medium | confirmed | Model 259 benchmark cannot be reproduced from the files in the repository |
| [R-04](#r-04) | fixed | confirmed | Examples 258/259 pointed to a file on the original developers' cluster |
| [R-05](#r-05) | info | confirmed | Results change at noise level with the number of MPI processes |
| [A-01](#a-01) | **resolved** | confirmed | Old Python API broken beyond repair; replaced by the `python/` package (chapter 10) |
| [M-01](#m-01) | medium | confirmed | ~6 500 lines (15 %) of C are never compiled |
| [M-02](#m-02) | medium | code reading | A model is defined in 7 different places; duplicated unreachable code |
| [M-03](#m-03) | low | confirmed | CI (Travis) is dead; build docs mention obsolete steps |
| [P-01](#p-01) | low | confirmed | CLI sleeps 1 s during initialisation |
| [P-02](#p-02) | medium | code reading | Snapshots gather every link through rank 0 one message at a time |
| [P-03](#p-03) | ? | hypothesis | Scheduler, barriers and step-size resets in `Advance`: needs profiling |
| [S-01](#s-01) | open question | code reading | Parent states indexed with `dim` instead of `max_dim` in the equations |
| [S-02](#s-02) | **resolved** | confirmed | Model 254 baseflow floor `max(0.001, q_b)` (added 2021) removed; original 2015 equation restored |
| [S-03](#s-03) | open question | code reading | Potential evaporation assumes a 30-day month |
| [S-04](#s-04) | open question | code reading | Models 400–405: `temperature == 0` treated as "no snow" |
| [S-05](#s-05) | open question | code reading | Snapshot filter rewrites cumulative states with `fmod(x, 1e200)` |
| [S-06](#s-06) | open question | code reading | Model 254 evaporation always runs at the full potential rate; clamping then creates water |
| [D-01..03](#d-01-to-d-03) | low | code reading | `docs/builtin_models.rst` disagrees with the model 254 code in 3 places |

---

## Bugs

### B-01
**Model 254 uses the snapshot filter of model 256: heap buffer overflow.** *Critical, confirmed.*
**Fixed** (2026-09-25): the missing `break;` was added. clearcreek now runs on 1 process; with
2 processes all 27 output files are bit-identical to the original code (see CHANGELOG).

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
**Fixed** (2026-09-25): the filter is applied to every link. In a 2-process clearcreek snapshot, the
original code left 4 values in (0, 1e-12) unfiltered; the fixed code leaves none.

In `DumpStateH5` (`src/processdata.c:1903-1911`) the output filter
(`OutputConstrainsHdf5`) is applied only to links that live on process 0. Values
received from other processes (`MPI_Recv` branch) are written unfiltered. The same
simulation therefore writes a *different* snapshot file depending on the number of
MPI processes. That is a reproducibility problem, because snapshots are used as
initial conditions for the next run.

**Proposed fix:** apply the filter after `MPI_Recv` too (or on the sending side).

### B-03
**`outputfile` is closed twice.** *High, confirmed.*
**Fixed** (2026-09-25): the pointer is set to `NULL` after each `fclose`. Debug and sanitizer
builds now run every example to the end with exit code 0.

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
**Fixed** (2026-09-25): the index is validated (in the `.gbl` file and in `.rkd` files). An invalid
value stops the run with `Error: numerical solver index 4 in the global file is not valid. Use 0 (RK 3(2)),
1 (RK 4(3)) or 2 (Dormand-Prince 5(4)).` The comments in the example `.gbl` files and in the docs were corrected.

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
**Fixed** (2026-09-25) together with B-14: it frees the arrays and the per-link structure.

`src/system.c:204-207`: `free(&error->abstol)` frees the *address of the field*
(inside a struct) instead of the memory the field points to. It should be
`free(error->abstol)`. It is reached only when tolerances come from an `.rkd` file and
the solver is freed (debug builds).

### B-06
**`Asynch_Get_Num_Links` truncates.** *Medium, code reading.*

`src/asynch_interface.c:500` returns `unsigned short` (max 65 535). State-wide
networks (e.g. Iowa, ~400 000 links) are silently truncated. The CLI does not use it,
but any external program would.
**Fixed** (2026-09-25): returns `unsigned int`. On a synthetic network of 70 000 links it returns 70 000; the old
type would have returned 4 464.

### B-07
**`DumpStateH5` edge cases.** *Medium, code reading.*
**Fixed** (2026-09-25): the search is bounded and the buffers are freed.

`src/processdata.c:1861-1863`: `while (assignments[i] != my_rank) i++;` runs past the
end of the array if process 0 owns no link (possible with many processes and a small
network). The buffer `data_storage` allocated at line 1892 is never freed (a memory
leak at every recurrent snapshot).

### B-08
**Misaligned `double` access.** *Medium, confirmed by UndefinedBehaviorSanitizer.*
**Fixed** (2026-09-25): states are filtered in an aligned array before being packed. The sanitizer
reports for the examples went from 21 to 0.

Snapshot records are packed as `uint32 + doubles`, so the doubles sit at addresses
that are not multiples of 8, and the filters access them through `double*`
(`src/models/output_constraints.c`). This is undefined behaviour in C. x86 tolerates it,
but other architectures (and optimisers) may not. **Fix:** filter a properly aligned
copy before packing it.

### B-09
**Debug print in model 402.** *Low.* `src/models/check_state.c:48-55` has `int debug = 1;`
and prints `found dam_check_qvs_402` on every call. That floods the output and slows runs with dams.
Model 403 did the same. **Fixed** (2026-09-25): debugging is off by default.

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
**Fixed** (2026-09-25): missing values are detected. ASYNCH warns and sets them to 0 (the buffer is
zero-initialised); a value that is not a number is an error; a model number that differs from the
`.gbl` gives a warning. The check revealed that `examples/more/common/test.uini` (3 values) is also
short for models 258 and 259, which read 4. Their subsurface storage started from uninitialised memory
in the original code, which happened to be 0. It is now 0 by design, and results are bit-identical.
`examples/clearcreek.uini` now has the right model number and all 7 values.

### B-13
**RK 3(2) and RK 4(3) read their coefficients from freed memory.** *Critical for users of
methods 0 and 1, confirmed.* Found while testing the fix of B-04.
`RKDense3_2` and `TheRKDense4_3` (`src/solvers/rk3_2_dense.c`, `src/solvers/rk4_3_dense.c`)
stored in the `RKMethod` struct pointers to their *local* coefficient arrays (`A`, `b`, `c`, `d`,
`e`). Local arrays live on the stack and disappear when the function returns, so every time step
then read whatever else happened to be on the stack. AddressSanitizer:
`stack-use-after-return ... in ExplicitRKSolver src/steppers/explicit.c:120`, pointing at
array `c` of `TheRKDense4_3`. With method 1, `examples/test.gbl` ran forever in most runs (with 1
or 2 processes, in the original code too). **Any result computed with solver index 0 or 1 by
earlier versions is unreliable.** Method 2 (Dormand–Prince), used by all examples, stores its
tables as `static` and was never affected.
**Fixed** (2026-09-25): the tables are `static`. Methods 0 and 1 now finish, are free of sanitizer
reports and bit-reproducible with 1 process. They agree with method 2 within the expected accuracy
(clearcreek, 6 359 links: peak discharge differs by at most 7.7e-4 m³/s, median relative
difference 0.1 %).

### B-14
**`.rkd` files (tolerances and method per link) could not be used.** *High for users of this
option, confirmed.* Found while fixing B-04 and B-05. With a solver flag of `1` in the `.gbl`, the
original code never got past "Reading dam and reservoir data...". `Build_RKData`
(`src/riversys.c`) had five defects:
1. the loops reading the tolerances incremented `i` instead of `j` (`for (j = 0; j < num_states; i++)`),
   an endless loop running off the arrays;
2. the array of method indices had `num_states` entries instead of one per link;
3. the broadcast to the other processes sent `methods` (the table of RK methods) instead of the method
   indices, overwriting memory;
4. the per-link `ErrorData` structure was never allocated before being written to;
5. the link ids in the file were read but not used: rows were assumed to be in network order.

**Fixed** (2026-09-25): the reader was rewritten. Rows are matched to links by id; every value is
checked, and a bad file stops the run with a clear message (unknown or repeated id, missing link or
value, invalid method, too few tolerances for the model). The format is now documented in
`docs/input_output.rst`. `examples/test_rkd.gbl` + `examples/test.rkd` repeat the settings of
`examples/test.gbl` for every link. They give **bit-identical** results with 1 process, and are part of
the regression tests.

### B-15
**Unwritable outputs are not fatal.** *High, confirmed* (while testing the documentation). If a
folder named in the `.gbl` for hydrographs, peaks or snapshots does not exist, every write prints
`Error: could not open h5 file ...` / `Error: Cannot open peakflow file ...` (27 lines for `test.gbl`), but the
simulation runs to the end and `asynch` **exits with code 0**, the code for success, having written no results.
In a script or an operational chain, the failure goes unnoticed. The simulation time is also wasted.
**Fixed** (2026-09-25): `Read_Global_Data` (`src/config_gbl.c`) checks that the folders of the hydrograph, peak,
snapshot and temporary files exist and are writable, and stops before computing otherwise. `main`
(`src/asynch_cli.c`) now checks the return values of the final output functions, and exits with `EXIT_FAILURE` if
one failed.

### B-16
**Links with many parents overflowed memory.** *High, confirmed* (while testing B-06 on a synthetic network).
The time-step routines (`src/steppers/*.c`) keep the parents' data in an array of `ASYNCH_LINK_MAX_PARENTS` = 8
entries, but the network reader (`Create_River_Network`, `src/riversys.c`) accepted up to 10 parents, and stored
each parent *before* checking the limit. A link with 9 or 10 parents made every time step write past the array
(AddressSanitizer: `stack-buffer-overflow in ExplicitRKSolver`, the run aborted). With 11 or more parents the reader
itself wrote past its buffer.
**Fixed** (2026-09-25): one limit, `ASYNCH_LINK_MAX_PARENTS` = 16, is used by the reader and the solvers; both readers
(file and database) check it before storing. A network with 70 000 links and 10 parents per main-channel link now
runs cleanly (release and sanitizer builds, 1 and 2 processes). One with 21 parents stops with
`Error: link 1 has 21 parents; ASYNCH supports at most 16 (ASYNCH_LINK_MAX_PARENTS in src/constants.h).`

### B-17
**Several library functions crashed or did not exist.** *Medium, confirmed* (while writing the Python package).
They only concern programs that use ASYNCH as a library; the `asynch` program does not call them.
* `Asynch_Get_Size_Global_Parameters` and `Asynch_Set_Global_Parameters` read `asynch->model`, which only exists for
  custom models: with a built-in model they dereferenced a null pointer. `Asynch_Set_Global_Parameters` also did not
  update the count kept in `globals`, so `Asynch_Get_Global_Parameters` copied the old number of values.
* `Asynch_Set_Total_Simulation_Duration` was declared in `asynch_interface.h` but never written: a program calling
  it did not link.
* `Asynch_Set_System_State` passed the discontinuity state where `check_state` expects the dam flag.
* `Asynch_Custom_Model` allocated a model that it immediately replaced (a leak), and a model created by
  `Asynch_Custom_Partitioning` alone (no equations) made the global-file reader call a null function.
* `Asynch_Set_Init_File` read before the start of names shorter than 4 characters, did not accept `.h5`
  initial states, and wrote into a null pointer when the global file took the initial states from a database.

**Fixed** (2026-09-25) in `src/asynch_interface.c`, `src/config_gbl.c` and `src/riversys.c`: the counts come from
`globals`, the missing function exists, the flags are passed in the right place, a custom model is recognised by
its callbacks (so a partitioning-only "model" keeps the built-in equations), and the file type is taken from the
extension (`.ini`, `.uini`, `.rec`, `.h5`).

### B-18
**Initial-state readers stored the discontinuity state on the wrong link.** *Medium, confirmed by reading.*
In `Load_Initial_Conditions` (`src/riversys.c`), the two `.ini` branches computed the state of the link at
location `loc` but stored it in `system[i]`, where `i` is only a loop counter. The `.rec`, `.dbc` and `.h5` branches
passed the state where `check_state` expects the dam flag. Only models with discontinuity states (the dam models) are
affected: their first step could start in the wrong regime. The shipped examples have no dams and do not change.
**Fixed** (2026-09-25).

### B-19
**Model 190 read a forcing that does not exist.** *Low, confirmed by reading.* `LinearHillslope_MonthlyEvap`
(`src/models/equations.c`) read `forcing_values[2]` into an unused variable, but model 190 has two forcings (the
array holds two values). The optimiser removes the unused read, so results were never affected; the line, added in
2017 together with model 195, is removed.

### B-20
**Custom time series outputs of states that are not interpolated were wrong.** *High, confirmed.* A program can add
its own outputs (`Asynch_Set_Output_Int/Double/Float`) and say which states they use. Those states must be
interpolated ("dense output") at the print times. The code added the states that were *already* interpolated, and
skipped the others; those were then written as whatever was in memory. Test: an output returning state 1 of model 190,
with State1 not otherwise printed, wrote **0** at every time instead of values around 0.001. Also, when called at the
documented moment (right after reading the global file), the links did not exist yet and nothing was added at all.
**Fixed** (2026-09-25): the used states are recorded before the model is initialised and added afterwards; the output
now equals State1 to its print precision (1, 2 and 3 processes). The same off-by-one (`>` instead of `>=` when checking
that a state exists) was fixed in `Initialize_Model`.

### B-21
**A custom model inherited the snapshot filter of the built-in model with the same number.** *Low, confirmed by reading.*
`SetOutputConstraints` chooses a filter for `.h5` snapshots from the model number of the global file, even for a
custom model, whose states may mean something else. Custom models now get no filter.

### B-22
**Wrong constant in the derivative of the Dormand-Prince dense output.** *Low, confirmed by a unit test.*
`DOPRI5_bderiv` (`src/solvers/dopri5_dense.c`) had `1144640195640` where 32805 x 3489224 = `114463993320` belongs
(the fifth coefficient). The derivative is only evaluated at theta = 1 (`src/steppers/explicit_index1_dam.c`), where
this term is multiplied by 0, so no result was affected. **Fixed** (2026-09-25).

### B-23
**Models 263, 601, 602 and 603 wrote and read past the parameter array of every link.** *High for users of these
models, confirmed by a unit test.* `SetParamSizes` (`src/models/definitions.c`) declared fewer parameters per link
(`num_params`) than it reads from disk (`num_disk_params`): 14 < 15 (263 and 601), 16 < 17 (602), 20 < 21 (603). The
reader stores every value read into an array of `num_params` doubles, so the last one was written past it. The
precalculations of 601-603 then read it (`v_0`, used for `invtau`) from there, and the equations of 263 read two values
(`v_B`, `k_tl`) past the array: results depended on whatever memory followed. **Fixed** (2026-09-25): the arrays have
room for every value read (15, 17, 21; 16 for model 263, whose equations use 16 values, all read from disk: its
parameter files or database queries must give 16 values per link).

### B-24
**Seven model numbers crashed at the first step; the Runge-Kutta tables were shared by all solvers.** *Medium,
confirmed by unit tests.*
* Models 200, 260, 300, 301, 315, 607 and 2000 have sizes in `SetParamSizes` but no equations (200 is meant for
  another program; 260's equation is commented out; the others have no `InitRoutines` branch). A run called a null
  function. `Initialize_Model` now stops with `Error: model N cannot be integrated by ASYNCH ... (no equations)`.
* `Build_RKData` (`src/riversys.c`) built the tables into a `static` array, shared by every solver of the program.
  With two solvers (easy from Python), creating the second rebuilt the tables of the first. Each solver now owns its
  array, and `Destroy_RKMethod` frees what the constructors allocate (it freed nothing; RK 4(3) pointed `b` to a static
  table, so it could not be freed consistently).

### B-25
**Rain from binary files: a file past the range was read, the last file lasted 0.0001 min, memory overflow, crash on
a missing file.** *High, confirmed by a test* (the same rain as a `.str` file and as binary files). Binary forcing
files (global file flags 2 and 6: one file per time step, used for radar rainfall) are read in passes of `chunk size`
files. In `src/forcings.c` the last file of a pass was capped at `last + 1`, a file outside the declared range, and
`src/forcings_io.c`:
* read it (flag 2: from a NULL file pointer if it did not exist, which crashed; flag 6: stopped);
* gave the value of the last file for 0.0001 min only, then 0 (it was only right when the file after the range existed);
* allocated `number of files + 1` values per link, but wrote `chunk size + 1`: a last pass with fewer files than the
  chunk size wrote past the array.

**Fixed** (2026-09-25): files `first` to `last` are read, the last one applies for a full time step, then 0 (as
documented); the arrays are large enough; a missing file stops the run with its name. Test
(`tests/python/test_forcings.py`): rain different at every link, written as `.str`, binary, gzipped binary and
irregular binary files, gives identical results. Runs whose files covered one step more than the declared range differ
only by the 0.0001 min of that extra file.

---

## Reproducibility

### R-01
**No regression testing.** *High.* `make check` runs a single unit test (`days_in_month`).
Nothing checks that the model still produces the same hydrographs. **Addressed by**
`tests/regression/run_examples.py` (see [09_reproducibility.md](09_reproducibility.md)). Since 2026-09-25
`make check` runs 23 C unit tests (`tests/check_asynch.c`), 68 tests of the Python package (`tests/python`) and the
9 example comparisons; the tests found B-22 to B-25. Line coverage: 66.5 % (chapter 9).

### R-02
**Clearcreek reference is from another configuration, and model 254 changed in 2021.** *Medium, confirmed.*
`examples/results/clearcreek.pea` (with `.dat` and `.rec`) was committed in May 2015 (commit
`b73fc2d`, the first import). For the outlet (link 2527) the reference peak is at **3001 min**,
while `clearcreek.gbl` only simulates **1440 min** (one day), so the reference cannot validate
today's example as it stands.

*Explained* (2026-09-25). The 2015 global file (`Global254.gbl` in `b73fc2d`) simulated **6000
minutes starting 2014-05-01**. All input files are byte-for-byte the same today. That configuration
is now `examples/clearcreek_2015.gbl`. Running it:
* with today's code, the references are **not** reproduced (hydrograph differences up to 0.085 m³/s;
  zeros where the reference has small baseflow values);
* with today's code and **one line** of `model254` restored to its 2015 form
  (`double q_b = y_i[6];` instead of `max(0.001, y_i[6])`), hydrographs and final states agree with the
  references within the solver tolerance (largest difference 9.4e-5, solver abs tolerance 1e-4), and peak
  discharges within 1.7e-4 m³/s.

So the difference is model 254 itself: the floor `max(0.001, q_b)` was added in January 2021, in commit
`93241a3`, whose message is "added model 194". That change of the operational model is not
mentioned anywhere. See S-02. The reference files are kept unchanged.

**Resolved** (2026-09-25): the 2015 equation was restored (S-02). `examples/clearcreek_2015.gbl` now
reproduces all three reference files: hydrographs within 9.5e-5, final states within 1.5e-5, and peak values
within 1.7e-4 m³/s (only 9 of 6 359 links above 1e-4; their peak times moved by 3–7 minutes, because peaks
are recorded at solver steps). `examples/clearcreek.gbl` itself still simulates a different period (one day
from 2017-01-01), so its comparison with the 2015 file stays a known mismatch by design.

### R-03
**Model 259 benchmark cannot be reproduced.** *Medium, confirmed.* The 2018 commit that
added the benchmark (`cba763b`) was built and run: it produces output **bit-identical to
today's code**, and both differ from the benchmark (outlet peak 0.696 vs 0.755 m³/s).
So the code has *not* changed. The benchmark was produced with an input that is not
in the repository, most likely model 259's own `evap.mon` on the original cluster
(`/Dedicated/IFC/.../mdl259a/evap.mon`). With zero evaporation the peak is 0.845, so the
original file lies between the two. The benchmark files are kept unchanged; the case stays
a known mismatch unless the original evaporation file is found.

### R-04
**Examples 258/259 referenced a cluster path.** *Fixed.* Their `.gbl`
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

**Resolved** (2026-09-25): replaced by the package in `python/` (chapter 10), a `ctypes` binding over the
shared library `libasynch.so` and a small C interface (`src/asynch_api.h`) that exposes only numbers, arrays and
opaque handles, never structure layouts. `py/`, `asynchdist.py` and `asynchdist_custom.py` were removed; the custom
model of `asynchdist_custom.py` is ported in `examples/python/custom_model.py` and reproduces model 191 exactly.

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
direct consequence. Possible improvement: one descriptor per model (struct
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

## Scientific review items (open questions)

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
(`equations.c:1638`). When the baseflow is below 0.001 m³/s, the channel still loses baseflow as if
it were 0.001 m³/s, so it drains faster than the linear reservoir would and is then clamped to 0 by
`check_consistency`. This changes the water balance at low flow.

This line was **not** part of the original model: it was added in January 2021 (commit `93241a3`,
"added model 194") and changed model 254's results (see R-02). With the 2015 form (`q_b = y[6]`),
today's code reproduces the original repository's clearcreek references within the solver tolerance.
**Resolved** (2026-09-25, owner's decision): the 2015 form `q_b = y[6]` is restored. The original
reference results for clearcreek (`examples/results/clearcreek.dat`, `.pea`, `.rec`) are now reproduced
within the solver tolerance.

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

Details: [05_model_254_explained.md §5.7](05_model_254_explained.md#57-documentation-discrepancies-found-while-writing-this-page).
