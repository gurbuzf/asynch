# asynch-hlm: the Python package of ASYNCH (`import asynch`)

Python interface to [ASYNCH](https://github.com/gurbuzf/asynch), the asynchronous solver of hydrological models on river networks.
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

Installation, tutorial and reference: <https://gurbuzf.github.io/asynch/guide/10_python.html>.

**Ready-made (Linux x86-64, glibc 2.31 or newer)**, from [PyPI](https://pypi.org/project/asynch-hlm/). The package
carries the library and the `asynch` program, compiled; pip installs MPI with it (the `mpich` package, with
`mpiexec`). Nothing to build:

```sh
pip install --upgrade pip && pip install asynch-hlm      # the latest version
asynch test.gbl               # the program; mpiexec -n 4 asynch test.gbl
```

`pip install --upgrade asynch-hlm` updates it; `pip install asynch-hlm==<version>` installs a given version. The same
wheels are attached to each release of <https://github.com/gurbuzf/asynch/releases>.

**From the sources**, after building and installing ASYNCH (`make install` puts `libasynch.so` in `/usr/local/lib`):

```sh
pip install ./python          # or: export PYTHONPATH=$PWD/python
python3 -m asynch library     # shows which libasynch.so is used (override with ASYNCH_LIBRARY)
```

Needs Python >= 3.8 and NumPy; h5py to read `.h5` files; a C compiler for models written in C; mpi4py only
to pass another communicator.
