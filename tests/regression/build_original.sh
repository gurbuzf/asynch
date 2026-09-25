#!/bin/sh
# Build an unmodified copy of ASYNCH at a given git commit, to compare results with.
#
#   tests/regression/build_original.sh [COMMIT] [DEST]
#
#   COMMIT  commit, tag or branch to build   (default: 84da43a, the original upstream code)
#   DEST    directory to build in            (default: $HOME/asynch-original)
#
# The executable ends up in DEST/build/src/asynch. Use it with
#   python3 tests/regression/run_examples.py --compare-to DEST/build/src/asynch
#
# Build the code under test with the same CFLAGS, otherwise compiler optimisations alone
# can cause (tiny) differences.
set -e

COMMIT=${1:-84da43a}
DEST=${2:-$HOME/asynch-original}
CFLAGS=${CFLAGS:-"-O3 -DNDEBUG -Wno-format-security"}
REPO=$(cd "$(dirname "$0")/../.." && pwd)

echo "Building commit $COMMIT into $DEST (CFLAGS=$CFLAGS)"
rm -rf "$DEST"
mkdir -p "$DEST/build"
# Export the sources of that commit (no .git, the repository is not modified).
git -C "$REPO" archive "$COMMIT" | tar -x -C "$DEST"
cd "$DEST"
autoreconf --install > autoreconf.log 2>&1
cd build
../configure CFLAGS="$CFLAGS" > configure.log 2>&1
make -j"$(nproc 2>/dev/null || echo 2)" > make.log 2>&1
echo "Done: $DEST/build/src/asynch"
