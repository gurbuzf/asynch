#!/usr/bin/env python3
"""
Plot the discharge at one link from one or more ASYNCH hydrograph files, to compare runs.

    python3 plot_hydrographs.py --link 80 outputs.h5 run2/outputs.h5 --out compare.png
    python3 plot_hydrographs.py --link 2527 clearcreek.h5 --column 2 --out baseflow.png

Accepted files: .dat, .csv and .h5 hydrograph outputs. By default the first state after the
time column is plotted (State0 = discharge for most models); change it with --column
(1 = first column after time, 2 = second, ...). The time axis is in hours from the start.
Labels default to the file names; set them with --labels "run A" "run B".
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asynch_io  # noqa: E402

COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]   # validated palette, first three slots
STYLES = ["-", "--", ":"]


def load(path):
    ext = os.path.splitext(path)[1]
    if ext == ".dat":
        return asynch_io.read_dat(path), "min"
    if ext == ".csv":
        return asynch_io.read_csv(path), "min"
    if ext == ".h5":
        data = asynch_io.read_h5_hydrographs(path)
        # the array layout (flag 6) stores unix time; the packet layout (flag 5) stores minutes
        first = next(iter(data.values()))
        return data, "unix" if first[0, 0] > 1e8 else "min"
    sys.exit("unknown file type: %s" % path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help="hydrograph files (.dat, .csv, .h5), at most 3")
    ap.add_argument("--link", type=int, required=True, help="link id to plot")
    ap.add_argument("--column", type=int, default=1, help="which output after time (default 1)")
    ap.add_argument("--labels", nargs="+", help="one label per file")
    ap.add_argument("--out", default="hydrograph.png", help="image file to write")
    args = ap.parse_args()
    if len(args.files) > 3:
        sys.exit("at most 3 files, so that the curves stay distinguishable")
    labels = args.labels or [os.path.relpath(f) for f in args.files]

    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (path, label) in enumerate(zip(args.files, labels)):
        data, unit = load(path)
        if args.link not in data:
            sys.exit("link %d is not in %s (links there: %s)" % (args.link, path, sorted(data)[:10]))
        d = data[args.link]
        hours = (d[:, 0] - d[0, 0]) / 3600.0 if unit == "unix" else d[:, 0] / 60.0
        ax.plot(hours, d[:, args.column], color=COLORS[i], ls=STYLES[i], lw=1.8, label=label)
        print("%s: link %d, maximum %.6g at %.2f h" % (label, args.link, d[:, args.column].max(),
                                                      hours[d[:, args.column].argmax()]))
    ax.set_xlabel("time since start [hours]")
    ax.set_ylabel("output column %d (discharge [m³/s] for column 1)" % args.column)
    ax.set_title("Link %d" % args.link, loc="left")
    ax.grid(True, color="#e4e3df")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print("written", args.out)


if __name__ == "__main__":
    main()
