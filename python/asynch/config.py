"""
Read, change and write ASYNCH global files (``.gbl``) from Python.

A global file is read by ``Read_Global_Data`` (``src/config_gbl.c``) one value line after the other;
lines starting with ``%`` and empty lines are comments. :class:`GlobalConfig` follows that reader
field by field, so ``GlobalConfig.read(path).write(other)`` gives a file that ASYNCH reads exactly
as the original (the comments are not kept).

Example::

    from asynch.config import GlobalConfig, Forcing

    cfg = GlobalConfig.read("examples/test_2015.gbl")
    cfg.end = "2014-05-01 10:00"
    cfg.global_params[3] = 0.5                     # runoff coefficient RC of model 190
    cfg.hydrographs.path = "out/test_rc05.dat"
    cfg.write("examples/test_rc05.gbl")

Paths inside a global file are relative to the folder ASYNCH runs in, not to the file.
"""
import copy
import datetime as _dt

# ---------------------------------------------------------------------------------------------------
# Blocks with a flag and optional fields
# ---------------------------------------------------------------------------------------------------


class Forcing:
    """One forcing (rain, evaporation, ...). The flag selects the source, as in the global file:

    ====  =====================================  =============================================
    flag  source                                  fields used
    ====  =====================================  =============================================
    0     none                                    -
    1     .str file (per link time series)        path
    2     binary files, one per time step         path, increment, file_time, first, last
    3     database                                path (.dbc), increment, file_time, first, last
    4     .ustr file (same rain everywhere)       path
    5     irregular binary files                  path, increment, file_time, first, last
    6     gzipped binary files                    path, increment, file_time, first, last
    7     .mon file (monthly recurring values)    path, first, last
    8     grid cells                              path, increment, first, last
    9     database, irregular time steps          path (.dbc), increment, first, last
    ====  =====================================  =============================================
    """

    def __init__(self, flag=0, path=None, increment=None, file_time=None, first=None, last=None):
        self.flag = int(flag)
        self.path = path
        self.increment = increment
        self.file_time = file_time
        self.first = first
        self.last = last

    # common cases
    @classmethod
    def none(cls):
        return cls(0)

    @classmethod
    def storm_file(cls, path):
        """A .str file: a time series of values for every link."""
        return cls(1, path)

    @classmethod
    def uniform(cls, path):
        """A .ustr file: one time series applied to every link."""
        return cls(4, path)

    @classmethod
    def monthly(cls, path, first, last):
        """A .mon file of 12 monthly values, used between the unix times first and last."""
        return cls(7, path, first=first, last=last)

    def lines(self):
        f = self.flag
        if f == 0:
            return ["0"]
        if f in (1, 4):
            return ["%d %s" % (f, self.path)]
        if f in (2, 3, 5, 6):
            return ["%d %s" % (f, self.path),
                    "%s %s %s %s" % (self.increment, _num(self.file_time), self.first, self.last)]
        if f in (8, 9):
            return ["%d %s" % (f, self.path), "%s %s %s" % (self.increment, self.first, self.last)]
        if f == 7:
            return ["7 %s" % self.path, "%s %s" % (self.first, self.last)]
        raise ValueError("invalid forcing flag %r" % f)

    def __repr__(self):
        return "Forcing(%s)" % ", ".join("%s=%r" % kv for kv in vars(self).items() if kv[1] is not None)

    def __eq__(self, other):
        return isinstance(other, Forcing) and vars(self) == vars(other)


class Output:
    """Hydrograph (time series) output.

    flag: 0 none, 1 .dat, 2 .csv, 3 database (path is a .dbc, table needed), 4 .rad,
    5 .h5 (packet), 6 .h5 (array). interval: minutes between written values.
    """

    def __init__(self, flag=0, interval=None, path=None, table=None):
        self.flag = int(flag)
        self.interval = interval
        self.path = path
        self.table = table

    def lines(self):
        if self.flag == 0:
            return ["0"]
        if self.flag == 3:
            return ["3 %s %s %s" % (_num(self.interval), self.path, self.table)]
        return ["%d %s %s" % (self.flag, _num(self.interval), self.path)]

    def __repr__(self):
        return "Output(%s)" % ", ".join("%s=%r" % kv for kv in vars(self).items() if kv[1] is not None)

    def __eq__(self, other):
        return type(self) is type(other) and vars(self) == vars(other)


class PeakOutput(Output):
    """Peak flow output. flag: 0 none, 1 .pea file, 2 database (path is a .dbc, table needed)."""

    def __init__(self, flag=0, path=None, table=None):
        Output.__init__(self, flag, None, path, table)

    def lines(self):
        if self.flag == 0:
            return ["0"]
        if self.flag == 2:
            return ["2 %s %s" % (self.path, self.table)]
        return ["%d %s" % (self.flag, self.path)]


