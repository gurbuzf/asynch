"""The `asynch` command of the self-contained wheel: runs the ASYNCH program carried in asynch/bin.

    asynch my_basin.gbl
    mpiexec -n 4 asynch my_basin.gbl          # mpiexec comes with the `mpich` package, installed with the wheel
"""
import os
import stat
import sys

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")


def asynch():
    """The asynch program, with the MPI library of the `mpich` package."""
    exe = os.path.join(BIN, "asynch")
    if not os.path.exists(exe):
        sys.exit("the asynch program is not part of this installation of the asynch package: only the self-contained "
                 "wheel carries it. Build ASYNCH from the sources (docs/guide/01_setup.md) to get it.")
    if not os.access(exe, os.X_OK):                  # some installers drop the executable bit
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    from ._lib import mpich_libdir
    env = dict(os.environ)
    mpi_dir = mpich_libdir()
    if mpi_dir:
        env["LD_LIBRARY_PATH"] = mpi_dir + (os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    os.execve(exe, [exe] + sys.argv[1:], env)
