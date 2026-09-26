# 7. What was fixed, and why it matters

*Written for readers who do not program. Each item also has a short "C lesson" for those who
are learning the code; the full technical record is chapter 8 (`08_known_issues.md`), and every
change is in `CHANGELOG.md`.*

## 7.1 How every change was checked

Two comparisons are made after **every** change to the code:

1. **Against the results shipped with the original ASYNCH repository** (`examples/results/`,
   `examples/more/*/results_benchmark/`). These reference files are never modified. They are the benchmark.
2. **Against the original code itself**, run on the same inputs. With one processor, an unchanged
   result must be **identical to the last digit**; only a change that is meant to alter results may
   differ, and then the difference is measured and explained.

On top of that, special builds of the program that stop at the first memory error (the "sanitizers",
chapter 9) run every example. Chapter 9 explains how to repeat all of this yourself, with one command.

The figure below summarises the outcome against the six reference files of 2015: the orange bars are the
original code, the blue bars this version. Lower is better; below the dashed line means "within the solver's accuracy".

![Agreement with the 2015 reference results, before and after](figures/reference_agreement.png)

## 7.2 How serious is a bug? The four classes

| Class | Meaning for a user of the model |
|---|---|
| **Critical** | Can give **wrong numbers without any warning**, or crash, with standard settings or the shipped examples |
| **High** | Wrong numbers, a crash or an endless run in a documented option or a plausible setup; or results lost without being told |
| **Medium** | A crash with an obvious cause, or differences far too small to matter hydrologically |
| **Low** | No effect on results: messages, warnings, tidiness of the code |

A "silent" error is always worse than a crash: a crash is noticed, a wrong number is not.

## 7.3 Overview

| Area | Issue | Class | Status |
|---|---|---|---|
| Numerical solver | B-13: solver methods 0 and 1 computed with random numbers | **Critical** | fixed |
| Memory / outputs | B-01: the main example overwrote memory; crashed on one processor | **Critical** | fixed |
| Model equations | S-02: model 254 baseflow forced to 0 by a line added in 2021 | **High** | fixed (original equation restored) |
| Inputs | B-12: missing initial values were taken from random memory | **High** | fixed |
| Numerical solver | B-14: per-link solver settings (`.rkd`) never worked | **High** | fixed |
| Outputs | B-15: a missing output folder lost all results, yet the run "succeeded" | **High** | fixed |
| Network | B-16: a junction with more than 8 upstream streams crashed the run | **High** | fixed |
| Model equations | B-23: models 263, 601, 602, 603 read parameters from outside their memory | **High** | fixed |
| Inputs | B-25: rain from binary (radar) files: the last file almost ignored, crashes, memory overflow | **High** | fixed |
| Library / Python | B-20: user-defined outputs of some states were written as 0 | **High** | fixed |
| Python | A-01: the Python interface did not work at all | **High** | replaced (chapter 10) |
| Models | B-24: 7 model numbers without equations crashed; solvers of one program shared tables | Medium | fixed |
| Library | B-17: library functions that crashed with built-in models, or were missing | Medium | fixed |
| Inputs | B-18: dam models could start in the wrong regime when read from an `.ini` file | Medium | fixed |
| Library | B-06: programs using ASYNCH as a library got a wrong link count above 65 535 links | Medium | fixed |
| Numerical solver | B-04: an invalid solver number crashed the program | Medium | fixed |
| Outputs | B-02: snapshots depended slightly on the number of processors | Medium | fixed |
| Program end | B-03: debug versions crashed at the very end | Medium | fixed |
| Examples | two examples pointed to a computer at the University of Iowa | Medium | fixed |
| Memory | B-05, B-07, B-08: freeing the wrong memory, a leak, misaligned reads | Low | fixed |
| Messages | B-09, B-10: debug text printed at every step; compiler warnings | Low | fixed |
| Code | B-19, B-21, B-22: an unused out-of-range read, a filter applied to the wrong model, a typo multiplied by 0 | Low | fixed |

## 7.4 The critical issues

### B-13: solver methods 0 and 1 computed with random numbers — Critical

**What happened.** ASYNCH offers three numerical methods (the `%Numerical solver index` in the `.gbl`):
0 = RK 3(2), 1 = RK 4(3), 2 = Dormand–Prince 5(4). Each method is defined by a small table of fixed
coefficients. For methods 0 and 1 these tables were stored in a temporary place in memory that is
released as soon as the setup is finished. Every time step then read whatever happened to be in that place.

**Why it matters.** Results computed with method 0 or 1 by earlier versions of ASYNCH are unreliable:
the run either computed with meaningless coefficients, or never finished (the `test` example ran forever
in most attempts). Method 2, which all examples use, stores its table correctly and was never affected.

**Now.** The three methods run and agree with each other as they should (figure below: the curves overlap;
the lower panel shows that the differences stay below 0.00085 m³/s, which is 0.15 % of the peak).

![The three methods agree](figures/solver_methods_agree.png)