class Snapshot(Output):
    """Final state output. flag: 0 none, 1 .rec, 2 database (.dbc + table), 3 .h5,
    4 .h5 every `interval` minutes (the path gets the time appended)."""

    def lines(self):
        if self.flag == 0:
            return ["0"]
        if self.flag == 2:
            return ["2 %s %s" % (self.path, self.table)]
        if self.flag == 4:
            return ["4 %s %s" % (_num(self.interval), self.path)]
        return ["%d %s" % (self.flag, self.path)]


class Selection:
    """Links written to an output. flag: 0 none, 1 .sav file, 2 database (.dbc), 3 all links."""

    def __init__(self, flag=0, path=None):
        self.flag = int(flag)
        self.path = path

    def lines(self):
        return ["%d %s" % (self.flag, self.path)] if self.flag in (1, 2) else ["%d" % self.flag]

    def __repr__(self):
        return "Selection(flag=%d%s)" % (self.flag, ", path=%r" % self.path if self.path else "")

    def __eq__(self, other):
        return isinstance(other, Selection) and vars(self) == vars(other)


class FileRef:
    """A block made of a flag and a path (topology, parameters, initial state, dams).
    `extra` holds what follows the path on the same line (e.g. the timestamp of a .dbc initial state)."""

    def __init__(self, flag=0, path=None, extra=None):
        self.flag = int(flag)
        self.path = path
        self.extra = extra

    def lines(self):
        parts = [str(self.flag)]
        if self.path is not None:
            parts.append(str(self.path))
        if self.extra is not None:
            parts.append(str(self.extra))
        return [" ".join(parts)]

    def __repr__(self):
        return "FileRef(%s)" % ", ".join("%s=%r" % kv for kv in vars(self).items() if kv[1] is not None)

    def __eq__(self, other):
        return isinstance(other, FileRef) and vars(self) == vars(other)


def _num(x):
    """Numbers as written by a person: 5.0 -> '5.0', 1e-06 -> '1e-06'."""
    if x is None:
        return ""
    if isinstance(x, float):
        return repr(x)
    return str(x)


def _time(x):
    """Begin/end times: 'YYYY-MM-DD HH:MM', a datetime, or a unix time (int)."""
    if isinstance(x, _dt.datetime):
        return x.strftime("%Y-%m-%d %H:%M")
    return str(x)


# ---------------------------------------------------------------------------------------------------
# The global file
# ---------------------------------------------------------------------------------------------------


