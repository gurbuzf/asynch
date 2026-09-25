#!/usr/bin/env python3
"""
Write a synthetic river network, and a complete model-190 setup for it, of any size.

The network is a "fishbone": a main channel of M reaches; every reach receives the reach upstream
of it plus K small side streams (leaves). Total links N = M * (1 + K). Link ids are 1..N, link 1 is
the outlet.

    python3 make_synthetic_network.py --links 70000 --out /tmp/big

writes big.rvr (topology), big.prm (parameters), big.ustr (uniform rain), big.uini (initial
state), big.sav (outlet only), and big.gbl (model 190, 2 hours, peaks for all links). Used by the
tests to check networks with more than 65 535 links (issue B-06).
"""
import argparse
import os

GBL = """%Model UID
190

%Begin and end date time
2017-01-01 00:00
2017-01-01 {end}

0	%Parameters to filenames

%Components to print
2
Time
State0

%Peakflow function
Classic

%Global parameters
%6 v_r  lambda_1  lambda_2  RC    v_h  v_g
6  0.33  0.20      -0.1     0.33  0.1  2.2917e-5

%No. steps stored at each link and
%Max no. steps transfered between procs
%Discontinuity buffer size
30 10 30

%Topology (0 = .rvr, 1 = database)
0 {name}.rvr

%DEM Parameters (0 = .prm, 1 = database)
0 {name}.prm

%Initial state (0 = .ini, 1 = .uini, 2 = .rec, 3 = .dbc, 4 = .h5)
1 {name}.uini

%Forcings (0 = none, 1 = .str, 2 = binary, 3 = database, 4 = .ustr, 5 = forecasting, 6 = .gz binary, 7 = recurring)
2

%Rain
4 {name}.ustr

%Evaporation
7 evap.mon
1398902400 1588291200

%Dam (0 = no dam, 1 = .dam, 2 = .qvs)
0

%Reservoir ids (0 = no reservoirs, 1 = .rsv, 2 = .dbc file)
0

%Where to put write hydrographs
%(0 = no output, 1 = .dat file, 2 = .csv file, 3 = database, 5 = .h5 packet, 6 = .h5 array)
1 5.0 {name}.dat

%Where to put peakflow data
%(0 = no output, 1 = .pea file, 2 = database)
1 {name}.pea

%.sav files for hydrographs and peak file
%(0 = save no data, 1 = .sav file, 2 = .dbc file, 3 = all links)
1 {name}.sav %Hydrographs
3 %Peakflows

%Snapshot information (0 = none, 1 = .rec, 2 = database, 3 = .h5, 4 = recurrent .h5)
0

%Filename for scratch work
tmp

%Numerical solver settings follow

%facmin, facmax, fac
.1 10.0 .9

%Solver flag (0 = data below, 1 = .rkd)
0
%Numerical solver index (0 = RK 3(2), 1 = RK 4(3), 2 = Dormand-Prince 5(4))
2
%Error tolerances (abs, rel, abs dense, rel dense)
1e-3 1e-3 1e-3
1e-6 1e-6 1e-6
1e-3 1e-3 1e-3
1e-6 1e-6 1e-6

# %End of file
"""


def write_network(out, links, side=9, minutes=120):
    """Write the files; return the actual number of links (a multiple of side + 1)."""
    stem = max(1, links // (side + 1))
    n = stem * (1 + side)
    os.makedirs(out, exist_ok=True)
    name = os.path.basename(os.path.normpath(out))
    leaf_area, hill_area, length = 0.10, 0.05, 0.5          # km2, km2, km

    # stem reach j (0 = outlet) has id j+1; its K leaves have ids stem+1+j*K ... stem+(j+1)*K
    def leaves(j):
        return [stem + 1 + j * side + k for k in range(side)]

    upstream = [0.0] * stem                                   # upstream area of each stem reach
    acc = 0.0
    for j in reversed(range(stem)):
        acc += side * leaf_area + hill_area
        upstream[j] = acc

    with open(os.path.join(out, name + ".rvr"), "w") as f:
        f.write("%d\n\n" % n)
        for j in range(stem):
            parents = leaves(j) + ([j + 2] if j + 1 < stem else [])
            f.write("%d\n%d %s\n\n" % (j + 1, len(parents), " ".join(map(str, parents))))
        for j in range(stem):
            for leaf in leaves(j):
                f.write("%d\n0\n\n" % leaf)

    with open(os.path.join(out, name + ".prm"), "w") as f:
        f.write("%d\n\n" % n)
        for j in range(stem):
            f.write("%d\n%.6f %.6f %.6f\n\n" % (j + 1, upstream[j], length, hill_area))
        for j in range(stem):
            for leaf in leaves(j):
                f.write("%d\n%.6f %.6f %.6f\n\n" % (leaf, leaf_area, length, leaf_area))

    with open(os.path.join(out, name + ".ustr"), "w") as f:
        f.write("3\n0 20.0\n30 10.0\n60 0.0\n")                 # mm/h: 20 for 30 min, 10 for 30 min
    with open(os.path.join(out, name + ".uini"), "w") as f:
        f.write("190\n0.000000\n\n1.000000e-6 0.000000e+00 0.000000e+00\n")
    with open(os.path.join(out, name + ".sav"), "w") as f:
        f.write("1\n")
    with open(os.path.join(out, "evap.mon"), "w") as f:
        f.write("\n".join(["0.0"] * 12) + "\n")
    end = "%02d:%02d" % (minutes // 60, minutes % 60)
    with open(os.path.join(out, name + ".gbl"), "w") as f:
        f.write(GBL.format(name=name, end=end))
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--links", type=int, required=True, help="approximate number of links")
    ap.add_argument("--out", required=True, help="output folder; files are named after it")
    ap.add_argument("--side", type=int, default=9, help="side streams per main-channel reach")
    ap.add_argument("--minutes", type=int, default=120, help="simulation length (< 24 h)")
    a = ap.parse_args()
    print("wrote %d links to %s" % (write_network(a.out, a.links, a.side, a.minutes), a.out))