*C lesson* ([6.6](06_c_primer.md#66-memory-malloc--free)): a variable declared inside a function lives only
while the function runs. Keeping its address afterwards is a "dangling pointer". The fix was one word, `static`,
which makes the table live for the whole program.

### B-01: the main example overwrote memory — Critical

**What happened.** When writing a snapshot, model 254 used a filter written for model 256, which has
one more state. For each link it touched one number more than exists, writing into the neighbouring link's data,
and for the last link past the end of the memory reserved for the file. The cause was a single missing word,
`break`, in the list of models.

**Why it matters.** The flagship example `clearcreek.gbl` **crashed** on one processor. On several processors it
seemed to work, but memory was being overwritten, which can corrupt results in ways that cannot be predicted.

**Now.** Runs on any number of processors. The fix itself changed no result: on two processors, all 27 output
files were identical to the original's. (Model 254 results changed later, on purpose, with S-02 below.) *C lesson* ([6.7](06_c_primer.md#67-switch-falls-through)): in C, a `switch` keeps
running into the next case until it meets `break`.

## 7.5 The high-severity issues

### S-02: model 254 baseflow forced to zero — High

**What happened.** Model 254 tracks, besides the total discharge, the part of it that comes from
groundwater (baseflow, state `q_b`). In January 2021 one line of the model was changed, inside a code change titled
"added model 194", so that the channel always lost baseflow *as if* there were at least 0.001 m³/s of it. When there
was less, the model removed water that was not there, and the baseflow was pushed to zero. This line is not part of
the published model or of its documentation.

**Why it matters.** Over the 100-hour Clear Creek run, the reference baseflow at the outlet rises to 0.085 m³/s.
The 2021 code kept it at **0 for the whole run**: a 100 % error on that output. The total discharge was almost
unaffected (at most 0.0003 m³/s), because in this model the baseflow state is bookkeeping: it reports how much
of the flow is baseflow, and does not feed back into the total. Anyone using the baseflow output of model 254
since 2021 was affected.

**Now.** The original equation is restored (decision of the model owner). The reference results shipped with
ASYNCH are reproduced within the accuracy of the solver.

![Clear Creek outlet: total discharge and baseflow, before and after](figures/clearcreek_outlet_before_after.png)

### B-12: missing initial values taken from random memory — High

**What happened.** The initial-state file (`.uini`) gives one starting value per state. If it gave fewer values
than the model needs, ASYNCH did not notice, and the missing states started from whatever was in memory.

**Why it matters.** It happened in the shipped examples: models 258 and 259 need 4 values, but their file gives 3,
so the subsurface storage started from random memory. By luck that memory was 0; on another computer it may not be.

**Now.** Missing values are 0, a warning says so, and a mismatch between the model number in the file and in the
`.gbl` is reported. *C lesson* ([6.8](06_c_primer.md#68-reading-files-always-check-the-return-value)):
reading functions report end-of-file with a special value, which must be checked.

### B-14: per-link solver settings never worked — High

**What happened.** The `.rkd` option (a file giving tolerances and method for each link) is part of the documented
input format. Reading it contained five separate mistakes, the first being an endless loop: the program never got past
"Reading dam and reservoir data...".

**Now.** Rewritten and tested: a file that repeats the global settings for every link gives results identical to the
normal run, and a faulty file stops with a clear message. The format is now documented and has an example (`examples/test.rkd`).

### B-15: results silently lost when an output folder was missing — High

**What happened.** If a folder named in the `.gbl` for the outputs did not exist, ASYNCH computed the whole
simulation, printed `Error: could not open ...` lines while writing, and then **reported success** (exit code 0)
without having written any results. Scripts and operational chains that run ASYNCH check that exit code, so the
missing results went unnoticed. It was found while testing the exercise of chapter 2.

**Now.** Every output folder is checked before the computation starts, and a missing or read-only folder stops
the run at once with a message naming it. If writing still fails at the end (a full disk, for example), `asynch`
ends with an error code. *C lesson*: a program tells whoever started it whether it succeeded through its **exit
code** (the value returned by `main`, 0 = success). Printing an error is not enough.

### B-23: four models read parameters from outside their memory — High

**What happened.** Each link keeps its parameters in a small table. For models 263, 601, 602 and 603 the table was
declared one or two places shorter than the number of values the model reads from its parameter file. The last
value was written just past the end of the table, into memory that belongs to something else, and the model then read
it back from there (model 263 even read two values that were never stored: `v_B` and `k_tl`).

**Why it matters.** The results of these models depended on whatever happened to be in that memory: they could be
right by luck, change from one computer to another, or crash. Nothing warned. None of the shipped examples uses these
models, which is why it went unnoticed; a new unit test that checks the sizes of every model found it.

**Now.** The tables have room for every value. Model 263 needs **16 values per link** in its parameter file (it used
16 in its equations all along).

### B-25: rain from binary files — High

**What happened.** Operational runs often read rain from a series of binary files, one per time step (e.g. radar
rainfall every 5 minutes); the global file says which files to use, from number `first` to number `last`. The reader
asked for one file more than that range. If the folder held exactly the declared files, the program crashed (or, for
compressed files, stopped). If it held one more, the run went on, but the rain of the file `last` was applied for
0.0001 minutes instead of a full time step. In some configurations it also wrote past the end of its memory.

**Now.** Exactly the declared files are read, the last one applies for its full time step and then the rain is 0,
as the documentation says. A missing file stops the run with its name. Tested: the same rain given as a text file and in
the three binary formats gives identical results.

### B-20: user-defined outputs could be written as 0 — High

A program (or now a Python script) can add its own outputs, computed from the states of a link. The solver must be
told which states such an output uses, so that it computes them at the output times. The code did the opposite of what
it meant: it added the states that were already computed, and skipped the others, which were then written as 0.
Tested: an output of the surface storage of model 190 was 0 at every time, instead of values around 0.001 m.

## 7.6 Medium and low issues, in brief

* **B-04** (Medium): a solver number other than 0, 1 or 2 (the `.gbl` comment even suggested 3 and 4) crashed
  the program. It now stops with a message listing the valid values.
* **B-02** (Medium): snapshot values below 10⁻¹² were set to 0 only for links computed by the first processor, so
  snapshots differed slightly with the number of processors. Now the same rule applies to every link.
* **B-03** (Medium): the output file was closed twice at the very end, which crashed "debug" versions of the program
  (results were already written). Fixed.
* **Examples 258/259** (Medium): pointed to a file on a University of Iowa computer, so they could not run anywhere
  else. They now use the evaporation file shipped in the repository, and reproduce their reference exactly.
* **B-16** (High): at a junction, ASYNCH keeps the data of every upstream stream in a list with room for 8. The file
  reader accepted up to 10, and a junction with 9 or 10 upstream streams overwrote memory at every time step, which
  crashed the run. Now one limit of 16 applies everywhere, and a network exceeding it is refused with a clear message.
* **B-06** (Medium): the function that reports the number of links used a type that stops at 65 535. A 70 000-link
  network was reported as 4 464 links. It only affected programs that use ASYNCH as a library, such as the Python API.
* **B-24** (Medium): seven model numbers (200, 260, 300, 301, 315, 607, 2000) have sizes but no equations in
  ASYNCH; choosing one crashed at the first step. They are now refused with a message. Also, the tables of the
  numerical methods were shared by every solver of a program: harmless for the `asynch` program (one solver), wrong
  for a Python script that creates several.
* **B-17** (Medium): functions of the library used by other programs (such as the Python package) crashed with the
  built-in models, or did not exist although declared.
* **B-18** (Medium): for models with dams, the initial "regime" (e.g. whether a spillway flows) was stored on the
  wrong link when the initial state came from an `.ini` file.
* **B-19, B-21, B-22** (Low): model 190 read a third forcing that does not exist, into a variable it never used;
  custom models received the snapshot filter of the built-in model with the same number; a wrong constant in a formula
  that is only ever evaluated where it is multiplied by 0.
* **B-05, B-07, B-08** (Low): memory handling errors that did not change results: freeing the wrong address, a
  buffer never released, numbers read from misaligned memory addresses.
* **B-09, B-10** (Low): models 402 and 403 printed a debug line at every step; compiler warnings about
  a missing declaration and a wrong print format.

## 7.7 Python, and tests for everything

The Python interface of the original ASYNCH could not work any more (issue A-01: Python 2, not built, and it
assumed a memory layout that had changed). It is replaced by a new package, described in chapter 10. What it
changes for a user:

* a simulation can be run, stopped, inspected and changed from a Python script (states, parameters, outputs);
* **new models can be written in Python**, as C code that is compiled automatically (as fast as the built-in
  models) or as Python functions (slower, no compiler needed);
* global files and input files can be created from Python.

How we know the package is right: the files it writes are identical to those of the `asynch` program, byte for byte;
models 190 and 191 rewritten through it give exactly the numbers of the built-in models; and simple models with a known
exact solution (a chain of linear reservoirs) are reproduced to better than 1e-8.

`make check` now runs three sets of tests (chapter 9): 23 C unit tests, 68 tests of the Python package, and all the
examples against their reference results. The C unit tests check, among other things, the coefficient tables of the
three numerical methods against the textbook conditions (a check that would have caught B-13) and the setup and equations
of every built-in model; with the Python tests (52 models run a short simulation; rain in four file formats) they
found B-22 to B-25. Together they run two thirds of the lines of the C code (chapter 9).

## 7.8 Tools added along the way

* `tests/regression/run_examples.py`: runs every example and compares every output with the references and,
  optionally, with the original code (chapter 9).
* `examples/test_2015.gbl`, `examples/clearcreek_2015.gbl`: the configurations that produced the 2015 reference
  results, recovered from the repository history and translated to today's format.
* `tools/python/asynch_io.py`, `tools/python/plot_hydrographs.py`: read and plot the outputs (chapter 2).
* `tools/python/make_comparison_plots.py`: regenerates the figures of this chapter.
* `Dockerfile`: a tested, ready-made environment (chapter 1).
