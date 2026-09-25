#!/usr/bin/env python3
"""
ASYNCH regression harness
=========================

Runs every example shipped in ``examples/`` and compares the files it
produces against the reference ("benchmark") results stored in the
repository.

Why a tolerance and not a byte-by-byte diff?
--------------------------------------------
ASYNCH is an *adaptive* ODE solver. Tiny differences in floating point
arithmetic (another compiler, another libm, another CPU, a different number of
MPI processes) change the step sizes chosen by the solver, which changes the
results in the ~6th-7th significant digit. Those differences are far below the
solver's own error tolerances and are *not* scientific changes. A real
regression (a changed equation, a wrong parameter) shows up as a difference of
several percent. We therefore compare with

        |new - ref| <= atol + rtol * |ref|

and always print the largest absolute and relative difference found, so a
human can judge the size of any change.

Usage
-----
    python3 tests/regression/run_examples.py                 # uses build/src/asynch
    python3 tests/regression/run_examples.py --asynch /path/to/asynch --np 2
    python3 tests/regression/run_examples.py --only clearcreek --keep

Only the Python standard library is needed. If ``h5py`` is installed, the HDF5
snapshot files are compared too; otherwise that comparison is skipped.

Exit status is 0 when every case passes (expected failures excluded), 1 otherwise.
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Test cases.
#   workdir : directory (relative to examples/) from which asynch is started
#   gbl     : global file to run
#   compare : list of (produced file, reference file, kind); paths relative to workdir
#   xfail   : None, or a string explaining why the comparison is known to fail
#             (a crash / non-zero exit code is always reported as FAIL)
# ---------------------------------------------------------------------------
CASES = [
    {
        "name": "test (model 190)",
        "workdir": ".",
        "gbl": "test.gbl",
        "compare": [("test.pea", "results/test.pea", "pea")],
        "xfail": None,
    },
    {
        "name": "clearcreek (model 254)",
        "workdir": ".",
        "gbl": "clearcreek.gbl",
        "compare": [("clearcreek.pea", "results/clearcreek.pea", "pea")],
        # See docs/guide/05_known_issues.md, issue "R-02".
        "xfail": ("reference dates from 2015 and was produced by a longer simulation "
                  "(outlet peak at 3001 min, but clearcreek.gbl simulates 1440 min)"),
    },
]
for _m in (192, 196, 258, 259):
    CASES.append({
        "name": "model_%d" % _m,
        "workdir": "more/model_%d" % _m,
        "gbl": "test%d.gbl" % _m,
        "compare": [
            ("results/test%d_hydr.csv" % _m, "results_benchmark/test%d_hydr.csv" % _m, "csv"),
            ("results/test%d_peak.pea" % _m, "results_benchmark/test%d_peak.pea" % _m, "pea"),
            ("results/test%d_snap.h5" % _m, "results_benchmark/test%d_snap.h5" % _m, "h5"),
        ],
        "xfail": None,
    })
# See docs/guide/05_known_issues.md, issue "R-03".
CASES[-1]["xfail"] = ("benchmark was produced with an evaporation file that is not in the "
                      "repository; the 2018 code gives the same result as today's code")


# ---------------------------------------------------------------------------
# Readers. Each returns a dict {key: [floats]} so that files can be compared
# independently of the order in which links are written.
# ---------------------------------------------------------------------------
def read_pea(path):
    """.pea (Classic format): 2 header lines, blank, then 'link_id area time_to_peak peak_value'."""
    rows = {}
    with open(path) as f:
        lines = [l.split() for l in f if l.strip()]
    header, body = lines[:2], lines[2:]
    rows["header"] = [float(x) for h in header for x in h]
    for parts in body:
        rows["link %s" % parts[0]] = [float(x) for x in parts[1:]]
    return rows


def read_csv(path):
    """.csv hydrographs: 2 header lines, then one row per output time (fixed order)."""
    rows = {}
    with open(path) as f:
        lines = f.read().splitlines()[2:]
    for i, line in enumerate(lines):
        cells = [c for c in line.split(",") if c.strip()]
        rows["row %d" % i] = [float(c) for c in cells]
    return rows


def read_h5(path):
    """.h5 snapshot: dataset 'snapshot' with columns link_id, state_0, state_1, ..."""
    import h5py  # optional dependency, imported lazily
    rows = {}
    with h5py.File(path, "r") as f:
        data = f["snapshot"][:]
        rows["attr model"] = [float(f.attrs["model"][0])]
    names = [n for n in data.dtype.names if n != "link_id"]
    for rec in data:
        rows["link %d" % rec["link_id"]] = [float(rec[n]) for n in names]
    return rows


READERS = {"pea": read_pea, "csv": read_csv, "h5": read_h5}


def compare(new, ref, rtol, atol):
    """Return (ok, messages, max_abs, max_rel)."""
    msgs = []
    max_abs = max_rel = 0.0
    missing = sorted(set(ref) - set(new))
    extra = sorted(set(new) - set(ref))
    if missing:
        msgs.append("missing entries: %s" % ", ".join(missing[:5]))
    if extra:
        msgs.append("unexpected entries: %s" % ", ".join(extra[:5]))
    n_bad = 0
    for key in sorted(set(ref) & set(new)):
        a, b = new[key], ref[key]
        if len(a) != len(b):
            msgs.append("%s: %d values, expected %d" % (key, len(a), len(b)))
            n_bad += 1
            continue
        for x, y in zip(a, b):
            if math.isnan(x) or math.isnan(y):
                if not (math.isnan(x) and math.isnan(y)):
                    n_bad += 1
                continue
            d = abs(x - y)
            max_abs = max(max_abs, d)
            if y != 0.0:
                max_rel = max(max_rel, d / abs(y))
            if d > atol + rtol * abs(y):
                n_bad += 1
                if n_bad <= 3:
                    msgs.append("%s: got %.10g, expected %.10g" % (key, x, y))
    if n_bad > 3:
        msgs.append("... %d values outside tolerance in total" % n_bad)
    ok = not missing and not extra and n_bad == 0
    return ok, msgs, max_abs, max_rel


def find_mpirun():
    for name in ("mpirun", "mpiexec"):
        p = shutil.which(name)
        if p:
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--asynch", default=os.path.join(REPO, "build", "src", "asynch"),
                    help="path to the asynch executable (default: build/src/asynch)")
    ap.add_argument("--np", type=int, default=1, help="number of MPI processes (default 1)")
    ap.add_argument("--rtol", type=float, default=1e-4, help="relative tolerance (default 1e-4)")
    ap.add_argument("--atol", type=float, default=1e-5,
                    help="absolute tolerance (default 1e-5, 10x tighter than the loosest solver "
                         "tolerance used by the examples)")
    ap.add_argument("--only", help="run only cases whose name contains this text")
    ap.add_argument("--keep", action="store_true", help="keep the temporary run directory")
    args = ap.parse_args()

    if not os.path.isfile(args.asynch):
        sys.exit("asynch executable not found at %s (build it first, or pass --asynch)" % args.asynch)
    mpirun = find_mpirun()
    if not mpirun:
        sys.exit("mpirun/mpiexec not found in PATH")
    try:
        import h5py  # noqa: F401
        have_h5py = True
    except ImportError:
        have_h5py = False
        print("note: h5py not installed, .h5 snapshot comparisons are skipped\n")

    # Run in a scratch copy so that the repository is never modified.
    tmp = tempfile.mkdtemp(prefix="asynch_regression_")
    run_root = os.path.join(tmp, "examples")
    shutil.copytree(os.path.join(REPO, "examples"), run_root)

    env = dict(os.environ)
    env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")          # harmless when not root
    env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    mpi_cmd = [mpirun, "-n", str(args.np)]
    if args.np > 1:
        mpi_cmd.append("--oversubscribe")

    failures = 0
    for case in CASES:
        if args.only and args.only not in case["name"]:
            continue
        wd = os.path.join(run_root, case["workdir"])
        os.makedirs(os.path.join(wd, "results"), exist_ok=True)
        log_path = os.path.join(wd, "asynch_run.log")
        with open(log_path, "w") as log:
            rc = subprocess.call(mpi_cmd + [args.asynch, case["gbl"]], cwd=wd,
                                 stdout=log, stderr=subprocess.STDOUT, env=env)

        case_ok = rc == 0
        lines = ["  exit code: %d%s" % (rc, "" if rc == 0 else "  <-- FAIL, last lines of the log:")]
        if rc != 0:
            with open(log_path, errors="replace") as log:
                # drop mpirun's own boilerplate so the actual error message is visible
                noise = ("---", "Primary job", "a non-zero exit", "mpirun ", "Per user-direction", "[")
                tail = [l.rstrip() for l in log if l.strip() and not l.lstrip().startswith(noise)][-6:]
            lines += ["      | " + l for l in tail]
        for produced, reference, kind in case["compare"]:
            if kind == "h5" and not have_h5py:
                continue
            p, r = os.path.join(wd, produced), os.path.join(wd, reference)
            if not os.path.isfile(p):
                lines.append("  %-28s FAIL: file was not produced" % produced)
                case_ok = False
                continue
            try:
                ok, msgs, mabs, mrel = compare(READERS[kind](p), READERS[kind](r), args.rtol, args.atol)
            except Exception as exc:  # unreadable/corrupt output
                ok, msgs, mabs, mrel = False, ["could not read: %s" % exc], float("nan"), float("nan")
            case_ok &= ok
            lines.append("  %-28s %s  (max abs diff %.3g, max rel diff %.3g)"
                         % (os.path.basename(produced), "ok  " if ok else "FAIL", mabs, mrel))
            lines += ["      " + m for m in msgs]

        if case_ok:
            status = "PASS"
        elif case["xfail"] and rc == 0:
            # A known mismatch with the reference is tolerated, a crash never is.
            status = "XFAIL (known: %s)" % case["xfail"]
        else:
            status = "FAIL"
            failures += 1
        print("[%s] %s" % (status.split(" ")[0], case["name"]))
        if status.startswith("XFAIL"):
            print("  " + status)
        print("\n".join(lines) + "\n")

    if args.keep:
        print("run directory kept at %s" % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%d unexpected failure(s)" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
