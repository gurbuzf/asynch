"""
Readers of ASYNCH output files. They now live in the Python package (python/asynch/io.py); this file
keeps the old import working for the scripts of this folder:

    import sys; sys.path.insert(0, "tools/python")
    import asynch_io
    hydro = asynch_io.read_dat("examples/out_2015/test.dat")

Only NumPy is needed (and h5py for .h5 files); the C library is not loaded.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "python"))

from asynch.io import *  # noqa: E402,F401,F403
from asynch.io import (read_dat, read_csv, read_pea, read_rec, read_h5_snapshot,  # noqa: E402,F401
                       read_h5_hydrographs, read_hydrographs, read_snapshot)
