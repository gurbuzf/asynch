#!/usr/bin/env python3
"""
Before/after figures for the documentation (docs/guide/figures/).

Runs the two configurations that produced the reference results shipped with ASYNCH
(examples/test_2015.gbl and examples/clearcreek_2015.gbl) with two executables:
  * "before": the original, unmodified code (build it with tests/regression/build_original.sh)
  * "after":  the current code
and compares both with the 2015 reference files in examples/results/.

    python3 tools/python/make_comparison_plots.py \
        --before ~/asynch-original/build/src/asynch --after build/src/asynch

Needs numpy and matplotlib, and mpirun in the PATH. Takes about a minute.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import asynch_io  # noqa: E402

# Colours: validated categorical palette (first three slots) + neutral ink for text and reference.
AFTER, BEFORE, THIRD = "#2a78d6", "#eb6834", "#1baf7a"
REF, INK, INK2, GRID, SURFACE = "#0b0b0b", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
OUTLET = 2527          # outlet link of the Clear Creek network


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
        "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
        "lines.linewidth": 1.6,
    })


def run(exe, gbl_text, name, np_):
    """Run one global file (given as text) in a fresh copy of examples/; return its folder."""
    d = tempfile.mkdtemp(prefix="asynch_plot_")
    shutil.copytree(os.path.join(REPO, "examples"), d, dirs_exist_ok=True)
    os.makedirs(os.path.join(d, "out_2015"), exist_ok=True)
    with open(os.path.join(d, name), "w") as f:
        f.write(gbl_text)
    env = dict(os.environ, OMPI_ALLOW_RUN_AS_ROOT="1", OMPI_ALLOW_RUN_AS_ROOT_CONFIRM="1")
    with open(os.path.join(d, "run.log"), "w") as log:
        rc = subprocess.call(["mpirun", "-n", str(np_), exe, name], cwd=d, stdout=log,
                             stderr=subprocess.STDOUT, env=env, timeout=1800)
    if rc != 0:
        sys.exit("run of %s with %s failed, see %s/run.log" % (name, exe, d))
    return d


def with_method(gbl_text, index):
    """Same global file, other numerical method (line after '%Numerical solver index')."""
    lines = gbl_text.splitlines(True)
    k = next(i for i, l in enumerate(lines) if l.startswith("%Numerical solver index"))
    lines[k + 1] = "%d\n" % index
    return "".join(lines)


def max_diff(new, ref):
    """Largest absolute difference between two {link: array} dictionaries."""
    return max(float(np.max(np.abs(np.asarray(new[k]) - np.asarray(ref[k])))) for k in ref)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--before", required=True, help="asynch executable of the original code")
    ap.add_argument("--after", required=True, help="asynch executable of the current code")
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "guide", "figures"))
    ap.add_argument("--np", type=int, default=1, help="MPI processes (default 1)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    style()

    ex = os.path.join(REPO, "examples")
    gbl = {n: open(os.path.join(ex, n + ".gbl")).read() for n in ("test_2015", "clearcreek_2015")}
    runs = {(v, n): run(exe, gbl[n], n + ".gbl", args.np)
            for v, exe in (("before", args.before), ("after", args.after)) for n in gbl}
    methods = {m: run(args.after, with_method(gbl["clearcreek_2015"], m), "m%d.gbl" % m, args.np)
               for m in (0, 1)}
    methods[2] = runs[("after", "clearcreek_2015")]

    # ---- numbers: largest difference from each 2015 reference file ----
    readers = {"dat": asynch_io.read_dat, "rec": asynch_io.read_rec}
    labels, before, after = [], [], []
    for ex_name in ("test", "clearcreek"):
        for ext in ("dat", "pea", "rec"):
            ref_path = os.path.join(ex, "results", "%s.%s" % (ex_name, ext))
            vals = []
            for v in ("before", "after"):
                path = os.path.join(runs[(v, ex_name + "_2015")], "out_2015", "%s.%s" % (ex_name, ext))
                if ext == "pea":     # compare peak discharge only (time of peak is ill-conditioned)
                    new, ref = asynch_io.read_pea(path), asynch_io.read_pea(ref_path)
                    vals.append(max(abs(new[k][2] - ref[k][2]) for k in ref))
                else:
                    new, ref = readers[ext](path), readers[ext](ref_path)
                    if ext == "dat":  # drop the time column
                        new = {k: a[:, 1:] for k, a in new.items()}
                        ref = {k: a[:, 1:] for k, a in ref.items()}
                    vals.append(max_diff(new, ref))
            labels.append("%s\n.%s" % (ex_name, ext))
            before.append(vals[0])
            after.append(vals[1])
    print("largest absolute difference from the 2015 reference files:")
    for l, b, a in zip(labels, before, after):
        print("  %-18s before %.2e   after %.2e" % (l.replace("\n", " "), b, a))

    # ---- figure 1: agreement with the reference results ----
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(labels))
    w = 0.38
    floor = 1e-9                      # a perfect match is drawn at the bottom of the log axis
    ax.bar(x - w / 2 - 0.01, np.maximum(before, floor), w, color=BEFORE, label="before (original code)")
    ax.bar(x + w / 2 + 0.01, np.maximum(after, floor), w, color=AFTER, label="after (this version)")
    ax.axhline(1e-4, color=INK2, lw=1, ls="--")
    ax.text(-0.45, 1.25e-4, "solver tolerance of clearcreek (1e-4)", ha="left", va="bottom",
            color=INK2, fontsize=9)
    ax.set_yscale("log")
    ax.set_ylim(floor, 1)
    ax.set_xticks(x, labels)
    ax.set_ylabel("largest difference from 2015 reference")
    ax.set_title("Agreement with the reference results shipped with ASYNCH (2015)", loc="left")
    ax.legend(loc="upper left", ncol=2)
    for xi, vb, va in zip(x, before, after):
        if vb == 0 and va == 0:
            ax.text(xi, floor * 1.4, "both identical", ha="center", fontsize=8, color=INK2)
            continue
        ax.text(xi - w / 2 - 0.01, max(vb, floor) * 1.4, "%.0e" % vb if vb else "identical", ha="center",
                fontsize=8, color=INK2)
        ax.text(xi + w / 2 + 0.01, max(va, floor) * 1.4, "%.0e" % va if va else "identical", ha="center",
                fontsize=8, color=INK2)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "reference_agreement.png"), dpi=150)
    plt.close(fig)

    # ---- figure 2: Clear Creek outlet, total discharge and baseflow ----
    ref = asynch_io.read_dat(os.path.join(ex, "results", "clearcreek.dat"))[OUTLET]
    b = asynch_io.read_dat(os.path.join(runs[("before", "clearcreek_2015")], "out_2015", "clearcreek.dat"))[OUTLET]
    a = asynch_io.read_dat(os.path.join(runs[("after", "clearcreek_2015")], "out_2015", "clearcreek.dat"))[OUTLET]
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    for ax, col, name in ((axes[0], 1, "total discharge q"), (axes[1], 2, "baseflow part q_b")):
        ax.plot(ref[:, 0] / 60, ref[:, col], color=REF, lw=3.2, alpha=0.25, label="2015 reference")
        ax.plot(b[:, 0] / 60, b[:, col], color=BEFORE, ls="--", label="before (original code)")
        ax.plot(a[:, 0] / 60, a[:, col], color=AFTER, ls=":", lw=2.2, label="after (this version)")
        ax.set_ylabel("%s [m³/s]" % name)
    axes[0].set_title("Clear Creek outlet (link %d), 2015 configuration: 100 hours from 2014-05-01"
                      % OUTLET, loc="left")
    axes[0].legend(loc="upper right")
    axes[1].set_xlabel("time since start [hours]")
    axes[1].annotate("before: baseflow stays at 0\n(floor max(0.001, q_b), issue S-02)",
                     xy=(70, 0.0), xytext=(45, 0.04), color=BEFORE, fontsize=9,
                     arrowprops=dict(arrowstyle="->", color=BEFORE))
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "clearcreek_outlet_before_after.png"), dpi=150)
    plt.close(fig)

    # ---- figure 3: the three numerical methods agree (after the fix of issue B-13) ----
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    names = {0: "method 0: RK 3(2)", 1: "method 1: RK 4(3)", 2: "method 2: Dormand-Prince 5(4)"}
    colors = {0: THIRD, 1: BEFORE, 2: AFTER}
    styles = {0: "-", 1: "--", 2: ":"}
    hyd = {m: asynch_io.read_dat(os.path.join(methods[m], "out_2015", "clearcreek.dat"))[OUTLET]
           for m in (0, 1, 2)}
    for m in (0, 1, 2):
        ax.plot(hyd[m][:, 0] / 60, hyd[m][:, 1], color=colors[m], ls=styles[m], lw=2.0 if m == 2 else 1.6,
                label=names[m])
    for m in (0, 1):
        ax2.plot(hyd[m][:, 0] / 60, hyd[m][:, 1] - hyd[2][:, 1], color=colors[m], ls=styles[m],
                 label=names[m] + " minus method 2")
    ax.set_ylabel("discharge q [m³/s]")
    ax.set_title("Clear Creek outlet with the three numerical methods (after fix B-13)", loc="left")
    ax.legend(loc="upper right")
    ax2.axhline(0, color=INK2, lw=0.8)
    ax2.set_ylabel("difference [m³/s]")
    ax2.set_xlabel("time since start [hours]")
    ax2.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "solver_methods_agree.png"), dpi=150)
    plt.close(fig)

    for d in set(runs.values()) | set(methods.values()):
        shutil.rmtree(d, ignore_errors=True)
    print("figures written to", args.out)


if __name__ == "__main__":
    main()
