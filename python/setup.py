"""Packaging of the asynch Python package (the metadata is in pyproject.toml).

Two kinds of wheel come from this folder:

* the pure-Python package (the default): it uses a libasynch.so built and installed from the sources;
* a self-contained wheel, when a libasynch.so has been copied into asynch/ first (python/build_wheel.sh does it, and
  the release workflow): the wheel then carries the library and the `asynch` program (asynch/bin), is marked as
  specific to the platform (py3-none-linux_x86_64), and `auditwheel repair` adds the libraries they need (HDF5,
  libpq, ...). MPI comes from the `mpich` package of PyPI, which it requires (it also provides `mpiexec`). It installs
  the command `asynch`.
"""
import glob
import os

from setuptools import setup
from setuptools.dist import Distribution

try:
    from setuptools.command.bdist_wheel import bdist_wheel
except ImportError:                                   # setuptools < 70
    from wheel.bdist_wheel import bdist_wheel

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = bool(glob.glob(os.path.join(HERE, "asynch", "libasynch.so*")))

SCRIPTS = ["asynch-py = asynch.__main__:main"]
if BUNDLED:
    # the programs carried in asynch/bin (see asynch/_cli.py)
    SCRIPTS += ["asynch = asynch._cli:asynch"]

REQUIRES = ["numpy"] + (["mpich"] if BUNDLED else [])


class BinaryDistribution(Distribution):
    """With the library inside, the package goes to platlib (platform-specific files), as auditwheel requires."""
    def has_ext_modules(self):
        return BUNDLED


class Wheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = not BUNDLED

    def get_tag(self):
        python, abi, plat = super().get_tag()
        # the library does not use the Python C API: one wheel serves every Python 3
        return ("py3", "none", plat) if BUNDLED else (python, abi, plat)


setup(
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": Wheel},
    package_data={"asynch": ["libasynch.so*", "bin/*"]} if BUNDLED else {},
    entry_points={"console_scripts": SCRIPTS},
    install_requires=REQUIRES,
)
