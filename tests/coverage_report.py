#!/usr/bin/env python3
"""
Line coverage of the C library by the tests, from a build compiled with --coverage.

    mkdir build-cov && cd build-cov
    ../configure CFLAGS="-O0 -g --coverage" LDFLAGS="--coverage"
    make -j4 && make check
    python3 ../tests/coverage_report.py .            # table per source file, then the total

The static library (used by the asynch program and the C unit tests) and the shared library (used by the Python
tests) are compiled separately; a line counts as covered if either executed it. Only gcov is needed (part of GCC).
"""
import collections
import glob
import gzip
import json
import os
import subprocess
import sys
import tempfile


def main(build):
    build = os.path.abspath(build)
    executed = collections.defaultdict(set)     # source -> lines executed
    lines = collections.defaultdict(set)        # source -> lines with code
    # os.walk, not glob: glob skips hidden folders such as .libs (the shared library's objects)
    gcdas = [os.path.join(d, f) for d, _, files in os.walk(os.path.join(build, "src")) for f in files
             if f.endswith(".gcda")]
    if not gcdas:
        sys.exit("no .gcda files under %s/src: build with --coverage and run make check first" % build)
    with tempfile.TemporaryDirectory() as tmp:
        for gcda in gcdas:
            subprocess.run(["gcov", "--json-format", "-o", os.path.dirname(gcda), gcda], cwd=tmp,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for js in glob.glob(os.path.join(tmp, "*.gcov.json.gz")):
                with gzip.open(js) as f:
                    data = json.load(f)
                os.unlink(js)
                for fl in data["files"]:
                    name = fl["file"]
                    if "/src/" not in name or name.endswith(".h"):
                        continue
                    name = "src/" + name.split("/src/", 1)[1]
                    for ln in fl["lines"]:
                        lines[name].add(ln["line_number"])
                        if ln["count"] > 0:
                            executed[name].add(ln["line_number"])
    total_l = total_e = 0
    print("%-40s %8s %8s %7s" % ("file", "lines", "tested", "%"))
    for name in sorted(lines, key=lambda n: -len(lines[n])):
        n, e = len(lines[name]), len(executed[name])
        total_l += n
        total_e += e
        print("%-40s %8d %8d %6.1f%%" % (name, n, e, 100.0 * e / n if n else 0))
    print("%-40s %8d %8d %6.1f%%" % ("TOTAL", total_l, total_e, 100.0 * total_e / total_l))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
