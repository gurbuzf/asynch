"""
The :class:`Simulation` class: run ASYNCH from Python and work with its states and parameters.

Run a global file exactly as the ``asynch`` program does (same output files)::

    from asynch import Simulation
    with Simulation("test_2015.gbl") as sim:
        sim.run()

Work with the model between runs::

    with Simulation("test_2015.gbl") as sim:
        sim.advance(60)                        # the first hour
        q = sim.states[:, 0]                   # discharge of every link (location order)
        sim.global_params = [0.33, 0.2, -0.1, 0.5, 0.1, 2.2917e-5]   # change RC after one hour
        sim.run()                              # the rest, then write the outputs

With MPI (``mpirun -np 4 python3 script.py``), every process runs the same script; each process
computes a part of the network. Methods marked *collective* must be called by every process.
"""
import ctypes
import os
import tempfile

import numpy as np

from . import _lib
from .config import GlobalConfig


class AsynchError(Exception):
    """An error detected before it reaches the C library (where most errors stop every process)."""


_FILE_INPUTS = {"topology": (0,), "parameters": (0,), "initial_state": (0, 1, 2, 4)}


class Simulation:
    """An ASYNCH solver.

    Parameters
    ----------
    global_file : str or GlobalConfig, optional
        The global file (.gbl) to read, or a :class:`~asynch.config.GlobalConfig`.
    model : asynch.model.Model, optional
        A model defined in Python; replaces the model number of the global file.
    comm : mpi4py.MPI.Comm, optional
        Communicator (only MPI_COMM_WORLD is fully supported by ASYNCH). Default: every process.
    verbose : bool
        Print the progress messages of the C library.
    load : bool
        Load everything (network, parameters, initial states, forcings, outputs) right away.
        Use ``load=False`` to register custom outputs (:meth:`set_output`) first, then call :meth:`load`.

    Notes
    -----
    The steps of :meth:`load` can also be called one by one, as in ``src/asynch_cli.c``.
    """

    def __init__(self, global_file=None, model=None, comm=None, verbose=False, load=True):
        self._L = _lib.lib()
        self._ptr = None
        self._spec = None
        self._outputs = {}           # name -> ctypes callback (kept alive)
        self._closed = False
        self._loaded = False
        self._outputs_ready = False
        self.config = None
        self.model = model

        if comm is None:
            _lib.mpi_init()
            self._ptr = self._L.Asynch_Init_World(bool(verbose))
        else:
            self._ptr = self._L.Asynch_Init_Fortran_Comm(comm.py2f(), bool(verbose))
        if not self._ptr:
            raise AsynchError("Asynch_Init failed")

        if model is not None:
            self._spec = model.build_spec()
            if self._L.Asynch_Install_Model(self._ptr, self._spec):
                raise AsynchError("could not install model %r" % model.name)

        if global_file is not None:
            self.read_global_file(global_file)
            if load:
                self.load()

    # -- life cycle -----------------------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def close(self):
        """Delete the temporary files and free the solver. The simulation cannot be used afterwards."""
        if self._closed or self._ptr is None:
            return
        self._closed = True
        if self._outputs_ready:
            self._L.Asynch_Delete_Temporary_Files(self._ptr)
        self._L.Asynch_Free(self._ptr)
        self._ptr = None
        if self._spec is not None:
            self._L.Asynch_Model_Spec_Free(self._spec)
            self._spec = None

    def _check_open(self):
        if self._closed or self._ptr is None:
            raise AsynchError("the simulation is closed")

    @property
    def rank(self):
        """Rank of this process (0 on a single process)."""
        return self._L.Asynch_Get_Rank(self._ptr)

    @property
    def num_procs(self):
        return self._L.Asynch_Get_Num_Procs(self._ptr)

    # -- reading the global file ----------------------------------------------------------------------

    def read_global_file(self, global_file):
        """Read a global file (path or GlobalConfig). Checks what would otherwise stop the program."""
        self._check_open()
        if isinstance(global_file, GlobalConfig):
            config = global_file
            fd, path = tempfile.mkstemp(suffix=".gbl", prefix="asynch_")
            with os.fdopen(fd, "w") as f:
                f.write(config.text())
            self._tmp_gbl = path
        else:
            path = os.fspath(global_file)
            if not os.path.isfile(path):
                raise FileNotFoundError("global file not found: %s" % path)
            try:
                config = GlobalConfig.read(path)
            except (ValueError, IndexError) as e:
                raise AsynchError("cannot read %s: %s" % (path, e)) from e
        self._precheck(config)
        self.config = config
        self._L.Asynch_Parse_GBL(self._ptr, path.encode())
        if isinstance(global_file, GlobalConfig):
            os.unlink(path)

    def _precheck(self, c):
        """Report in Python the problems for which the C library would abort every process."""
        missing = []
        for name, flags in _FILE_INPUTS.items():
            ref = getattr(c, name)
            if ref.flag in flags and ref.path and not os.path.isfile(ref.path):
                missing.append("%s file %s" % (name.replace("_", " "), ref.path))
        for i, f in enumerate(c.forcings):
            if f.flag in (1, 4, 7) and not os.path.isfile(f.path):
                missing.append("forcing %d file %s" % (i, f.path))
            elif f.flag in (2, 6) and f.first is not None and f.last is not None:
                # one file per index, first to last (C stops every process if one is missing)
                ext = ".gz" if f.flag == 6 else ""
                absent = [n for n in range(int(f.first), int(f.last) + 1)
                          if not os.path.isfile("%s%d%s" % (f.path, n, ext))]
                if absent:
                    missing.append("forcing %d files %s<index>%s for index %s" % (
                        i, f.path, ext, ", ".join(map(str, absent[:5])) + (", ..." if len(absent) > 5 else "")))
        for sel, what in ((c.hydrograph_links, "hydrograph links"), (c.peak_links, "peak links")):
            if sel.flag == 1 and not os.path.isfile(sel.path):
                missing.append("%s file %s" % (what, sel.path))
        if c.rkd and not os.path.isfile(c.rkd):
            missing.append(".rkd file %s" % c.rkd)
        if missing:
            raise FileNotFoundError("the global file refers to missing files: " + "; ".join(missing))
        for out, what in ((c.hydrographs, "hydrographs"), (c.peaks, "peak flows"), (c.snapshot, "snapshot")):
            if out.flag and out.path and not (out.flag in (2, 3) and out.path.endswith(".dbc")):
                folder = os.path.dirname(out.path) or "."
                if not os.path.isdir(folder):
                    raise FileNotFoundError("the folder for the %s output does not exist: %s" % (what, folder))
        if self.model is not None:
            m = self.model
            if len(c.global_params) < len(m.global_params):
                raise AsynchError("model %r needs %d global parameters, the global file gives %d"
                                  % (m.name, len(m.global_params), len(c.global_params)))
            if len(c.forcings) < len(m.forcings):
                raise AsynchError("model %r needs %d forcings, the global file gives %d"
                                  % (m.name, len(m.forcings), len(c.forcings)))
            if not c.rkd and len(c.abstol) < (m.min_error_tolerances or len(m.states)):
                raise AsynchError("model %r has %d states: give that many error tolerances in the global file"
                                  % (m.name, len(m.states)))

    # -- loading --------------------------------------------------------------------------------------

    def load(self, prepare_outputs=True):
        """Load the network, parameters, initial states and forcings (collective), then prepare the
        outputs of the global file (unless prepare_outputs is False)."""
        self._check_open()
        if self.config is None:
            raise AsynchError("read a global file first")
        L, p = self._L, self._ptr
        L.Asynch_Load_Network(p)
        L.Asynch_Partition_Network(p)
        L.Asynch_Load_Network_Parameters(p)
        L.Asynch_Load_Dams(p)
        L.Asynch_Load_Numerical_Error_Data(p)
        L.Asynch_Initialize_Model(p)
        L.Asynch_Load_Initial_Conditions(p)
        L.Asynch_Load_Forcings(p)
        L.Asynch_Load_Save_Lists(p)
        L.Asynch_Finalize_Network(p)
        L.Asynch_Calculate_Step_Sizes(p)
        self._loaded = True
        self._raise_model_error()
        if prepare_outputs:
            self.prepare_outputs()

    def prepare_outputs(self):
        """Open the temporary files for the hydrographs and prepare the peak and hydrograph outputs
        (as asynch_cli.c). Checks first that every output of the global file is defined."""
        self._check_loaded()
        undefined = [n for n in self.config.outputs if self._L.Asynch_Check_Output(self._ptr, n.encode()) != 1]
        if undefined:
            raise AsynchError("outputs %s of the global file are not defined: use Simulation.set_output "
                              "before load()" % ", ".join(undefined))
        if self.config.peakflow_function not in ("Classic", "Forecast") and \
                self._L.Asynch_Check_Peakflow_Output(self._ptr, self.config.peakflow_function.encode()) != 1:
            raise AsynchError("peakflow function %s is not defined: use Simulation.set_peakflow_output"
                              % self.config.peakflow_function)
        L, p = self._L, self._ptr
        L.Asynch_Prepare_Temp_Files(p)
        L.Asynch_Write_Current_Step(p)
        L.Asynch_Prepare_Peakflow_Output(p)
        L.Asynch_Prepare_Output(p)
        self._outputs_ready = True

    def _check_loaded(self):
        self._check_open()
        if not self._loaded:
            raise AsynchError("the simulation is not loaded (call load())")

    def _raise_model_error(self):
        if self.model is not None:
            self.model.raise_pending_error()

    # -- running --------------------------------------------------------------------------------------

    def advance(self, minutes=None, until=None, write=True):
        """Integrate for `minutes` more, or until the time `until` [minutes since the start], or to the end
        of the simulation period (collective). Hydrographs are written to the temporary files if `write`."""
        self._check_loaded()
        end = self.duration_total
        if minutes is not None:
            target = self.time + float(minutes)
        elif until is not None:
            target = float(until)
        else:
            target = end
        if target < self.time:
            raise AsynchError("cannot go back in time (now %g, asked %g)" % (self.time, target))
        if target != end:
            self._L.Asynch_Set_Total_Simulation_Duration(self._ptr, target)
        self._L.Asynch_Advance(self._ptr, 1 if (write and self._outputs_ready) else 0)
        if target != end:
            self._L.Asynch_Set_Total_Simulation_Duration(self._ptr, end)
        self._raise_model_error()
        return self.time

    def run(self, write_outputs=True):
        """Integrate to the end of the period, then write the snapshot, hydrograph and peak flow outputs of
        the global file (collective). Same results and files as the asynch program."""
        self.advance()
        if write_outputs:
            self.write_outputs()

    def write_outputs(self, suffix=None):
        """Write the snapshot, the hydrographs and the peak flows (collective). Raises if a file could not
        be written. `suffix` is appended to the hydrograph file name."""
        self._check_loaded()
        L, p = self._L, self._ptr
        errors = []
        if L.Asynch_Take_System_Snapshot(p, None) > 0:
            errors.append("snapshot")
        if self._outputs_ready:
            if L.Asynch_Create_Output(p, suffix.encode() if suffix else None) > 0:
                errors.append("hydrographs")
            if L.Asynch_Create_Peakflows_Output(p) > 0:
                errors.append("peak flows")
        if errors:
            raise AsynchError("could not write: " + ", ".join(errors))

    def snapshot(self, path=None):
        """Write a snapshot of the current states (collective); to `path` if given (.rec or .h5, as the
        snapshot type of the global file), else to the file of the global file."""
        self._check_loaded()
        if path is not None:
            old = self.snapshot_path
            if self._L.Asynch_Set_Snapshot_Output_Name(self._ptr, os.fspath(path).encode()):
                raise AsynchError("snapshot path too long")
        ret = self._L.Asynch_Take_System_Snapshot(self._ptr, None)
        if path is not None and old is not None:
            self._L.Asynch_Set_Snapshot_Output_Name(self._ptr, old.encode())
        if ret < 0:
            raise AsynchError("the global file has no snapshot output")
        if ret > 0:
            raise AsynchError("the snapshot could not be written")

    # -- time -----------------------------------------------------------------------------------------

    @property
    def time(self):
        """Current time [minutes since the start]."""
        return self._L.Asynch_Get_Current_Time(self._ptr)

    @property
    def duration_total(self):
        """Length of the simulation period [minutes]."""
        return self._L.Asynch_Get_Total_Simulation_Duration(self._ptr)

    @duration_total.setter
    def duration_total(self, minutes):
        self._L.Asynch_Set_Total_Simulation_Duration(self._ptr, float(minutes))

    @property
    def begin(self):
        """Start of the period (unix time)."""
        return self._L.Asynch_Get_Begin_Timestamp(self._ptr)

    @property
    def end(self):
        """End of the period (unix time)."""
        return self._L.Asynch_Get_End_Timestamp(self._ptr)

    def set_period(self, begin, end):
        """Change the simulation period (unix times) before running."""
        self._L.Asynch_Set_Simulation_Period(self._ptr, int(begin), int(end))

    # -- network --------------------------------------------------------------------------------------

    @property
    def num_links(self):
        """Number of links in the network (all processes)."""
        return self._L.Asynch_Get_Num_Links(self._ptr)

    @property
    def num_links_local(self):
        """Number of links computed by this process."""
        return self._L.Asynch_Get_Num_Links_Proc(self._ptr)

    @property
    def link_ids(self):
        """Link ids in location order (the order of every per-link array of this class)."""
        f = self._L.Asynch_Get_Link_ID
        return np.array([f(self._ptr, i) for i in range(self.num_links)], dtype=np.int64)

    def location(self, link_id):
        """Location (row in the per-link arrays) of a link id."""
        loc = self._L.Asynch_Find_Link(self._ptr, int(link_id))
        if loc < 0:
            raise KeyError("link %d is not in the network" % link_id)
        return loc

    def parents(self, link_id):
        """Ids of the links upstream of a link."""
        loc = self.location(link_id)
        n = self._L.Asynch_Get_Link_Num_Parents(self._ptr, loc)
        ids = (ctypes.c_uint * max(n, 1))()
        self._L.Asynch_Get_Link_Parents(self._ptr, loc, ids)
        return [ids[i] for i in range(n)]

    def child(self, link_id):
        """Id of the link downstream of a link, or None at an outlet."""
        c = self._L.Asynch_Get_Link_Child(self._ptr, self.location(link_id))
        return None if c < 0 else c

    def owner(self, link_id):
        """Rank of the process that computes a link."""
        return self._L.Asynch_Get_Link_Owner(self._ptr, self.location(link_id))

    def save_network_dot(self, path):
        """Write the network as a Graphviz .dot file."""
        self._L.Asynch_Save_Network_Dot(self._ptr, os.fspath(path).encode())

    # -- model and parameters -------------------------------------------------------------------------

    @property
    def model_uid(self):
        """Model number of the global file."""
        return self._L.Asynch_Get_Model_Type(self._ptr)

    @property
    def global_params(self):
        """Global parameters (a copy). Setting them after load() also recomputes the derived link
        parameters of every link, so the new values are used from the next step on."""
        n = self._L.Asynch_Get_Size_Global_Parameters(self._ptr)
        buf = np.zeros(n)
        if n:
            self._L.Asynch_Get_Global_Parameters(self._ptr, buf.ctypes.data_as(_lib.c_double_p))
        return buf

    @global_params.setter
    def global_params(self, values):
        v = np.ascontiguousarray(values, dtype=float)
        if self._loaded and len(v) != len(self.global_params):
            raise AsynchError("the number of global parameters cannot change after load()")
        self._L.Asynch_Set_Global_Parameters(self._ptr, v.ctypes.data_as(_lib.c_double_p), len(v))
        if self._loaded:
            self._L.Asynch_Update_Precalculations(self._ptr)

    @property
    def num_link_params(self):
        """Parameters per link (read from disk + derived)."""
        return self._L.Asynch_Get_Num_Link_Params(self._ptr)

    @property
    def num_disk_params(self):
        """Parameters per link read from the .prm file."""
        return self._L.Asynch_Get_Num_Disk_Params(self._ptr)

    def get_link_params(self, link_id):
        """All parameters of a link (read + derived). The link must be stored on this process
        (always true on one process)."""
        buf = np.zeros(self.num_link_params)
        if self._L.Asynch_Get_Link_Params(self._ptr, self.location(link_id), buf.ctypes.data_as(_lib.c_double_p)):
            raise AsynchError("the parameters of link %d are not stored on process %d" % (link_id, self.rank))
        return buf

    def set_link_params(self, link_id, values, update=True):
        """Set the first len(values) parameters of a link (usually those read from disk) and, if update,
        recompute the derived parameters of every link. Ignored for links not stored on this process;
        call it on every process."""
        v = np.ascontiguousarray(values, dtype=float)
        loc = self.location(link_id)
        if len(v) > self.num_link_params:
            raise AsynchError("link %d has %d parameters" % (link_id, self.num_link_params))
        self._L.Asynch_Set_Link_Params(self._ptr, loc, v.ctypes.data_as(_lib.c_double_p), len(v))
        if update:
            self._L.Asynch_Update_Precalculations(self._ptr)
            self._raise_model_error()

    def update_precalculations(self):
        """Recompute the derived parameters of every link (after several set_link_params(update=False))."""
        self._L.Asynch_Update_Precalculations(self._ptr)
        self._raise_model_error()

    # -- states ---------------------------------------------------------------------------------------

    @property
    def max_dim(self):
        """Largest number of states of a link."""
        return self._L.Asynch_Get_Max_Dim(self._ptr)

    @property
    def states(self):
        """*Collective.* Current states of every link: array [num_links, max_dim], rows in location order
        (see link_ids). Every process gets the whole array."""
        self._check_loaded()
        buf = np.zeros((self.num_links, self.max_dim))
        self._L.Asynch_Gather_States(self._ptr, buf.ctypes.data_as(_lib.c_double_p))
        return buf

    def set_states(self, states, time=None):
        """*Collective.* Replace the states of every link (array [num_links, max_dim], as `states`) and
        restart the solver from them at `time` [minutes since the start, default: now]."""
        self._check_loaded()
        s = np.ascontiguousarray(states, dtype=float)
        if s.shape != (self.num_links, self.max_dim):
            raise AsynchError("states must have shape %s" % ((self.num_links, self.max_dim),))
        t = self.time if time is None else float(time)
        self._L.Asynch_Set_States(self._ptr, t, s.ctypes.data_as(_lib.c_double_p))
        self._raise_model_error()

    def state(self, link_id):
        """(time, states) of one link computed by this process."""
        loc = self.location(link_id)
        n = self._L.Asynch_Get_Link_Dim(self._ptr, loc)
        y = np.zeros(n)
        t = ctypes.c_double()
        if self._L.Asynch_Get_Link_State(self._ptr, loc, y.ctypes.data_as(_lib.c_double_p), ctypes.byref(t)):
            raise AsynchError("link %d is computed by process %d, not %d" % (link_id, self.owner(link_id), self.rank))
        return t.value, y

    @property
    def peaks(self):
        """*Collective.* (time of peak [min], peak discharge) of every link since the start, arrays in
        location order. Links without peak output (see the peak links of the global file) give 0."""
        self._check_loaded()
        n = self.num_links
        t, v = np.zeros(n), np.zeros(n)
        self._L.Asynch_Gather_Peakflows(self._ptr, t.ctypes.data_as(_lib.c_double_p), v.ctypes.data_as(_lib.c_double_p))
        return t, v

    def reset_peaks(self):
        """Start the peak flow search again from the current states."""
        self._L.Asynch_Reset_Peakflow_Data(self._ptr)

    # -- forcings -------------------------------------------------------------------------------------

    @property
    def num_forcings(self):
        return self._L.Asynch_Get_Num_Forcings(self._ptr)

    def forcing_values(self, link_id):
        """Current value of every forcing at a link computed by this process."""
        buf = np.zeros(self.num_forcings)
        if self._L.Asynch_Get_Link_Forcings(self._ptr, self.location(link_id), buf.ctypes.data_as(_lib.c_double_p)):
            raise AsynchError("link %d is not computed by process %d" % (link_id, self.rank))
        return buf

    def activate_forcing(self, index, active=True):
        """Switch a forcing on or off (off = 0 everywhere)."""
        f = self._L.Asynch_Activate_Forcing if active else self._L.Asynch_Deactivate_Forcing
        if f(self._ptr, int(index)):
            raise AsynchError("invalid forcing index %d" % index)

    def forcing_timestamps(self, index):
        """(first, last) unix times of a forcing (database and binary forcings)."""
        return (self._L.Asynch_Get_First_Forcing_Timestamp(self._ptr, index),
                self._L.Asynch_Get_Last_Forcing_Timestamp(self._ptr, index))

    def set_forcing_timestamps(self, index, first=None, last=None):
        if first is not None:
            self._L.Asynch_Set_First_Forcing_Timestamp(self._ptr, int(first), index)
        if last is not None:
            self._L.Asynch_Set_Last_Forcing_Timestamp(self._ptr, int(last), index)

    def set_forcing_state(self, index, t_0, first_file, last_file):
        """Restart a forcing at time t_0 [min] with the files/times first_file..last_file (forecasting)."""
        if self._L.Asynch_Set_Forcing_State(self._ptr, index, float(t_0), int(first_file), int(last_file)):
            raise AsynchError("could not set forcing %d" % index)

    def set_forcing_db_start(self, index, unix_time):
        self._L.Asynch_Set_Forcing_DB_Starttime(self._ptr, int(unix_time), index)

    @property
    def reservoir_forcing(self):
        """Index of the forcing that feeds the reservoirs, or -1."""
        return self._L.Asynch_Get_Reservoir_Forcing(self._ptr)

    # -- initial state and databases ------------------------------------------------------------------

    def set_initial_file(self, path):
        """Use another initial-state file (.ini, .uini, .rec or .h5). Call before load()."""
        path = os.fspath(path)
        if os.path.splitext(path)[1] not in (".ini", ".uini", ".rec", ".h5"):
            raise AsynchError("initial-state files end in .ini, .uini, .rec or .h5: %s" % path)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        if self._loaded:
            raise AsynchError("set_initial_file must be called before load()")
        self._L.Asynch_Set_Init_File(self._ptr, path.encode())

    @property
    def init_timestamp(self):
        return self._L.Asynch_Get_Init_Timestamp(self._ptr)

    @init_timestamp.setter
    def init_timestamp(self, unix_time):
        if self._L.Asynch_Set_Init_Timestamp(self._ptr, int(unix_time)):
            raise AsynchError("the initial state is not read from a database")

    def set_database_connection(self, conninfo, index):
        """Replace database connection number `index` (see ASYNCH_DB_LOC_* in src/constants.h)."""
        self._L.Asynch_Set_Database_Connection(self._ptr, conninfo.encode(), int(index))

    # -- output files and custom outputs --------------------------------------------------------------

    def _get_name(self, getter):
        buf = ctypes.create_string_buffer(_lib.MAX_PATH_LENGTH)
        if getter(self._ptr, buf):
            return None
        return buf.value.decode()

    @property
    def snapshot_path(self):
        return self._get_name(self._L.Asynch_Get_Snapshot_Output_Name)

    @snapshot_path.setter
    def snapshot_path(self, path):
        if self._L.Asynch_Set_Snapshot_Output_Name(self._ptr, os.fspath(path).encode()):
            raise AsynchError("snapshot path too long")

    @property
    def peaks_path(self):
        """Peak flow file, without the .pea extension (None if there is no peak output)."""
        return self._get_name(self._L.Asynch_Get_Peakflow_Output_Name)

    @peaks_path.setter
    def peaks_path(self, path):
        if self._outputs_ready:
            raise AsynchError("the peak flow file must be named before the outputs are prepared (load)")
        buf = ctypes.create_string_buffer(os.fspath(path).encode(), _lib.MAX_PATH_LENGTH)
        ret = self._L.Asynch_Set_Peakflow_Output_Name(self._ptr, buf)
        if ret == 1:
            raise AsynchError("the global file has no peak flow output")
        if ret == 2:
            raise AsynchError("the peak flow file must end in .pea")

    def set_output(self, name, function, states=(), dtype=float):
        """Define the time series output `name` listed in the "%Components to print" of the global file.

        function(link_id, time, y) -> number, where y are the states of the link. `states` lists the
        indices of the states that function uses (they are then interpolated at the output times).
        dtype: float (written as double), np.float32 or int. Call after reading the global file and
        before load() (or before loading the initial conditions when loading step by step)."""
        self._check_open()
        if self.config is None:
            raise AsynchError("read the global file first")
        if self._loaded:
            raise AsynchError("set_output must be called before load()")
        if self._L.Asynch_Check_Output(self._ptr, name.encode()) == -1:
            raise AsynchError("%s is not in the outputs of the global file" % name)
        kinds = {float: ("Asynch_Set_Output_Double", _lib.OUTPUT_DOUBLE),
                 np.float64: ("Asynch_Set_Output_Double", _lib.OUTPUT_DOUBLE),
                 np.float32: ("Asynch_Set_Output_Float", _lib.OUTPUT_FLOAT),
                 int: ("Asynch_Set_Output_Int", _lib.OUTPUT_INT)}
        if dtype not in kinds:
            raise AsynchError("dtype must be float, numpy.float32 or int")
        setter, ctype = kinds[dtype]
        errors = []

        def call(link_id, t, y, n):
            try:
                return function(link_id, t, np.ctypeslib.as_array(y, (n,)))
            except BaseException as e:
                if not errors:
                    errors.append(e)
                return 0
        cb = ctype(call)
        self._outputs[name] = (cb, errors)
        used = (ctypes.c_uint * max(len(states), 1))(*states)
        if not getattr(self._L, setter)(self._ptr, name.encode(), cb, used, len(states)):
            raise AsynchError("could not set output %s" % name)

    def set_peakflow_output(self, name, function):
        """Define the peak flow function `name` given in the global file.

        function(link_id, peak_time, peak_values, params, global_params, area_conversion, area_index)
        -> str, one line of the peak file (at most 255 characters, newline included)."""
        n_states = max(self.max_dim, 1) if self._loaded else 1
        errors = []

        def call(link_id, peak_time, peak_value, params, gparams, conversion, area_idx, user, buffer):
            try:
                line = function(link_id, peak_time,
                                np.ctypeslib.as_array(peak_value, (n_states,)),
                                np.ctypeslib.as_array(params, (max(self.num_link_params, 1),)),
                                np.ctypeslib.as_array(gparams, (max(len(self.global_params), 1),)),
                                conversion, area_idx)
                data = line.encode()[:_lib.PEAKFLOW_BUFFER_SIZE - 1] + b"\0"
            except BaseException as e:
                if not errors:
                    errors.append(e)
                data = b"\n\0"
            ctypes.memmove(buffer, data, len(data))
        cb = _lib.PEAKFLOW_OUTPUT(call)
        self._outputs["peakflow:" + name] = (cb, errors)
        if not self._L.Asynch_Set_Peakflow_Output(self._ptr, name.encode(), cb):
            raise AsynchError("the global file uses another peakflow function than %s" % name)

    def output_errors(self):
        """Exceptions raised by Python output functions (they write 0 instead)."""
        return {name: e[0] for name, (cb, e) in self._outputs.items() if e}
