#!/bin/bash
# Tests the self-contained wheel in dist/ on a Linux without anything of ASYNCH, MPI, HDF5 or a compiler, as the
# GitHub workflow .github/workflows/wheel.yml does. From the repository folder, with any Linux image:
#
#   docker run --rm -v "$PWD":/w ubuntu:24.04 bash /w/python/ci/test_wheel.sh
#   docker run --rm -v "$PWD":/w python:3.9-slim-bullseye bash /w/python/ci/test_wheel.sh
#
# It installs the wheel with pip in a new virtual environment, then checks: the `asynch` command, runs on 2 processes
# with the `mpiexec` of the mpich package, h5py next to asynch, every example against the reference results (1 and 2
# processes), and the tests of the Python package.
set -e
if ! command -v python3 > /dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq python3 python3-venv ca-certificates > /dev/null
fi
python3 -m venv /tmp/v
/tmp/v/bin/pip install -q --upgrade pip
/tmp/v/bin/pip install -q /w/dist/asynch-*.whl h5py
export PATH=/tmp/v/bin:$PATH
pkg=$(python -c "import asynch, os; print(os.path.dirname(asynch.__file__))")
work=$(mktemp -d) && cp -a /w/examples /w/tests "$work/" && cd "$work/examples"

asynch -v | head -1
asynch test_2015.gbl > run.log 2>&1 || { cat run.log; exit 1; }
mpiexec -n 2 asynch clearcreek_2015.gbl > run2.log 2>&1 || { cat run2.log; exit 1; }
grep -q "Process 1 (2 total)" run2.log || { echo "mpiexec -n 2 did not start 2 processes:"; cat run2.log; exit 1; }
mpiexec -n 2 python python/run_example.py > run3.log 2>&1 || { cat run3.log; exit 1; }
python -c "import asynch; asynch._lib.lib(); import h5py; print('asynch and h5py in one program: ok')"
echo "examples against the references:"
for np in 1 2; do
    python "$work/tests/regression/run_examples.py" --asynch "$pkg/bin/asynch" --np $np > reg.log 2>&1 \
        || { cat reg.log; exit 1; }
    tail -1 reg.log
done
cd "$work/tests"
ASYNCH_LIBRARY="$pkg/libasynch.so" ASYNCH_EXE="$pkg/bin/asynch" python -m unittest discover -s python -p "test_*.py"
