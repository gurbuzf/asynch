#!/bin/bash
# Builds the self-contained Linux wheel of the asynch package in a clean Ubuntu 20.04 container, as the GitHub
# workflow .github/workflows/wheel.yml does. From the repository folder:
#
#   docker run --rm -v "$PWD":/w ubuntu:20.04 bash /w/python/ci/build_linux_wheel.sh
#
# The wheel is written to dist/. Ubuntu 20.04 because its C library (glibc 2.31) is old: the wheel then installs on
# every Linux with glibc 2.31 or newer (Ubuntu 20.04+, Debian 11+, RHEL 9+, ...). ASYNCH is built with the MPICH of
# the `mpich` package of PyPI (the wheel requires that package); make check must pass before the wheel is made.
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# --no-install-recommends: the recommended packages of HDF5 bring Open MPI, which must not be linked instead of MPICH
apt-get install -y -qq --no-install-recommends gcc gfortran libc6-dev make autoconf automake libtool pkg-config \
    libhdf5-dev libpq-dev zlib1g-dev check python3.9 python3.9-venv ca-certificates file > /dev/null
python3.9 -m venv /tmp/wheel-venv
/tmp/wheel-venv/bin/pip install -q --upgrade pip
/tmp/wheel-venv/bin/pip install -q mpich auditwheel patchelf wheel numpy h5py
export PATH=/tmp/wheel-venv/bin:$PATH

# build in a copy, so that the repository is left as it was
rm -rf /tmp/src && mkdir /tmp/src && cp -a /w/. /tmp/src/ && cd /tmp/src
rm -rf build dist docs/_build
autoreconf --install > /dev/null 2>&1
mkdir build && cd build
../configure CC=/tmp/wheel-venv/bin/mpicc CFLAGS="-O3 -DNDEBUG -Wno-format-security" > configure.log 2>&1 \
    || { tail -30 configure.log; exit 1; }
make -j"$(nproc)" > make.log 2>&1 || { tail -30 make.log; exit 1; }
ldd src/.libs/libasynch.so | grep -q "libmpi.so.12 => /tmp/wheel-venv" \
    || { echo "libasynch is not linked with the MPICH of the mpich package:"; ldd src/.libs/libasynch.so; exit 1; }
make check > check.log 2>&1 || { tail -40 check.log; cat tests/*.log | tail -60; exit 1; }
grep -E "^# (PASS|FAIL):" check.log

cd /tmp/src
python/build_wheel.sh build /w/dist
chown -R "$(stat -c %u:%g /w)" /w/dist
ls -l /w/dist
