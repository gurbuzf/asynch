# 1. Build ASYNCH and run your first simulation

Everything on this page was tested on **Ubuntu 24.04** (GCC 13.3, OpenMPI 4.1.6,
HDF5 1.10.10) in September 2026. Commands you type start with `$`; everything else is
what you should see.

## 1.1 What you need, and why

| Package (Ubuntu) | Why ASYNCH needs it |
|---|---|
| `gcc`, `make` | the C compiler and the build driver |
| `autoconf`, `automake`, `libtool`, `pkg-config` | generate the `configure` script and the `Makefile`s ("autotools") |
| `openmpi-bin`, `libopenmpi-dev` | MPI: runs one model on several CPU cores/machines (`mpirun`, `mpicc`) |
| `libhdf5-dev`, `hdf5-tools` | HDF5: binary output files (`.h5`) and the `h5dump` viewer |
| `libpq-dev` | PostgreSQL client, for reading and writing a database (optional at run time, required to build) |
| `zlib1g-dev` | compressed (`.gz`) forcing files |
| `check` | the C unit-test framework used by `make check` |

```bash
$ sudo apt-get update
$ sudo apt-get install -y gcc make autoconf automake libtool pkg-config \
      openmpi-bin libopenmpi-dev libhdf5-dev hdf5-tools libpq-dev zlib1g-dev check
```

For the regression tests and for reading results in Python (optional):

```bash
$ python3 -m pip install h5py numpy
```

## 1.2 Build

ASYNCH uses **autotools**. The flow is always the same three steps:

1. `autoreconf --install` reads `configure.ac` and `Makefile.am` (written by the developers)
   and *generates* the `configure` script and `Makefile.in` templates. Run it once after
   cloning, or again after editing `configure.ac`/`Makefile.am`.
2. `configure` inspects your machine (where is MPI? where is HDF5?) and writes real
   `Makefile`s plus `config.h`. You run it from a separate *build directory*, so that
   compiled files never mix with the sources.
3. `make` compiles.

```bash
$ cd asynch                     # the repository
$ autoreconf --install
$ cd build                      # the (empty) build directory that ships with the repo
$ ../configure CFLAGS="-O3 -DNDEBUG -Wno-format-security"
$ make -j4
```

The result is `build/src/asynch` (the program) and `build/src/libasynch.a` (the library).
`make install` would copy them to `/usr/local` (or to `--prefix=...`); **you do not need
to install** to run the examples.

### Which `CFLAGS`?

| Flags | Use it for |
|---|---|
| `-O3 -DNDEBUG` | production runs (what the README recommends). `-DNDEBUG` turns `assert()` checks off. |
| `-O0 -g` | debugging with `gdb`: no optimisation, full debug info, `assert()`s active. |
| `-O1 -g -fsanitize=address,undefined` | hunting memory bugs, see [06_reproducibility.md](06_reproducibility.md) |

Compiler **warnings** (`warning: ignoring return value of 'fscanf'`, …) are expected at
the moment. They are catalogued in [05_known_issues.md](05_known_issues.md). **Errors**
stop the build and are not expected.

### Check the build

