# ASYNCH

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

> **New here? Start with the [ASYNCH guide](docs/guide/README.md).** It explains in plain words what the model
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
cd build
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

## ASYNCH from Python

```bash
export PYTHONPATH=~/asynch/python        # or: pip install ./python in a virtual environment
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

A new model, written in C and compiled on the fly (or as plain Python functions, without a compiler):

```python
from asynch import Model, Simulation

model = Model(states=["q"], global_params=["k"], params=["A_h"], forcings=["rain"],
              param_factors={"A_h": 1e6})        # km2 -> m2 when reading the parameter file
model.equations = """
    double inflow = upstream_q + rain * A_h * (0.001 / 3600.0);    /* mm/h on m2 -> m3/s */
    d_q = (inflow - q) / k;                                        /* per minute */
"""
with Simulation("my_network.gbl", model=model) as sim:
    sim.run()
```

More in [chapter 10](docs/guide/10_python.md) and in [`examples/python/`](examples/python): a sensitivity loop, a
custom model with its own outputs (it reproduces the built-in model 191 exactly), and a network, its input files and
its model built entirely from Python.

## Tests

`make check` (in the build folder) runs:

* 22 C unit tests (`tests/check_asynch.c`): the coefficient tables of the numerical methods, the setup of every
  built-in model, sorting and lookups, argument checks;
* 62 tests of the Python package (`tests/python`): runs identical to the `asynch` program byte for byte, models written
  in Python identical to the built-in ones, exact solutions, 70 000-link networks, MPI;
* every example, compared with the reference results shipped with ASYNCH (`tests/regression/run_examples.py`).

How results are compared, and how to compare a change with the original code: [chapter 9](docs/guide/09_reproducibility.md).

## Documentation

| | |
|---|---|
| [docs/guide/](docs/guide/README.md) | the guide: concepts, installation, running, equations, solver, C primer, Python, fixes, reproducibility |
| [docs/*.rst](docs/) | the reference manual: every file format, every built-in model, the C API ([online](http://asynch.readthedocs.io/), older version) |
| [CHANGELOG.md](CHANGELOG.md) | every change, and whether it changes numerical results |

To build the reference manual locally (Doxygen and Sphinx):

```bash
pip install --user sphinx sphinx-autobuild sphinx_rtd_theme breathe recommonmark
sudo apt-get install doxygen
cd docs && doxygen api.dox && doxygen devel.dox && make html     # result in docs/.build/html
```

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
