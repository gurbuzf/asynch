# asynch (Python package)

Python interface to [ASYNCH](../README.md), the asynchronous solver of hydrological models on river networks.
The numerical work is done by the C library `libasynch.so`; Python drives it.

```python
from asynch import Simulation
with Simulation("test_2015.gbl") as sim:     # run in examples/
    sim.run()                                # same output files as `asynch test_2015.gbl`
    q = sim.states[:, 0]                     # discharge of every link
```

* `Simulation`: run a global file, advance in steps, get/set states and parameters, custom outputs, MPI.
* `Model`: define a new model with C code (compiled, as fast as the built-in models) or Python functions.
* `GlobalConfig`: read, change and write global files (`.gbl`).
* `asynch.io`: read output files, write input files.

Installation, tutorial and reference: [docs/guide/10_python.md](../docs/guide/10_python.md) and
<https://gurbuzf.github.io/asynch/>.

**Ready-made (Linux x86-64, glibc 2.31 or newer).** The wheel attached to each release of
<https://github.com/gurbuzf/asynch/releases> carries the library and the `asynch` program, compiled; pip installs MPI
with it (the `mpich` package, with `mpiexec`). Nothing to build:

```sh
pip install --upgrade pip && pip install asynch-<version>-py3-none-manylinux_2_31_x86_64.whl
asynch test.gbl               # the program; mpiexec -n 4 asynch test.gbl
```

**From the sources**, after building and installing ASYNCH (`make install` puts `libasynch.so` in `/usr/local/lib`):

```sh
pip install ./python          # or: export PYTHONPATH=$PWD/python
python3 -m asynch library     # shows which libasynch.so is used (override with ASYNCH_LIBRARY)
```

Needs Python >= 3.8 and NumPy; h5py to read `.h5` files; a C compiler for models written in C; mpi4py only
to pass another communicator.
