# 6. Reproducibility and regression testing

> **Rule for every change to the C code:** run the regression harness before and
> after the change. If a result moves by more than the tolerance, the change is
> *scientific*. It must be explained in the `CHANGELOG.md` and, if intended, the
> benchmark is regenerated in the same commit, with the reason written down.

## 6.1 The harness

`tests/regression/run_examples.py` runs every example shipped in `examples/` and
compares the produced files with the reference ("benchmark") files stored in the
repository.

```bash
# after building (see 01_build_and_run.md)
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
| `clearcreek` | 254 (top layer) | `clearcreek.pea` | `examples/results/clearcreek.pea`, **known mismatch** (R-02) |
| `model_192` | 192 | hydrograph `.csv`, peaks `.pea`, snapshot `.h5` | `examples/more/model_192/results_benchmark/` |
| `model_196` | 196 | idem | idem |
| `model_258` | 258 | idem | idem |
| `model_259` | 259 | idem | idem, **known mismatch** (R-03) |

A *known mismatch* (`XFAIL`) is reported but does not make the run fail. A **crash is
always a failure**, even for those cases.

## 6.2 Why compare with a tolerance?

ASYNCH is an adaptive solver: every link chooses its own time step from an error
estimate. Anything that changes the last bits of a floating-point number (another
compiler, `-O2` vs `-O3`, another CPU, another number of MPI processes) changes some
step sizes, and therefore the results, around the 6th significant digit.

The solver itself only guarantees accuracy up to its tolerances, which are given in
the `.gbl` file (typically `1e-3`…`1e-6` absolute and `1e-6` relative for discharge). So
differences below those tolerances carry no information. The harness accepts

    |new − ref| ≤ atol + rtol·|ref|        with  atol = 1e-5,  rtol = 1e-4

and **always prints the largest absolute and relative difference**. A real regression (a
changed equation, a wrong unit, a parameter off by one index) produces differences of
percent or more, orders of magnitude above this threshold.

Files are compared by **link id** (`.pea`, `.h5`) or by row (`.csv`), so a different
order of links in the file (which happens with MPI) does not matter.

## 6.3 Baseline measured in Phase 1 (commit `84da43a` + example path fix)

Release build (`-O3 -DNDEBUG`), Ubuntu 24.04, GCC 13, OpenMPI 4.1, HDF5 1.10:

| Case | np=1 | np=2 | np=4 |
|---|---|---|---|
| test (190) | PASS | PASS | PASS |
| clearcreek (254) | **FAIL: crash (B-01)** | XFAIL (R-02) | XFAIL (R-02) |
| model_192 | PASS | PASS | PASS |
| model_196 | PASS (bit-identical) | PASS | PASS |
| model_258 | PASS (bit-identical) | PASS | PASS |
| model_259 | XFAIL (R-03) | XFAIL (R-03) | XFAIL (R-03) |

With a debug build (no `-DNDEBUG`), every case additionally fails with exit code 134
because of the double `fclose` at shutdown (B-03). The outputs are still correct.

## 6.4 Tools used for the audit (and useful later)

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
