"""
asynch: Python interface to ASYNCH, the asynchronous solver of hydrological models on river networks.

    from asynch import Simulation
    with Simulation("examples/test_2015.gbl") as sim:   # run from the examples folder
        sim.run()

Main pieces (see docs/guide/10_python.md):

* :class:`Simulation` (asynch.solver): run a global file, advance in steps, read and change states and
  parameters, custom outputs.
* :class:`Model` (asynch.model): define a new model in C code or in Python and let ASYNCH integrate it.
* :class:`GlobalConfig` (asynch.config): read, change and write global files (.gbl).
* :mod:`asynch.io`: read the output files and write the input files.

The C library libasynch is loaded the first time a Simulation or Model is used (not at import); set
ASYNCH_LIBRARY if it is not found.
"""
from .config import GlobalConfig, Forcing, Output, PeakOutput, Snapshot, Selection, FileRef
from .model import Model, ModelError
from .solver import Simulation, AsynchError
from . import io
from ._lib import find_library

__version__ = "1.4.3"          # same as the C library (configure.ac)

__all__ = ["Simulation", "AsynchError", "Model", "ModelError", "GlobalConfig", "Forcing", "Output", "PeakOutput",
           "Snapshot", "Selection", "FileRef", "io", "find_library", "library_path"]


def library_path():
    """Path of the libasynch shared library the package uses."""
    return find_library()
