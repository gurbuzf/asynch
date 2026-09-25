#!/bin/sh
# Runs the tests of the Python package (tests/python) against this build. Called by `make check`,
# which sets ASYNCH_LIBRARY and ASYNCH_EXE to the library and program just built.
# Exit code 77 means "skipped" to automake: Python 3 or NumPy is missing.
srcdir=${srcdir:-$(dirname "$0")}
command -v python3 >/dev/null 2>&1 || { echo "python3 not found: Python tests skipped"; exit 77; }
python3 -c "import numpy" 2>/dev/null || { echo "NumPy not found: Python tests skipped"; exit 77; }
exec python3 -m unittest discover -v -s "$srcdir/python" -p "test_*.py"
