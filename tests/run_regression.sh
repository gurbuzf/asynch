#!/bin/sh
# Runs every example with the program just built and compares its outputs with the reference results
# shipped in examples/ (see docs/guide/09_reproducibility.md). Called by `make check`.
# Exit code 77 means "skipped" to automake: Python 3 or NumPy is missing.
srcdir=${srcdir:-$(dirname "$0")}
command -v python3 >/dev/null 2>&1 || { echo "python3 not found: regression tests skipped"; exit 77; }
python3 -c "import numpy" 2>/dev/null || { echo "NumPy not found: regression tests skipped"; exit 77; }
exec python3 "$srcdir/regression/run_examples.py" --asynch "$ASYNCH_EXE" --np 1
