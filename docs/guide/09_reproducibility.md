# 9. Reproducibility and regression testing

> **Rule for every change to the C code:** run `make check` and the regression harness (with `--compare-to` the
> previous build) before and after the change. If a result moves by more than the tolerance, the change is
> *scientific* and must be explained in the `CHANGELOG.md`.
>
> **The benchmark is the set of example results shipped with the original ASYNCH repository**
> (`examples/results/` and `examples/more/*/results_benchmark/`). These files are never
> modified or regenerated. Every result is measured against them.

## 9.0 All the tests: `make check`

Run in the build folder, `make check` runs three sets of tests, in about a minute:

| Test | File | What it checks |
|---|---|---|
| `check_asynch` | `tests/check_asynch.c` | 22 C unit tests: the Runge-Kutta tables satisfy the order conditions (sum of b = 1, rows of A add up to c, ...) and reach their order on y' = y; their dense output is consistent; every built-in model has consistent sizes and all the functions the solver calls; sorting and the id lookup; argument checks of `asynch_api.h` |
| `run_python_tests.sh` | `tests/python/` | 62 tests of the Python package: runs identical to the `asynch` program, byte for byte; models written in Python identical to the built-in ones; exact solutions of reservoir chains; 70 000 links; 2 MPI processes; the example scripts |
| `run_regression.sh` | `tests/regression/run_examples.py` | every example against the reference results (9.1) |

The outcome is at the end (`# PASS: 3`, `# FAIL: 0`); the details are in `tests/*.log` of the build folder. If Python
or NumPy is missing, the last two are reported as `SKIP`. The unit tests found three bugs (B-22 to B-24, chapter 8)
when they were first written.

## 9.1 The harness

`tests/regression/run_examples.py` runs every example shipped in `examples/` and
compares the produced files with those original reference ("benchmark") files.

```bash
# after building (see 01_setup.md)
python3 tests/regression/run_examples.py                  # 1 MPI process
python3 tests/regression/run_examples.py --np 4           # 4 MPI processes
python3 tests/regression/run_examples.py --only model_258 # a single case
python3 tests/regression/run_examples.py --asynch /path/to/other/asynch --keep
```

* The examples are copied to a temporary directory, so the repository is never modified.
  `--keep` keeps that directory so you can look at the outputs.
* Only the Python standard library is required. If `h5py` is installed
  (`pip install h5py`), the HDF5 snapshot files are compared too.
* The exit status is `0` when everything passes, so the harness can run in CI.

### Cases

| Case | Model | Compared files | Reference |
|---|---|---|---|
| `test` | 190 (constant runoff) | `test.pea` | `examples/results/test.pea` |
| `test with .rkd file` | 190, tolerances from `examples/test.rkd` | `test_rkd.pea` | `examples/results/test.pea` (same settings, same result) |
| `test, 2015 configuration` | 190 | hydrographs `.dat`, peaks `.pea`, final states `.rec` | `examples/results/test.dat`, `.pea`, `.rec` |
| `clearcreek` | 254 (top layer) | `clearcreek.pea` | `examples/results/clearcreek.pea`, **known mismatch**: the reference comes from the 2015 configuration (next line) |
| `clearcreek, 2015 configuration` | 254 | `.dat`, `.pea`, `.rec` | `examples/results/clearcreek.dat`, `.pea`, `.rec`, **known mismatch** (R-02: model 254 changed in 2021) |
| `model_192` | 192 | hydrograph `.csv`, peaks `.pea`, snapshot `.h5` | `examples/more/model_192/results_benchmark/` |
| `model_196` | 196 | idem | idem |
| `model_258` | 258 | idem | idem |
| `model_259` | 259 | idem | idem, **known mismatch** (R-03) |

A *known mismatch* (`XFAIL`) is reported but does not make the run fail. A **crash is
always a failure**, even for those cases.

### The 2015 configurations

The reference files in `examples/results/` (`.dat`, `.pea`, `.rec`) were all produced in May 2015
(commit `b73fc2d`) with global files that are no longer in the repository: `Global190.gbl` (300
minutes) and `Global254.gbl` (6000 minutes), both starting on 2014-05-01. The input files
(topology, parameters, rain, evaporation) are byte-for-byte the same today.
`examples/test_2015.gbl` and `examples/clearcreek_2015.gbl` are those two configurations written in
today's format; they write into `examples/out_2015/`. Run them like any example:

```bash
cd examples
mpirun -n 2 ../build/src/asynch test_2015.gbl        # compare out_2015/test.* with results/test.*
```

Results: the `test` references are reproduced (hydrographs within 5e-7). The `clearcreek` references
are reproduced within the solver tolerance only when one line of model 254 is restored to its
2015 form; see issue R-02 in [08_known_issues.md](08_known_issues.md).

### Comparing with the original code (`--compare-to`)

Stored references can be old or incomplete, so the most direct test of a change is:
*does the changed code give the same answer as the code before the change, on the same inputs?*

