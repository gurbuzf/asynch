"""
Low-level binding: loads libasynch and declares the C prototype of every function the package uses.

Nothing here knows the layout of an ASYNCH structure: the C library is only handled through an opaque
pointer (``AsynchSolver*``) and plain numbers and arrays. That is what makes the binding robust: a change
of the C structures cannot silently shift memory the way the old ``py/asynch_interface.py`` did.

The library is searched in this order:

1. the path in the environment variable ``ASYNCH_LIBRARY``;
2. next to this package (a copy placed there by the user);
3. the build tree of this repository (``src/.libs``), when the package is used from a source checkout;
4. the system library path (``ctypes.util.find_library``), ``$CONDA_PREFIX/lib``, ``/usr/local/lib``.
"""
import ctypes
import ctypes.util
import os
import sys

c_double_p = ctypes.POINTER(ctypes.c_double)
c_uint_p = ctypes.POINTER(ctypes.c_uint)
c_time_t = ctypes.c_long           # time_t on Linux and macOS (LP64)
c_solver_p = ctypes.c_void_p       # AsynchSolver*, opaque
c_spec_p = ctypes.c_void_p         # AsynchModelSpec*, opaque

# Callback types, matching src/models/model.h and src/asynch_interface.h -----------------------------

#: dy/dt of one link (DifferentialFunc)
DIFFERENTIAL = ctypes.CFUNCTYPE(
    None,
    ctypes.c_double,                              # t
    c_double_p, ctypes.c_uint,                    # y_i, num_dof
    c_double_p, ctypes.c_ushort, ctypes.c_uint,   # y_p, num_parents, max_num_dof
    c_double_p,                                   # global_params
    c_double_p,                                   # params
    c_double_p,                                   # forcing_values
    ctypes.c_void_p,                              # qvs (dams; not used by custom models)
    ctypes.c_int,                                 # state
    ctypes.c_void_p,                              # user
    c_double_p)                                   # ans

#: the same signatures with every pointer as a plain address (an int, or None for NULL): converting an address is
#: much cheaper than building a ctypes pointer object, which matters in functions called millions of times
V_P = ctypes.c_void_p
DIFFERENTIAL_ADDR = ctypes.CFUNCTYPE(
    None, ctypes.c_double, V_P, ctypes.c_uint, V_P, ctypes.c_ushort, ctypes.c_uint, V_P, V_P, V_P, V_P,
    ctypes.c_int, V_P, V_P)
CHECK_CONSISTENCY_ADDR = ctypes.CFUNCTYPE(None, V_P, ctypes.c_uint, V_P, ctypes.c_uint, V_P, ctypes.c_uint, V_P)
PRECALCULATIONS_ADDR = ctypes.CFUNCTYPE(None, V_P, ctypes.c_uint, V_P, ctypes.c_uint, V_P)
INITIALIZE_ADDR = ctypes.CFUNCTYPE(ctypes.c_int, V_P, ctypes.c_uint, V_P, ctypes.c_uint, V_P, ctypes.c_uint, V_P)

#: consistency check of one link (CheckConsistencyFunc)
CHECK_CONSISTENCY = ctypes.CFUNCTYPE(
    None, c_double_p, ctypes.c_uint, c_double_p, ctypes.c_uint, c_double_p, ctypes.c_uint, ctypes.c_void_p)

#: derived parameters of one link (SpecPrecalculationsFunc)
PRECALCULATIONS = ctypes.CFUNCTYPE(
    None, c_double_p, ctypes.c_uint, c_double_p, ctypes.c_uint, ctypes.c_void_p)

#: initial states of one link (SpecInitializeFunc)
INITIALIZE = ctypes.CFUNCTYPE(
    ctypes.c_int, c_double_p, ctypes.c_uint, c_double_p, ctypes.c_uint, c_double_p, ctypes.c_uint, ctypes.c_void_p)

#: custom time series outputs (OutputIntCallback, OutputDoubleCallback, OutputFloatCallback)
OUTPUT_INT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint, ctypes.c_double, c_double_p, ctypes.c_uint)
OUTPUT_DOUBLE = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_uint, ctypes.c_double, c_double_p, ctypes.c_uint)
OUTPUT_FLOAT = ctypes.CFUNCTYPE(ctypes.c_float, ctypes.c_uint, ctypes.c_double, c_double_p, ctypes.c_uint)

#: custom peak flow output (PeakflowOutputCallback); writes one line (< 256 bytes) into the buffer
PEAKFLOW_OUTPUT = ctypes.CFUNCTYPE(
    None, ctypes.c_uint, ctypes.c_double, c_double_p, c_double_p, c_double_p, ctypes.c_double,
    ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)

