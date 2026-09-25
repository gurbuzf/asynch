"""
Read ASYNCH output files into Python (NumPy) objects.

Usage from Python:

    import sys; sys.path.insert(0, "tools/python")      # path to this folder
    import asynch_io

    hydro = asynch_io.read_dat("examples/out_2015/clearcreek.dat")
    t, q = hydro[2527][:, 0], hydro[2527][:, 1]           # time [min], discharge [m3/s] at link 2527

    peaks = asynch_io.read_pea("examples/test.pea")      # {link: (area, time_of_peak, peak_value)}
    state = asynch_io.read_rec("examples/out_2015/test.rec")  # {link: array of states}

Every reader returns a dictionary keyed by link id. The meaning of the columns depends on
the "%Components to print" block of the global file (.gbl) that produced the file.
Only NumPy is needed, plus h5py for the .h5 readers.
"""
import numpy as np


def read_dat(path):
    """Hydrographs in .dat format (global file: "1 <interval> file.dat").

    Layout: number of links, number of printed components, then for every link:
    "<link id> <number of rows>" followed by that many rows of components.
    Returns {link id: array [rows, components]}.
    """
    tok = open(path).read().split()
    n_links, n_comp = int(tok[0]), int(tok[1])
    out, i = {}, 2
    for _ in range(n_links):
        link, rows = int(tok[i]), int(tok[i + 1])
        i += 2
        out[link] = np.array(tok[i:i + rows * n_comp], dtype=float).reshape(rows, n_comp)
        i += rows * n_comp
    return out


def read_csv(path):
    """Hydrographs in .csv format (global file: "2 <interval> file.csv").

    Layout: a header line "Link <id> , , ," per link, a line of output names, then one row per
    output time with the components of every link side by side.
    Returns {link id: array [rows, components]}.
    """
    with open(path) as f:
        head = f.readline().split(",")
        f.readline()
        rows = [[float(c) for c in line.split(",") if c.strip()] for line in f if line.strip()]
    links = [int(h.split()[1]) for h in head if h.strip().startswith("Link")]
    data = np.array(rows)
    n_comp = data.shape[1] // len(links)
    return {link: data[:, k * n_comp:(k + 1) * n_comp] for k, link in enumerate(links)}


def read_pea(path):
    """Peak flows in .pea format ("Classic" peakflow function).

    Layout: number of links, model id, then per link: "<id> <upstream area [km2]>
    <time of peak [min]> <peak discharge [m3/s]>".
    Returns {link id: (area, time_of_peak, peak_value)}.
    """
    lines = [l.split() for l in open(path) if l.strip()]
    return {int(p[0]): tuple(float(x) for x in p[1:4]) for p in lines[2:]}


def read_rec(path):
    """Snapshot (all states of all links at one time) in .rec format.

    Layout: model id, number of links, time, then per link a line with its id and a line with
    its states. Returns {link id: array of states}.
    """
    lines = [l.split() for l in open(path) if l.strip()]
    out = {}
    for k in range(3, len(lines) - 1, 2):
        out[int(lines[k][0])] = np.array(lines[k + 1], dtype=float)
    return out


def read_h5_snapshot(path):
    """Snapshot in .h5 format (global file snapshot flag 3 or 4). Returns {link id: array of states}."""
    import h5py
    with h5py.File(path, "r") as f:
        data = f["snapshot"][:]
    cols = [c for c in data.dtype.names if c != "link_id"]
    return {int(r["link_id"]): np.array([r[c] for c in cols]) for r in data}


def read_h5_hydrographs(path):
    """Hydrographs in .h5 format, packet (flag 5) or array (flag 6) layout.

    Returns {link id: array [rows, components]}. For the array layout, the first column is the
    time (unix time) and the others are the printed components.
    """
    import h5py
    with h5py.File(path, "r") as f:
        if "link_id" in f:                                     # array layout (flag 6)
            ids, times, outs = f["link_id"][:], f["time"][:], f["outputs"][:]
            return {int(l): np.column_stack([times, outs[i]]) for i, l in enumerate(ids)}
        data = f["outputs"][:]                                 # packet layout (flag 5)
    names = [n for n in data.dtype.names if n != "LinkID"]
    out = {}
    for link in np.unique(data["LinkID"]):
        rows = data[data["LinkID"] == link]
        out[int(link)] = np.column_stack([rows[n].astype(float) for n in names])
    return out