```bash
# 1. Build the unmodified original code once (default: commit 84da43a, into ~/asynch-original)
tests/regression/build_original.sh
# 2. Build your version with the SAME flags (see 01_setup.md), then:
python3 tests/regression/run_examples.py --compare-to ~/asynch-original/build/src/asynch
python3 tests/regression/run_examples.py --compare-to ~/asynch-original/build/src/asynch --np 4
```

Both executables run every example on identical copies of the inputs, and **every output
file** is compared: peak flows, hydrographs (`.csv`, `.dat`, `.h5`) and every snapshot
(`.h5`, `.rec`). A case line looks like

```
  vs original: 27 of 27 output files identical
```

"Identical" means bit for bit. A file that differs but stays within the tolerance is
counted as "within tolerance" (use `--verbose` to list it). A file outside the tolerance,
or a file the original wrote but the new code did not, makes the case **FAIL**, even for
`XFAIL` cases. If the original itself crashes, its missing files are not compared.

**What to expect:**

| processes | same code, two runs | what a change must achieve |
|---|---|---|
| `--np 1` | bit-identical | **bit-identical**, unless the change is meant to alter results |
| `--np 2`, `--np 4` | differ: ~1e-6 relative on 1-day runs; up to ~1e-4 absolute on the 6000-minute clearcreek run (measured: three 4-process runs of the original code differed by 8.4e-5, 9.7e-5 and 1.15e-4) | within tolerance |

So a pure bug fix or refactoring must give "N of N output files identical" with one process.
That is the strict test. Runs with several processes check that nothing breaks in parallel.

## 9.2 Why compare with a tolerance?

ASYNCH is an adaptive solver: every link chooses its own time step from an error
estimate. Anything that changes the last bits of a floating-point number (another
compiler, `-O2` vs `-O3`, another CPU, another number of MPI processes) changes some
step sizes, and therefore the results, around the 6th significant digit.

The solver itself only guarantees accuracy up to its tolerances, which are given in
the `.gbl` file (typically `1e-3`…`1e-6` absolute and `1e-6` relative for discharge). So
differences below those tolerances carry no information. The harness accepts

    |new − ref| ≤ atol + rtol·|ref|        with  rtol = 1e-4  and
                                          atol = 1e-5 with 1 process, 1e-3 with several

and **always prints the largest absolute and relative difference**. A real regression (a
changed equation, a wrong unit, a parameter off by one index) produces differences of
percent or more, orders of magnitude above this threshold. The larger `atol` with several
processes covers the run-to-run variation measured above (up to ~1e-4). Both can be set with
`--atol` and `--rtol`.

**Time of the peak.** In `.pea` files, the time of each peak is compared with its own tolerance,
20 minutes by default (`--peak-time-atol`). On a flat-topped hydrograph the minute of the maximum is
ill-conditioned: two runs of the same code with 2 processes put some clearcreek peaks 15 minutes
apart while their values agree to 1e-7 m³/s. The peak *value* is always checked with the normal tolerance.

Files are compared by **link id** (`.pea`, `.h5`) or by row (`.csv`, `.dat`, `.rec`), so a different
order of links in the file (which happens with MPI) does not matter for `.pea` and `.h5`.

## 9.3 Reference baseline (commit `84da43a` + example path fix)

Release build (`-O3 -DNDEBUG`), Ubuntu 24.04, GCC 13, OpenMPI 4.1, HDF5 1.10:

| Case | np=1 | np=2 | np=4 |
|---|---|---|---|
| test (190) | PASS | PASS | PASS |
| clearcreek (254) | **FAIL: crash (B-01)** | XFAIL (R-02) | XFAIL (R-02) |
| model_192 | PASS | PASS | PASS |
| model_196 | PASS (bit-identical) | PASS | PASS |
| model_258 | PASS (bit-identical) | PASS | PASS |
| model_259 | XFAIL (R-03) | XFAIL (R-03) | XFAIL (R-03) |

At that commit, a debug build (no `-DNDEBUG`) additionally failed every case with exit
code 134, because of the double `fclose` at shutdown (B-03, since fixed).

## 9.4 Useful tools

**AddressSanitizer / UndefinedBehaviorSanitizer** detect invalid memory accesses and
undefined behaviour *while the program runs*, with the exact source line. Build a
separate copy (it runs about 2–3× slower):

```bash
mkdir -p ~/build-asan && cd ~/build-asan
/path/to/asynch/configure CFLAGS="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer" \
                          LDFLAGS="-fsanitize=address,undefined"
make -j
ASAN_OPTIONS=detect_leaks=0 python3 /path/to/asynch/tests/regression/run_examples.py --asynch ~/build-asan/src/asynch
```

**Compiler warnings** reveal many bugs for free:

```bash
../configure CFLAGS="-O2 -g -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare"
make 2>&1 | grep warning
```

**Bisecting across history** (how R-03 was established): build an old commit in a
separate directory with `git worktree` and run the same example.

```bash
git worktree add /tmp/asynch-2018 cba763b
cd /tmp/asynch-2018 && autoreconf --install && mkdir b && cd b && ../configure CFLAGS="-O2 -DNDEBUG" && make -j
```