PEAKFLOW_BUFFER_SIZE = 256        # char buffer[256] in processdata.c
MAX_PATH_LENGTH = 1024            # ASYNCH_MAX_PATH_LENGTH in src/constants.h

V, I, U, D = None, ctypes.c_int, ctypes.c_uint, ctypes.c_double
S, B, P = c_solver_p, ctypes.c_bool, ctypes.c_char_p

# name: (return type, argument types). Every function of asynch_interface.h and asynch_api.h that can
# be called without knowing a C structure layout.
PROTOTYPES = {
    # asynch_api.h: MPI and creation
    "Asynch_MPI_Init": (I, []),
    "Asynch_MPI_Finalize": (I, []),
    "Asynch_Init_World": (S, [B]),
    "Asynch_Init_Fortran_Comm": (S, [I, B]),
    "Asynch_Get_Rank": (I, [S]),
    "Asynch_Get_Num_Procs": (I, [S]),
    # asynch_interface.h: setup, in the order of asynch_cli.c
    "Asynch_Free": (V, [S]),
    "Asynch_Parse_GBL": (V, [S, P]),
    "Asynch_Load_Network": (V, [S]),
    "Asynch_Save_Network_Dot": (V, [S, P]),
    "Asynch_Partition_Network": (V, [S]),
    "Asynch_Load_Network_Parameters": (V, [S]),
    "Asynch_Load_Dams": (V, [S]),
    "Asynch_Load_Numerical_Error_Data": (V, [S]),
    "Asynch_Initialize_Model": (V, [S]),
    "Asynch_Load_Initial_Conditions": (V, [S]),
    "Asynch_Load_Forcings": (V, [S]),
    "Asynch_Load_Save_Lists": (V, [S]),
    "Asynch_Finalize_Network": (V, [S]),
    "Asynch_Calculate_Step_Sizes": (V, [S]),
    # run
    "Asynch_Advance": (V, [S, I]),
    "Asynch_Activate_Forcing": (I, [S, U]),
    "Asynch_Deactivate_Forcing": (I, [S, U]),
    # outputs
    "Asynch_Prepare_Temp_Files": (V, [S]),
    "Asynch_Write_Current_Step": (I, [S]),
    "Asynch_Prepare_Peakflow_Output": (V, [S]),
    "Asynch_Prepare_Output": (V, [S]),
    "Asynch_Create_Output": (I, [S, P]),
    "Asynch_Create_Peakflows_Output": (I, [S]),
    "Asynch_Take_System_Snapshot": (I, [S, P]),
    "Asynch_Delete_Temporary_Files": (I, [S]),
    "Asynch_Set_Temp_Files": (I, [S, D, ctypes.c_void_p, U]),
    "Asynch_Reset_Temp_Files": (I, [S, D]),
    "Asynch_Check_Output": (I, [S, P]),
    "Asynch_Check_Peakflow_Output": (I, [S, P]),
    "Asynch_Set_Output_Int": (I, [S, P, OUTPUT_INT, c_uint_p, U]),
    "Asynch_Set_Output_Double": (I, [S, P, OUTPUT_DOUBLE, c_uint_p, U]),
    "Asynch_Set_Output_Float": (I, [S, P, OUTPUT_FLOAT, c_uint_p, U]),
    "Asynch_Set_Peakflow_Output": (I, [S, P, PEAKFLOW_OUTPUT]),
    "Asynch_Get_Snapshot_Output_Name": (I, [S, ctypes.c_void_p]),
    "Asynch_Set_Snapshot_Output_Name": (I, [S, P]),
    "Asynch_Get_Peakflow_Output_Name": (I, [S, ctypes.c_void_p]),
    "Asynch_Set_Peakflow_Output_Name": (I, [S, ctypes.c_void_p]),
    "Asynch_Reset_Peakflow_Data": (V, [S]),
    # model, time, forcings, initial state
    "Asynch_Get_Model_Type": (ctypes.c_ushort, [S]),
    "Asynch_Set_Model_Type": (V, [S, ctypes.c_ushort]),
    "Asynch_Get_Begin_Timestamp": (c_time_t, [S]),
    "Asynch_Get_End_Timestamp": (c_time_t, [S]),
    "Asynch_Get_Total_Simulation_Duration": (D, [S]),
    "Asynch_Set_Simulation_Period": (V, [S, c_time_t, c_time_t]),
    "Asynch_Set_Total_Simulation_Duration": (V, [S, D]),
    "Asynch_Set_Database_Connection": (V, [S, P, U]),
    "Asynch_Get_First_Forcing_Timestamp": (U, [S, U]),
    "Asynch_Set_First_Forcing_Timestamp": (V, [S, U, U]),
    "Asynch_Get_Last_Forcing_Timestamp": (U, [S, U]),
    "Asynch_Set_Last_Forcing_Timestamp": (V, [S, U, U]),
    "Asynch_Set_Forcing_DB_Starttime": (V, [S, U, U]),
    "Asynch_Set_Forcing_State": (I, [S, U, D, U, U]),
    "Asynch_Set_Init_File": (V, [S, P]),
    "Asynch_Set_Init_Timestamp": (I, [S, U]),
    "Asynch_Get_Init_Timestamp": (U, [S]),
    "Asynch_Set_System_State": (V, [S, D, c_double_p]),
    "Asynch_Get_Reservoir_Forcing": (I, [S]),
    "Asynch_Get_Size_Global_Parameters": (U, [S]),
    "Asynch_Get_Global_Parameters": (V, [S, c_double_p]),
    "Asynch_Set_Global_Parameters": (I, [S, c_double_p, U]),
    "Asynch_Get_Num_Links": (U, [S]),
    "Asynch_Get_Num_Links_Proc": (U, [S]),
    "Asynch_Get_Local_LinkID": (U, [S, U]),
    # asynch_api.h: network
    "Asynch_Get_Link_ID": (U, [S, U]),
    "Asynch_Find_Link": (ctypes.c_long, [S, U]),
    "Asynch_Get_Link_Owner": (I, [S, U]),
    "Asynch_Get_Link_Num_Parents": (U, [S, U]),
    "Asynch_Get_Link_Parents": (U, [S, U, c_uint_p]),
    "Asynch_Get_Link_Child": (ctypes.c_long, [S, U]),
    "Asynch_Get_Link_Dim": (U, [S, U]),
    "Asynch_Get_Max_Dim": (U, [S]),
    # parameters
    "Asynch_Get_Num_Link_Params": (U, [S]),
    "Asynch_Get_Num_Disk_Params": (U, [S]),
    "Asynch_Get_Link_Params": (I, [S, U, c_double_p]),
    "Asynch_Set_Link_Params": (I, [S, U, c_double_p, U]),
    "Asynch_Update_Precalculations": (I, [S]),
    # states, peaks, forcings
    "Asynch_Get_Current_Time": (D, [S]),
    "Asynch_Get_Link_State": (I, [S, U, c_double_p, c_double_p]),
    "Asynch_Gather_States": (I, [S, c_double_p]),
    "Asynch_Set_States": (I, [S, D, c_double_p]),
    "Asynch_Gather_Peakflows": (I, [S, c_double_p, c_double_p]),
    "Asynch_Get_Num_Forcings": (U, [S]),
    "Asynch_Get_Link_Forcings": (I, [S, U, c_double_p]),
    # custom models
    "Asynch_Model_Spec_Create": (c_spec_p, [U, U, U, U, U]),
    "Asynch_Model_Spec_Free": (V, [c_spec_p]),
    "Asynch_Model_Spec_Set_Differential": (I, [c_spec_p, ctypes.c_void_p]),
    "Asynch_Model_Spec_Set_Precalculations": (I, [c_spec_p, ctypes.c_void_p]),
    "Asynch_Model_Spec_Set_Initialize": (I, [c_spec_p, ctypes.c_void_p]),
    "Asynch_Model_Spec_Set_Num_Initial_States": (I, [c_spec_p, U]),
    "Asynch_Model_Spec_Set_Dense_Indices": (I, [c_spec_p, U, c_uint_p]),
    "Asynch_Model_Spec_Set_Nonnegative": (I, [c_spec_p, I]),
    "Asynch_Model_Spec_Set_Check_Consistency": (I, [c_spec_p, ctypes.c_void_p]),
    "Asynch_Model_Spec_Set_Param_Factors": (I, [c_spec_p, c_double_p]),
    "Asynch_Model_Spec_Set_Areas": (I, [c_spec_p, U, U, B]),
    "Asynch_Model_Spec_Set_Min_Error_Tolerances": (I, [c_spec_p, U]),
    "Asynch_Model_Spec_Set_User": (I, [c_spec_p, ctypes.c_void_p]),
    "Asynch_Install_Model": (I, [S, c_spec_p]),
}

