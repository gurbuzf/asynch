"""
Shared helpers of the Python tests.

The tests use the Python package in python/ and the library and program of a build. They are found with,
in order: the environment variables ASYNCH_LIBRARY (libasynch.so) and ASYNCH_EXE (the asynch program), then
the build tree (src/.libs and src/ of the current directory when run by `make check`, then of the
repository), then the installed ones.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXAMPLES = os.path.join(REPO, "examples")
sys.path.insert(0, os.path.join(REPO, "python"))


def _first(paths):
    for p in paths:
        if p and os.path.exists(p):
            return os.path.abspath(p)
    return None


def find_library():
    return _first([os.environ.get("ASYNCH_LIBRARY"),
                   os.path.join(os.getcwd(), "src", ".libs", "libasynch.so"),
                   os.path.join(os.getcwd(), "..", "src", ".libs", "libasynch.so"),
                   os.path.join(REPO, "src", ".libs", "libasynch.so"),
                   "/usr/local/lib/libasynch.so"])


def find_exe():
    return _first([os.environ.get("ASYNCH_EXE"),
                   os.path.join(os.getcwd(), "src", "asynch"),
                   os.path.join(os.getcwd(), "..", "src", "asynch"),
                   os.path.join(REPO, "src", "asynch"),
                   shutil.which("asynch")])


LIBRARY = find_library()
if LIBRARY:
    os.environ["ASYNCH_LIBRARY"] = LIBRARY
EXE = find_exe()

# compiled test models go to a private cache
os.environ.setdefault("ASYNCH_MODEL_CACHE", os.path.join(tempfile.gettempdir(), "asynch-test-models-%d" % os.getuid()))

requires_library = unittest.skipUnless(LIBRARY, "libasynch.so not found (set ASYNCH_LIBRARY)")
requires_exe = unittest.skipUnless(EXE, "asynch program not found (set ASYNCH_EXE)")


def has_compiler():
    import sysconfig
    cc = os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc"
    return shutil.which(cc.split()[0]) is not None


requires_compiler = unittest.skipUnless(has_compiler(), "no C compiler")


def has_numba():
    try:
        import numba  # noqa: F401
        return True
    except ImportError:
        return False


requires_numba = unittest.skipUnless(has_numba(), "numba not installed")


def has_mpirun():
    return shutil.which("mpirun") is not None


class InExamples(unittest.TestCase):
    """Each test runs in a fresh copy of examples/ (the global files use paths relative to it)."""

    def setUp(self):
        self._old = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix="asynch-test-")
        self.dir = os.path.join(self.tmp, "examples")
        shutil.copytree(EXAMPLES, self.dir)          # a copy: the reference results are never touched
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self._old)
        shutil.rmtree(self.tmp, ignore_errors=True)


def run_cli(gbl, cwd, np=1):
    """Run the asynch program; returns the completed process."""
    cmd = [EXE, gbl] if np == 1 else ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(np), EXE, gbl]
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                          timeout=600)


def run_python(code, cwd, np=1, timeout=600):
    """Run Python code in a new process (with mpirun if np > 1); returns the completed process."""
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "python"))
    cmd = [sys.executable, "-c", code]
    if np > 1:
        cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(np)] + cmd
    return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=timeout)
