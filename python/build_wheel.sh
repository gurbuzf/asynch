#!/bin/sh
# Builds the self-contained wheel of the asynch package: the Python code, libasynch.so, the asynch program and the
# libraries they need (HDF5, libpq, ...), so that `pip install asynch-*.whl` works without building ASYNCH. MPI is
# not copied: the wheel requires the `mpich` package of PyPI, which brings the MPI library and `mpiexec`.
#
#   python/build_wheel.sh BUILD_DIR [OUT_DIR]
#
# BUILD_DIR is a build folder of ASYNCH compiled with the mpicc of the PyPI mpich package, e.g.
#   python3 -m venv ~/wheel-venv && ~/wheel-venv/bin/pip install mpich auditwheel patchelf wheel
#   ../configure CC=~/wheel-venv/bin/mpicc CFLAGS="-O3 -DNDEBUG" && make
# and this script run with that environment first in PATH. OUT_DIR defaults to ./dist.
set -e
[ -n "$1" ] || { echo "usage: $0 BUILD_DIR [OUT_DIR]" >&2; exit 2; }
build=$(cd "$1" && pwd)
out=${2:-dist}
here=$(cd "$(dirname "$0")" && pwd)
lib="$build/src/.libs/libasynch.so"
[ -f "$lib" ] || { echo "$lib not found: build ASYNCH first" >&2; exit 1; }
# the MPICH ABI (libmpi.so.12), which the mpich package of PyPI provides at run time
ldd "$lib" | grep -q "libmpi.so.12 " || { echo "$lib is not linked with MPICH (libmpi.so.12): see above" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp -r "$here/." "$tmp/src"
rm -rf "$tmp/src/build" "$tmp/src"/*.egg-info "$tmp/src/asynch/__pycache__" "$tmp/src/asynch/bin"
cp -L "$lib" "$tmp/src/asynch/libasynch.so"
mkdir -p "$tmp/src/asynch/bin"
# the program: src/asynch, or src/.libs/asynch when src/asynch is a libtool wrapper script
prog="$build/src/.libs/asynch"; [ -f "$prog" ] || prog="$build/src/asynch"
cp -L "$prog" "$tmp/src/asynch/bin/asynch"
python3 -m pip wheel --no-deps "$tmp/src" -w "$tmp/wheel"
auditwheel repair --exclude libmpi.so.12 "$tmp"/wheel/*.whl -w "$tmp/repaired"

# libmpi.so.12 is found in the lib folder of the environment, where pip installs the mpich package:
# <prefix>/lib/pythonX.Y/site-packages/asynch/libasynch.so -> <prefix>/lib, and one more level for asynch/bin/asynch
python3 -m wheel unpack "$tmp"/repaired/*.whl -d "$tmp/unpacked"
dir=$(echo "$tmp"/unpacked/*)
patchelf --add-rpath '$ORIGIN/../../..' "$dir/asynch/libasynch.so"
patchelf --add-rpath '$ORIGIN/../../../..' "$dir/asynch/bin/asynch"
# The libraries copied by auditwheel find each other in their own folder ($ORIGIN): a search path set on a library
# does not apply to the libraries it loads (DT_RUNPATH, which patchelf writes). The program's copy of libasynch also
# needs the folder of MPICH.
for f in "$dir"/asynch.libs/*.so*; do
    patchelf --add-rpath '$ORIGIN' "$f"
    case "$(basename "$f")" in libasynch*) patchelf --add-rpath '$ORIGIN/../../..' "$f" ;; esac
done
mkdir -p "$out"
python3 -m wheel pack "$dir" -d "$out"
