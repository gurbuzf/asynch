"""Start parallel (MPI) runs from Python, for instance from a Jupyter notebook.

A Python program cannot become several MPI processes after it has started, so these functions start new ones with
`mpiexec`, and wait for them:

    import asynch
    asynch.run_parallel("my_basin.gbl", 4)                   # the asynch program on 4 processes
    asynch.run_script_parallel("my_study.py", 4)             # a Python script on 4 processes (it uses Simulation)

The same as typing `mpiexec -n 4 asynch my_basin.gbl` or `mpiexec -n 4 python3 my_study.py` in a terminal. The
output files are those the global file names, as with the program.
"""
import os
import shutil
import subprocess
import sys
import sysconfig

from ._cli import BIN


class ParallelRunError(RuntimeError):
    """A parallel run ended with an error; `.returncode` and `.output` (the text it printed, if captured)."""

    def __init__(self, message, returncode, output=None):
        super().__init__(message)
        self.returncode = returncode
        self.output = output


def find_mpiexec():
    """The mpiexec (or mpirun) to use: the one next to this Python (the `mpich` package of the ready-made wheel, or an
    activated environment), else the first on PATH."""
    folders = [os.path.dirname(sys.executable), sysconfig.get_path("scripts")]
    for folder in folders:
        for name in ("mpiexec", "mpirun"):
            path = os.path.join(folder, name)
            if folder and os.path.exists(path):
                return path
    for name in ("mpiexec", "mpirun"):
        path = shutil.which(name)
        if path:
            return path
    raise ParallelRunError("mpiexec was not found: install MPI (with the ready-made wheel it comes with the `mpich` "
                           "package), or pass mpiexec=...", None)


def find_program():
    """The asynch program: $ASYNCH_EXE, the one carried by the ready-made wheel, else `asynch` on PATH."""
    candidates = [os.environ.get("ASYNCH_EXE"), os.path.join(BIN, "asynch"), shutil.which("asynch")]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise ParallelRunError("the asynch program was not found: install the ready-made wheel, build ASYNCH "
                           "(make install), or set ASYNCH_EXE", None)


def _environment():
    env = dict(os.environ)
    # Open MPI: allowed as root (containers) and with more processes than cores; MPICH ignores these variables
    env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")
    env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    env.setdefault("OMPI_MCA_rmaps_base_oversubscribe", "1")
    from ._lib import mpich_libdir
    mpi_dir = mpich_libdir()
    if mpi_dir:                                           # the MPICH of the ready-made wheel, for the processes
        env["LD_LIBRARY_PATH"] = mpi_dir + (os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    return env


def _run(command, processes, cwd, mpiexec, mpiexec_args, capture, timeout):
    if int(processes) < 1:
        raise ValueError("processes must be at least 1")
    cmd = [mpiexec or find_mpiexec(), "-n", str(int(processes))] + list(mpiexec_args) + list(command)
    proc = subprocess.run(cmd, cwd=cwd, env=_environment(), timeout=timeout, universal_newlines=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)
    if proc.returncode != 0:
        raise ParallelRunError("%s ended with exit code %d%s" % (" ".join(cmd), proc.returncode,
                               (":\n" + proc.stdout[-3000:]) if capture and proc.stdout else ""),
                               proc.returncode, proc.stdout)
    return proc


def run_parallel(global_file, processes, cwd=None, program=None, mpiexec=None, mpiexec_args=(), capture=False,
                 timeout=None):
    """Runs the asynch program on a global file with `processes` MPI processes, and waits for it.

    Parameters
    ----------
    global_file : str
        The global file. As with the program, the file names inside it are relative to `cwd`.
    processes : int
        Number of MPI processes.
    cwd : str, optional
        Folder to run in (default: the current folder).
    program, mpiexec : str, optional
        Paths of the asynch program and of mpiexec (default: found by find_program and find_mpiexec).
    mpiexec_args : sequence of str
        Extra options for mpiexec, e.g. ["--hostfile", "hosts"].
    capture : bool
        Return the printed text in `.stdout` instead of showing it.
    timeout : float, optional
        Seconds before the run is stopped.

    Returns
    -------
    subprocess.CompletedProcess
        Raises ParallelRunError if the run fails.
    """
    return _run([program or find_program(), global_file], processes, cwd, mpiexec, mpiexec_args, capture, timeout)


def run_script_parallel(script, processes, *args, cwd=None, python=None, mpiexec=None, mpiexec_args=(), capture=False,
                        timeout=None):
    """Runs a Python script with `processes` MPI processes (`mpiexec -n processes python script args...`), and waits.

    Every process runs the whole script; `Simulation` shares the links between them (chapter 10.9 of the guide).
    The other parameters are those of run_parallel; `python` defaults to this Python.
    """
    return _run([python or sys.executable, script] + [str(a) for a in args], processes, cwd, mpiexec, mpiexec_args,
                capture, timeout)