#: C functions that are deliberately not bound, and why (see docs/guide/10_python.md)
NOT_BOUND = {
    "Asynch_Init": "takes an MPI_Comm, whose type depends on the MPI library; "
                   "use Asynch_Init_World or Asynch_Init_Fortran_Comm",
    "Asynch_Custom_Model": "takes an AsynchModel structure; use the model specification (Asynch_Install_Model)",
    "Asynch_Custom_Partitioning": "the partitioning function works on the internal Link structure",
    "Asynch_Get_Links": "returns internal Link structures; use the link accessors of asynch_api.h",
    "Asynch_Get_Links_Proc": "returns internal Link structures; use the link accessors of asynch_api.h",
    "Asynch_Create_OutputUser_Data": "per-link user data for C output callbacks; "
                                     "Python callbacks keep their own data",
    "Asynch_Free_OutputUser_Data": "see Asynch_Create_OutputUser_Data",
    "Asynch_Copy_Local_OutputUser_Data": "see Asynch_Create_OutputUser_Data",
    "Asynch_Set_Size_Local_OutputUser_Data": "see Asynch_Create_OutputUser_Data",
}


def _candidates():
    env = os.environ.get("ASYNCH_LIBRARY")
    if env:
        yield env
        return
    here = os.path.dirname(os.path.abspath(__file__))
    names = ["libasynch.so", "libasynch.so.0", "libasynch.dylib"]
    for name in names:
        yield os.path.join(here, name)
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    for sub in ("src/.libs", "build/src/.libs"):
        for name in names:
            yield os.path.join(repo, sub, name)
    found = ctypes.util.find_library("asynch")
    if found:
        yield found
    prefixes = [os.environ.get("CONDA_PREFIX"), sys.prefix, "/usr/local", "/usr"]
    for prefix in prefixes:
        if prefix:
            for name in names:
                yield os.path.join(prefix, "lib", name)


