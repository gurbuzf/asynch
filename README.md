# ASYNCH

**Version 1.5.0** · [release notes](https://gurbuzf.github.io/asynch/release_notes.html) ·
[download](https://github.com/gurbuzf/asynch/releases) · [documentation](https://gurbuzf.github.io/asynch/)

ASYNCH solves large systems of ordinary differential equations that have the shape of a tree, such as a
river network cut into thousands of links (hillslope-link models). Each link is integrated with its own
adaptive time step (an *asynchronous* Runge-Kutta method), and the network can be split between many
processors with MPI. It comes with more than 50 built-in hydrological models, such as model 190 and the
Top Layer model 254 used at the Iowa Flood Center.

What you can do with it:

* **Run simulations** from the command line: `asynch my_basin.gbl`, on one or many processors.
* **Use it from Python**: run, stop, inspect and change simulations, build input files and global files in a
  script, and **define new models in Python** while the computation runs at C speed
  ([Python guide](docs/guide/10_python.md)).
* **Use it from C** as a library (`libasynch.so`, `asynch_interface.h`, `asynch_api.h`).

> **New here? Start with the [documentation website](https://gurbuzf.github.io/asynch/)** (or the same
> [guide on GitHub](docs/guide/README.md)). It explains in plain words what the model
> computes ([chapter 0](docs/guide/00_what_is_asynch.md)), how to install it and run a first simulation
> ([chapter 1](docs/guide/01_setup.md)), how to run and change simulations ([chapter 2](docs/guide/02_running_the_model.md)),
> then the equations, the solver, the C code, and the Python package ([chapter 10](docs/guide/10_python.md)).
> [Chapter 7](docs/guide/07_improvements_explained.md) lists the problems that were found and fixed, and how serious
> each was. Every change is recorded in [CHANGELOG.md](CHANGELOG.md).

## Quick start with Docker (any system)

```bash
git clone https://github.com/gurbuzf/asynch.git && cd asynch && git checkout modernization
docker build -t asynch .                 # installs everything, compiles, runs all the tests (about 10 minutes)
docker run --rm -it asynch               # a shell inside the container, in the examples folder
mpirun -n 2 asynch clearcreek.gbl        # a 6 359-link basin, on 2 processors
python3 python/run_example.py            # the same kind of run from Python
```

Details, and how to share a folder with the container: [chapter 1, option B](docs/guide/01_setup.md#option-b-docker-windows-macos-linux).

## Install on Ubuntu 24.04 (or Windows with WSL2)

```bash
sudo apt-get update
sudo apt-get install -y git ca-certificates gcc gfortran make autoconf automake libtool pkg-config \
    openmpi-bin libopenmpi-dev libhdf5-dev hdf5-tools libpq-dev zlib1g-dev check \
    python3 python3-numpy python3-h5py python3-matplotlib

git clone https://github.com/gurbuzf/asynch.git && cd asynch && git checkout modernization
autoreconf --install
mkdir -p build && cd build
../configure CFLAGS="-O3 -DNDEBUG -Wno-format-security"
make -j4
make check                               # C unit tests, Python tests, examples vs reference results
sudo make install && sudo ldconfig       # asynch -> /usr/local/bin, libasynch.so -> /usr/local/lib
```

`make check` ends with `# PASS: 3` and `# FAIL: 0`. What each package is for, and what to do when a step fails:
[chapter 1, option A](docs/guide/01_setup.md#option-a-native-install-on-ubuntu-2404). A different installation
folder: `../configure --prefix=/my/folder ...`.

Run the examples (paths inside a global file are relative to the folder you run from):

```bash
cd ../examples
mpirun -n 2 asynch test.gbl              # 11 links, model 190
mpirun -n 4 asynch clearcreek.gbl        # Clear Creek, Iowa: 6 359 links, model 254
```

## ASYNCH as a Python library

`asynch` is a regular Python package (`import asynch`): a thin layer over the C library `libasynch.so`, which does
all the computation, the way h5py sits on top of HDF5. Install it into a virtual environment after `make install`:

```bash
sudo apt-get install -y python3-venv python3-setuptools python3-wheel
python3 -m venv --system-site-packages ~/asynch-venv && source ~/asynch-venv/bin/activate
cd build && make install-python PYTHON_FOR_ASYNCH=~/asynch-venv/bin/python    # = pip install ../python
pip install numba mpi4py                   # optional: models in Python at C speed; MPI from your own code
python3 -m asynch library                  # which libasynch.so the package uses
```

```python
from asynch import Simulation

with Simulation("test_2015.gbl") as sim:         # in examples/
    sim.advance(60)                              # the first hour
    g = sim.global_params
    g[3] = 0.5                                   # model 190: runoff coefficient RC
    sim.global_params = g                        # derived link parameters are recomputed
    sim.run()                                    # the rest; writes the output files of the global file
    peak_time, peak_q = sim.peaks                # for every link, in the order of sim.link_ids
```

**A new model** in plain Python, compiled by Numba so that it runs at the speed of C (or write the equations as C
code; or leave out `jit` to run without any compiler):

```python
from asynch import Model, Simulation

def equations(t, y, upstream, gp, p, forcing):   # dq/dt of one link; upstream: states of the parent links
    inflow = upstream[:, 0].sum() + forcing[0] * p[0] * (0.001 / 3600.0)     # mm/h on m2 -> m3/s
    return (inflow - y[0]) / gp[0],

model = Model(states=["q"], global_params=["k"], params=["A_h"], forcings=["rain"],
              param_factors={"A_h": 1e6}, jit="numba")
model.equations = equations
with Simulation("my_network.gbl", model=model) as sim:
    sim.run()
```

Measured on 5 000 links (model 190 rewritten each way, identical results): built-in C 0.10 s, C code 0.10 s,
Python + Numba 0.13 s, plain Python 4.1 s.

**MPI**: `mpirun -n 4 python3 my_script.py`; every process runs the script and ASYNCH shares the links (Clear Creek,
6 359 links: 8.0 s on 1 process, 2.75 s on 4). mpi4py is optional (`Simulation(..., comm=MPI.COMM_WORLD)`).

More in the [Python chapter](docs/guide/10_python.md), the
[Python API reference](https://gurbuzf.github.io/asynch/python_api.html) and [`examples/python/`](examples/python).

## Tests

`make check` (in the build folder) runs:

* 23 C unit tests (`tests/check_asynch.c`): the coefficient tables of the numerical methods, the setup and equations of
  every built-in model, sorting and lookups, argument checks;
* 70 tests of the Python package (`tests/python`): runs identical to the `asynch` program byte for byte, models written
  in Python identical to the built-in ones, exact solutions, 52 built-in models integrating a short simulation, rain in
  four file formats, 70 000-link networks, MPI;
* every example, compared with the reference results shipped with ASYNCH (`tests/regression/run_examples.py`).

Together they run 66.5 % of the lines of the C code (`tests/coverage_report.py`). How results are compared, and how to
compare a change with the original code: [chapter 9](docs/guide/09_reproducibility.md).

## Documentation

| | |
|---|---|
| **[Documentation website](https://gurbuzf.github.io/asynch/)** | everything below in one searchable site (built from `docs/` by GitHub Actions) |
| [docs/guide/](docs/guide/README.md) | the guide: concepts, installation, running, equations, solver, C primer, Python, fixes, reproducibility |
| [docs/*.rst](docs/) | the reference manual: every file format, every built-in model, the C API |
| [CHANGELOG.md](CHANGELOG.md) | every change, and whether it changes numerical results |
| [Releases](https://github.com/gurbuzf/asynch/releases) | each version with a source archive that builds without autotools (`./configure && make`) |

To build the website locally: `pip install -r docs/requirements.txt` (and `sudo apt-get install doxygen` for the C API
pages), then `sphinx-build -b html docs docs/_build/html` and open `docs/_build/html/index.html`.

## Repository layout

```
src/              the C library and the asynch program (models in src/models/, solvers in src/solvers/)
python/asynch/    the Python package
examples/         example basins, global files and reference results; examples/python/ for Python
tests/            C unit tests, Python tests, regression harness, synthetic network generator
tools/python/     plotting and comparison scripts
docs/             reference manual (.rst) and guide (docs/guide/)
```

A map of the code, file by file: [chapter 3](docs/guide/03_code_map.md).

## Other systems (not tested)

**Fedora**: install `autoconf automake libtool gcc gcc-gfortran make openmpi-devel hdf5-devel libpq-devel zlib-devel
check-devel python3-numpy`, then make the MPI programs visible with `sudo ln -s /usr/lib64/openmpi/bin/* /usr/bin/`,
and build as above. **Red Hat / CentOS**: as Fedora, after enabling the `epel-release` and `PowerTools` repositories
(`sudo dnf install epel-release && sudo dnf config-manager --set-enabled PowerTools`). OpenBLAS is optional.
**macOS**: use Docker. See also [chapter 1, option C](docs/guide/01_setup.md#option-c-other-systems-not-tested).

## License

See [LICENSE](LICENSE).