```bash
$ make check        # runs the (single) C unit test
$ python3 ../tests/regression/run_examples.py --np 2
```
The second command runs all examples and compares them with the reference results. The expected
output today is described in [06_reproducibility.md §6.3](06_reproducibility.md#63-reference-baseline-commit-84da43a--example-path-fix).

## 1.3 Run an example

```bash
$ cd ../examples
$ mpirun -n 2 ../build/src/asynch test.gbl
```

* `mpirun -n 2` starts **2 copies** of the program (2 MPI *processes*). ASYNCH splits the
  river network between them. `-n 1` is fine for small networks.
* In a Docker container you run as root: add `--allow-run-as-root`, or set
  `OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1`.
* If you ask for more processes than you have cores, add `--oversubscribe`.

Expected output (times vary):

```
Beginning initialization...
*****************************
Reading global file...
Loading network...
...
Model type is 190.
Process 1 (2 total) is good to go with 4 links.
Process 0 (2 total) is good to go with 7 links.
Finished initialization. Total time for initialization: 1.0...

Computing solution at each link...
************************************

Computations complete. Total time for calculations: 0.01...

Results written to file outputs.h5.
Peakflows written to file test.pea.
```

The larger example, the Clear Creek basin (6 359 links, model 254), runs the same way:

```bash
$ mpirun -n 4 ../build/src/asynch clearcreek.gbl
```

> Versions of ASYNCH before the 2026-09-25 fixes crash on this example with one process
> (`Fatal glibc error: malloc.c ...`, issue B-01). If you see that message, you are running an old build.

## 1.4 What goes in: the input files

Everything is driven by **one text file, the global file (`.gbl`)**. It has a rigid
order: each non-comment line answers the next question. Lines starting with `%` are
comments. The full reference is in `docs/input_output.rst` (section *Global File Structure*).
Here is `examples/test.gbl` with the meaning of each block:

| Block in `test.gbl` | Meaning |
|---|---|
| `190` | **model id**: which system of ODEs to solve (see `docs/builtin_models.rst`) |
| `2017-01-01 00:00` / `2017-01-02 00:00` | simulation start and end (UTC). ASYNCH's internal time is **minutes since start** |
| `3` `Time` `LinkID` `State0` | the 3 quantities written in the hydrograph output (`State0` = discharge q [m³/s]) |
| `Classic` | format of the peak-flow file |
| `6 0.33 0.20 -0.1 0.33 0.1 2.2917e-5` | 6 **global parameters** (same for all links), meaning depends on the model |
| `30 10 30` | internal buffer sizes (steps kept per link, steps sent per MPI message, discontinuities); keep these values |
| `0 test.rvr` | **topology**: which link flows into which |
| `0 test.prm` | **link parameters** (areas, lengths) |
| `1 test.uini` | **initial state** (`.uini` = same value for every link) |
| `2` then `1 test.str` and `7 evap.mon ...` | **forcings**: 2 of them, rain from a `.str` file and monthly evaporation (`7` = recurring) |
| `5 5.0 outputs.h5` | hydrographs: format 5 (HDF5 packet), every 5 minutes, to `outputs.h5` |
| `1 test.pea` | peak flows to `test.pea` |
| `1 test.sav` / `3` | links to save: hydrographs for the ids listed in `test.sav`, peaks for all links |
| `4 60 test.h5` | snapshots: format 4 (recurring HDF5) every 60 minutes → `test_<unixtime>.h5` |
| `2` | numerical method: **index 2 = Dormand–Prince 5(4)** (recommended). 0 = RK 3(2) and 1 = RK 4(3) also exist; any other value stops the run with an error |
| 4 lines of numbers | error tolerances per state: absolute, relative, absolute (dense output), relative (dense output) |

The small network files are easy to read by eye:

```
test.rvr (topology)          test.prm (parameters)         test.str (rain)
11          <- # links       11                            11          <- # links
                                                           
1           <- link id       1                             1           <- link id
3 2 8 3     <- 3 parents:    0.42674164 0.26215310 0.04694315   3      <- 3 changes
               ids 2, 8, 3   ^ upstream   ^ channel ^ hillslope   0    40   <- t=0 min: 40 mm/h
9                               area km²    length km  area km²   100  20   <- t=100: 20 mm/h
0           <- no parents                                          200   0   <- t=200: stop
```

## 1.5 What comes out

| File | Content | How to read it |
|---|---|---|
| `test.pea` | one line per link: `link_id  upstream_area[km²]  time_of_peak[min]  peak_discharge[m³/s]` (after 2 header lines: #links, model id) | any text editor / `numpy.loadtxt(skiprows=2)` |
| `outputs.h5` (format 5) | table `outputs` with columns `Time` [min], `LinkID`, `State0` (**stored as float32**) | `h5py` (below) |
| `clearcreek.h5` (format 6) | arrays `link_id[n]`, `time[t]`, `outputs[n, t, k]` | `h5py` |
| `*.csv` (format 2) | one column group per link, one row per output time | spreadsheet / `pandas` |
| `test_<unixtime>.h5` | **snapshot**: full state of every link at one time, `float64`. Usable as initial condition of a later run | `h5py`, `h5dump` |

Reading the outputs in Python:

```python
import h5py, numpy as np

# Hydrographs, packet format (5)
with h5py.File("outputs.h5") as f:
    t = f["outputs"]["Time"]; ids = f["outputs"]["LinkID"]; q = f["outputs"]["State0"]
outlet = ids == 80
print("peak at outlet:", q[outlet].max(), "m3/s")

# Hydrographs, array format (6)
with h5py.File("clearcreek.h5") as f:
    link_ids = f["link_id"][:]      # (n_links,)
    times = f["time"][:]            # (n_times,) unix time
    out = f["outputs"][:]           # (n_links, n_times, n_outputs)

# Peak flows
pea = np.loadtxt("test.pea", skiprows=2)   # columns: id, area, t_peak, q_peak
```

Next: [02_code_map.md](02_code_map.md) shows where all of this happens in the source code.
