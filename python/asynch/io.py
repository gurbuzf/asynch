"""
Read ASYNCH output files and write ASYNCH input files.

Readers (outputs of a run) return a dictionary keyed by link id::

    from asynch import io
    hydro = io.read_hydrographs("examples/out_2015/clearcreek.dat")   # .dat, .csv or .h5
    t, q = hydro[2527][:, 0], hydro[2527][:, 1]
    peaks = io.read_pea("examples/out_2015/test.pea")                 # {link: (area, time, peak)}
    state = io.read_snapshot("examples/out_2015/test.rec")            # .rec or .h5

The meaning of the hydrograph columns depends on the "%Components to print" block of the global file.

Writers (inputs of a run) create the text formats of docs/input_output.rst from Python data::

    io.write_rvr("net.rvr", {1: [2, 3], 2: [], 3: []})               # link -> upstream links
    io.write_prm("net.prm", {1: [1.2, 0.5, 0.1], 2: [...], 3: [...]})  # link -> parameters
    io.write_uini("net.uini", 190, [1e-6, 0.0, 0.0])
    io.write_ustr("rain.ustr", [(0, 20.0), (60, 0.0)])                # (minute, value)

Only NumPy is needed, plus h5py for the .h5 files.
"""
import os

import numpy as np



def read_dat(path):
    """Hydrographs in .dat format (global file: "1 <interval> file.dat").

    Layout: number of links, number of printed components, then for every link:
    "<link id> <number of rows>" followed by that many rows of components.
    Returns {link id: array [rows, components]}.
    """
    with open(path) as f:
        tok = f.read().split()
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
    with open(path) as f:
        lines = [l.split() for l in f if l.strip()]
    return {int(p[0]): tuple(float(x) for x in p[1:4]) for p in lines[2:]}


def read_rec(path):
    """Snapshot (all states of all links at one time) in .rec format.

    Layout: model id, number of links, time, then per link a line with its id and a line with
    its states. Returns {link id: array of states}.
    """
    with open(path) as f:
        lines = [l.split() for l in f if l.strip()]
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


# ---------------------------------------------------------------------------------------------------
# Readers chosen by file extension
# ---------------------------------------------------------------------------------------------------


def read_hydrographs(path):
    """Hydrographs from a .dat, .csv or .h5 file. Returns {link id: array [rows, components]}."""
    ext = os.path.splitext(path)[1]
    if ext == ".dat":
        return read_dat(path)
    if ext == ".csv":
        return read_csv(path)
    if ext == ".h5":
        return read_h5_hydrographs(path)
    raise ValueError("unknown hydrograph format: %s" % path)


def read_snapshot(path):
    """Snapshot from a .rec or .h5 file. Returns {link id: array of states}."""
    ext = os.path.splitext(path)[1]
    if ext == ".rec":
        return read_rec(path)
    if ext == ".h5":
        return read_h5_snapshot(path)
    raise ValueError("unknown snapshot format: %s" % path)


# ---------------------------------------------------------------------------------------------------
# Writers of input files
# ---------------------------------------------------------------------------------------------------

def _num(x):
    return repr(float(x))


def write_rvr(path, parents):
    """Topology (.rvr). parents: {link id: list of upstream link ids}, in the order to write."""
    with open(path, "w") as f:
        f.write("%d\n\n" % len(parents))
        for link, ups in parents.items():
            ups = list(ups)
            f.write("%d\n%d%s\n\n" % (link, len(ups), "".join(" %d" % u for u in ups)))
    return path


def write_prm(path, params):
    """Link parameters (.prm). params: {link id: sequence of the parameters read from disk}."""
    with open(path, "w") as f:
        f.write("%d\n\n" % len(params))
        for link, values in params.items():
            f.write("%d\n%s\n\n" % (link, " ".join(_num(v) for v in values)))
    return path


def write_uini(path, model, values, time=0.0):
    """Initial state, the same at every link (.uini)."""
    with open(path, "w") as f:
        f.write("%d\n%s\n\n%s\n" % (model, _num(time), " ".join(_num(v) for v in values)))
    return path


def write_ini(path, model, states, time=0.0):
    """Initial state per link (.ini); states: {link id: values read from file}.
    The .rec format is the same with every state of every link (write_rec)."""
    with open(path, "w") as f:
        f.write("%d\n%d\n%s\n\n" % (model, len(states), _num(time)))
        for link, values in states.items():
            f.write("%d\n%s\n\n" % (link, " ".join(_num(v) for v in values)))
    return path


write_rec = write_ini


def write_str(path, series):
    """Forcing per link (.str); series: {link id: [(time [min], value), ...]} (constant between times)."""
    with open(path, "w") as f:
        f.write("%d\n\n" % len(series))
        for link, points in series.items():
            points = list(points)
            f.write("%d %d\n" % (link, len(points)))
            for t, v in points:
                f.write("%s %s\n" % (_num(t), _num(v)))
            f.write("\n")
    return path


def write_ustr(path, points):
    """Forcing uniform in space (.ustr); points: [(time [min], value), ...] (constant between times)."""
    points = list(points)
    with open(path, "w") as f:
        f.write("%d\n" % len(points))
        for t, v in points:
            f.write("%s %s\n" % (_num(t), _num(v)))
    return path


def write_mon(path, values):
    """Monthly recurring forcing (.mon): 12 values, January first."""
    values = list(values)
    if len(values) != 12:
        raise ValueError("a .mon file needs 12 values, got %d" % len(values))
    with open(path, "w") as f:
        f.write("".join("%s\n" % _num(v) for v in values))
    return path


def write_sav(path, links):
    """List of links to write outputs for (.sav)."""
    with open(path, "w") as f:
        f.write("".join("%d\n" % l for l in links))
    return path


def read_rvr(path):
    """Topology (.rvr). Returns {link id: list of upstream link ids}, in file order."""
    with open(path) as f:
        tok = f.read().split()
    n, i, out = int(tok[0]), 1, {}
    for _ in range(n):
        link, k = int(tok[i]), int(tok[i + 1])
        out[link] = [int(x) for x in tok[i + 2:i + 2 + k]]
        i += 2 + k
    return out


def read_prm(path):
    """Link parameters (.prm). Returns {link id: array of parameters}. The number of parameters per
    link is found from the file (all links have the same number)."""
    with open(path) as f:
        lines = [l.split() for l in f if l.strip()]
    n = int(lines[0][0])
    out = {}
    k = 1
    for _ in range(n):
        link = int(lines[k][0])
        values = lines[k][1:]
        k += 1
        if not values:                      # parameters on the next line
            values = lines[k]
            k += 1
        out[link] = np.array(values, dtype=float)
    return out