def mpich_libdir():
    """Folder of libmpi.so.12 installed by the `mpich` package of PyPI (the MPI of the self-contained wheel), or None.
    pip puts it in the lib folder of the environment (or of the user base for `pip install --user`)."""
    import site
    prefixes = [sys.prefix, getattr(site, "USER_BASE", None) or site.getuserbase(), sys.base_prefix]
    for prefix in prefixes:
        if prefix and os.path.exists(os.path.join(prefix, "lib", "libmpi.so.12")):
            return os.path.join(prefix, "lib")
    return None


def _bundled(path):
    """True for the library carried by the self-contained wheel (inside the package folder)."""
    return os.path.dirname(os.path.abspath(path)) == os.path.dirname(os.path.abspath(__file__))


def _make_mpi_global():
    """Makes Open MPI's library global when libasynch loaded it (as mpi4py does): Open MPI loads plugins at MPI_Init
    that need its symbols. RTLD_NOLOAD: only a library already loaded is affected. MPICH needs no plugins, and stays
    local, so that another library of the program linked with a different MPI is not handed MPICH's symbols."""
    try:
        ctypes.CDLL("libmpi.so.40", mode=ctypes.RTLD_GLOBAL | getattr(os, "RTLD_NOLOAD", 4))
    except OSError:
        pass


def find_library():
    """Path of the libasynch shared library that would be loaded."""
    tried = []
    for path in _candidates():
        tried.append(path)
        if os.path.sep not in path or os.path.exists(path):
            return path
    raise OSError(
        "libasynch was not found. Build ASYNCH (it installs libasynch.so) and, if it is not in a standard "
        "place, set ASYNCH_LIBRARY=/path/to/libasynch.so. Tried:\n  " + "\n  ".join(tried))


_lib = None


def lib():
    """The loaded library, with every prototype of PROTOTYPES declared (loaded on first use)."""
    global _lib
    if _lib is None:
        path = find_library()
        if _bundled(path):
            # the self-contained wheel does not carry MPI: it uses the MPICH of the `mpich` package. The library
            # finds it in the lib folder of the environment; loading it first also covers other installation layouts
            mpi_dir = mpich_libdir()
            if mpi_dir is None:
                raise OSError("the MPI library of the `mpich` package was not found: pip install mpich")
            ctypes.CDLL(os.path.join(mpi_dir, "libmpi.so.12"), mode=ctypes.RTLD_LOCAL)
        # RTLD_LOCAL: the symbols of libasynch's dependencies (HDF5 in particular) must not become global, or another
        # library loaded later in the same program, such as h5py with its own HDF5, would use them and fail.
        library = ctypes.CDLL(path, mode=ctypes.RTLD_LOCAL)
        _make_mpi_global()
        for name, (restype, argtypes) in PROTOTYPES.items():
            try:
                func = getattr(library, name)
            except AttributeError:
                raise OSError("%s does not provide %s: it is older than this Python package; rebuild ASYNCH"
                              % (path, name))
            func.restype = restype
            func.argtypes = argtypes
        library._asynch_path = path
        _lib = library
    return _lib


def mpi_init():
    """Initialise MPI unless it already is (by mpi4py, for example). Registered to finalise at exit."""
    import atexit
    if lib().Asynch_MPI_Init():
        atexit.register(lib().Asynch_MPI_Finalize)