class GlobalConfig:
    """Every setting of a global file. Attributes, in file order:

    model (int), begin, end (``"YYYY-MM-DD HH:MM"``, datetime or unix time), parameters_in_filenames (0/1),
    outputs (list of names, e.g. ``["Time", "State0"]``), peakflow_function (``"Classic"``),
    global_params (list of floats), steps_stored, steps_transferred, discontinuity_buffer (ints),
    topology, parameters, initial_state (:class:`FileRef`), forcings (list of :class:`Forcing`),
    dams (:class:`FileRef`, flag 0 none, 1 .dam, 2 .qvs, 3 .dbc), reservoirs (:class:`FileRef`, flag 0/1/2,
    `extra` = index of the forcing that feeds them), hydrographs (:class:`Output`), peaks (:class:`PeakOutput`),
    hydrograph_links, peak_links (:class:`Selection`), snapshot (:class:`Snapshot`), scratch (str),
    facmin, facmax, fac (floats), rkd (path of a .rkd file, or None), solver (0, 1 or 2),
    abstol, reltol, abstol_dense, reltol_dense (lists of floats, one per state).
    """

    def __init__(self, **kw):
        self.model = 190
        self.begin = "2017-01-01 00:00"
        self.end = "2017-01-02 00:00"
        self.parameters_in_filenames = 0
        self.outputs = ["Time", "State0"]
        self.peakflow_function = "Classic"
        self.global_params = []
        self.steps_stored = 30
        self.steps_transferred = 10
        self.discontinuity_buffer = 30
        self.topology = FileRef(0, None)
        self.parameters = FileRef(0, None)
        self.initial_state = FileRef(1, None)
        self.forcings = []
        self.dams = FileRef(0)
        self.reservoirs = FileRef(0)
        self.hydrographs = Output(0)
        self.peaks = PeakOutput(0)
        self.hydrograph_links = Selection(0)
        self.peak_links = Selection(0)
        self.snapshot = Snapshot(0)
        self.scratch = "tmp"
        self.facmin, self.facmax, self.fac = 0.1, 10.0, 0.9
        self.rkd = None
        self.solver = 2
        self.abstol = [1e-3]
        self.reltol = [1e-6]
        self.abstol_dense = [1e-3]
        self.reltol_dense = [1e-6]
        for key, value in kw.items():
            if not hasattr(self, key):
                raise TypeError("GlobalConfig has no setting %r" % key)
            setattr(self, key, value)

    def copy(self):
        return copy.deepcopy(self)

    # -- writing --------------------------------------------------------------------------------------

    def text(self):
        """The content of the global file."""
        out = []

        def block(comment, *lines):
            out.append("%" + comment)
            out.extend(lines)
            out.append("")

        def tol(values):
            return " ".join(_num(float(v)) for v in values)

        block("Model UID", str(self.model))
        block("Begin and end date time", _time(self.begin), _time(self.end))
        block("Parameters to filenames", str(self.parameters_in_filenames))
        block("Components to print", str(len(self.outputs)), *self.outputs)
        block("Peakflow function", self.peakflow_function)
        block("Global parameters",
              " ".join([str(len(self.global_params))] + [_num(float(v)) for v in self.global_params]))
        block("No. steps stored at each link, max no. steps transferred between procs, discontinuity buffer size",
              "%d %d %d" % (self.steps_stored, self.steps_transferred, self.discontinuity_buffer))
        block("Topology (0 = .rvr, 1 = database)", *self.topology.lines())
        block("DEM Parameters (0 = .prm, 1 = database)", *self.parameters.lines())
        block("Initial state (0 = .ini, 1 = .uini, 2 = .rec, 3 = .dbc, 4 = .h5)", *self.initial_state.lines())
        lines = [str(len(self.forcings))]
        block("Forcings (0 = none, 1 = .str, 2 = binary, 3 = database, 4 = .ustr, 5 = forecasting, "
              "6 = .gz binary, 7 = recurring)", *lines)
        for i, forcing in enumerate(self.forcings):
            block("Forcing %d" % i, *forcing.lines())
        block("Dam (0 = no dam, 1 = .dam, 2 = .qvs)", *self.dams.lines())
        block("Reservoir ids (0 = no reservoirs, 1 = .rsv, 2 = .dbc file)", *self.reservoirs.lines())
        block("Where to put write hydrographs (0 = no output, 1 = .dat file, 2 = .csv file, 3 = database, "
              "5 = .h5 packet, 6 = .h5 array)", *self.hydrographs.lines())
        block("Where to put peakflow data (0 = no output, 1 = .pea file, 2 = database)", *self.peaks.lines())
        block(".sav files for hydrographs and peak file (0 = save no data, 1 = .sav file, 2 = .dbc file, "
              "3 = all links)", *(self.hydrograph_links.lines() + self.peak_links.lines()))
        block("Snapshot information (0 = none, 1 = .rec, 2 = database, 3 = .h5, 4 = recurrent .h5)",
              *self.snapshot.lines())
        block("Filename for scratch work", self.scratch)
        block("Numerical solver settings follow")
        block("facmin, facmax, fac", "%s %s %s" % (_num(self.facmin), _num(self.facmax), _num(self.fac)))
        if self.rkd:
            block("Solver flag (0 = data below, 1 = .rkd)", "1 %s" % self.rkd)
        else:
            block("Solver flag (0 = data below, 1 = .rkd)", "0")
            block("Numerical solver index (0 = RK 3(2), 1 = RK 4(3), 2 = Dormand-Prince 5(4))", str(self.solver))
            block("Error tolerances (abs, rel, abs dense, rel dense)",
                  tol(self.abstol), tol(self.reltol), tol(self.abstol_dense), tol(self.reltol_dense))
        out.append("# %End of file")
        return "\n".join(out) + "\n"

    def write(self, path):
        """Write the global file to path; returns path."""
        with open(path, "w") as f:
            f.write(self.text())
        return path

    # -- reading --------------------------------------------------------------------------------------

    @classmethod
    def read(cls, path):
        """Read a global file (the same way as src/config_gbl.c)."""
        with open(path) as f:
            return cls.parse(f.read())

    @classmethod
    def parse(cls, text):
        lines = _ValueLines(text)
        c = cls()
        c.model = int(lines.next_words()[0])
        c.begin = _parse_time(lines.next_line())
        c.end = _parse_time(lines.next_line())
        c.parameters_in_filenames = int(lines.next_words()[0])
        n = int(lines.next_words()[0])
        c.outputs = [lines.next_words()[0] for _ in range(n)]
        c.peakflow_function = lines.next_words()[0]
        w = lines.next_words()
        n = int(w[0])
        c.global_params = [float(v) for v in w[1:1 + n]]
        if len(c.global_params) < n:
            raise ValueError("global parameters: %d announced, %d given" % (n, len(c.global_params)))
        w = lines.next_words()
        c.steps_stored, c.steps_transferred, c.discontinuity_buffer = int(w[0]), int(w[1]), int(w[2])
        c.topology = _fileref(lines.next_words())
        c.parameters = _fileref(lines.next_words())
        c.initial_state = _fileref(lines.next_words())
        n = int(lines.next_words()[0])
        c.forcings = []
        for _ in range(n):
            w = lines.next_words()
            flag = int(w[0])
            fc = Forcing(flag, w[1] if len(w) > 1 and flag != 0 else None)
            if flag in (2, 3, 5, 6):
                v = lines.next_words()
                fc.increment, fc.file_time, fc.first, fc.last = int(v[0]), _float(v[1]), int(v[2]), int(v[3])
            elif flag in (8, 9):
                v = lines.next_words()
                fc.increment, fc.first, fc.last = int(v[0]), int(v[1]), int(v[2])
            elif flag == 7:
                v = lines.next_words()
                fc.first, fc.last = int(v[0]), int(v[1])
            elif flag not in (0, 1, 4):
                raise ValueError("invalid forcing flag %d" % flag)
            c.forcings.append(fc)
        c.dams = _fileref(lines.next_words())
        c.reservoirs = _fileref(lines.next_words())
        w = lines.next_words()
        flag = int(w[0])
        if flag == 0:
            c.hydrographs = Output(0)
        elif flag == 3:
            c.hydrographs = Output(3, _float(w[1]), w[2], w[3])
        else:
            c.hydrographs = Output(flag, _float(w[1]), w[2])
        w = lines.next_words()
        flag = int(w[0])
        c.peaks = PeakOutput(flag, w[1] if flag else None, w[2] if flag == 2 else None)
        w = lines.next_words()
        c.hydrograph_links = Selection(int(w[0]), w[1] if int(w[0]) in (1, 2) else None)
        w = lines.next_words()
        c.peak_links = Selection(int(w[0]), w[1] if int(w[0]) in (1, 2) else None)
        w = lines.next_words()
        flag = int(w[0])
        if flag in (1, 3):
            c.snapshot = Snapshot(flag, None, w[1])
        elif flag == 2:
            c.snapshot = Snapshot(2, None, w[1], w[2])
        elif flag == 4:
            c.snapshot = Snapshot(4, _float(w[1]), w[2])
        else:
            c.snapshot = Snapshot(0)
        c.scratch = lines.next_words()[0]
        w = lines.next_words()
        c.facmin, c.facmax, c.fac = _float(w[0]), _float(w[1]), _float(w[2])
        w = lines.next_words()
        if int(w[0]) == 1:
            c.rkd = w[1]
        else:
            c.rkd = None
            c.solver = int(lines.next_words()[0])
            c.abstol = [float(v) for v in _numbers(lines.next_words())]
            n = len(c.abstol)
            c.reltol = [float(v) for v in _numbers(lines.next_words())][:n]
            c.abstol_dense = [float(v) for v in _numbers(lines.next_words())][:n]
            c.reltol_dense = [float(v) for v in _numbers(lines.next_words())][:n]
        end = lines.next_line()
        if not end.startswith("#"):
            raise ValueError("the global file does not end with a line starting with '#'")
        return c

    def __eq__(self, other):
        return isinstance(other, GlobalConfig) and vars(self) == vars(other)

    def __repr__(self):
        return "GlobalConfig(model=%r, begin=%r, end=%r, ...)" % (self.model, self.begin, self.end)


class _ValueLines:
    """The non-comment lines of a global file, as ReadLineFromTextFile returns them."""

    def __init__(self, text):
        self._lines = [l for l in text.splitlines() if l.strip() and not l.startswith("%")]
        self._i = 0

    def next_line(self):
        if self._i >= len(self._lines):
            raise ValueError("the global file ends too early (line %d of values)" % (self._i + 1))
        line = self._lines[self._i]
        self._i += 1
        return line

    def next_words(self):
        # text after a % on a value line is a comment (e.g. "1 test.sav %Hydrographs")
        return self.next_line().split("%")[0].split()


def _numbers(words):
    out = []
    for w in words:
        try:
            out.append(float(w))
        except ValueError:
            break
    return out


def _float(s):
    return float(s)


def _fileref(words):
    flag = int(words[0])
    path = words[1] if len(words) > 1 else None
    extra = " ".join(words[2:]) if len(words) > 2 else None
    return FileRef(flag, path, extra)


def _parse_time(line):
    s = line.split("%")[0].strip()
    parts = s.split()
    if len(parts) >= 2 and "-" in parts[0]:
        return "%s %s" % (parts[0], parts[1])
    return int(parts[0])
