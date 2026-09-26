"""
Define a new hydrological model in Python and let the ASYNCH solver integrate it.

A model is a set of ordinary differential equations solved at every link of the river network. You
describe it with names, and give the equations either

* as **C code** (a string): it is compiled once into a small shared library and runs at the speed of
  the built-in models; or
* as **Python functions**: no compiler needed, handy to try an idea, but each evaluation goes through
  the Python interpreter. Measured on 5 000 links, 2 simulated hours, model 190: built-in 0.11 s,
  C code 0.12 s, Python functions 16 s (about 140 times slower). The three give identical numbers.

Example: a linear reservoir at every link, dq/dt = (inflow - q) / k, with the rain falling on the
hillslope of area A_h going straight into the channel::

    from asynch.model import Model

    m = Model(
        name="linear_reservoir",
        states=["q"],                         # state 0: discharge [m3/s]
        global_params=["k"],                  # residence time [min], same everywhere
        params=["A_h"],                       # read from the .prm file [m2]
        forcings=["rain"],                    # [mm/h]
    )
    m.equations = '''
        double inflow = upstream_q + rain * A_h * (0.001 / 3600.0);    /* mm/h * m2 -> m3/s */
        d_q = (inflow - q) / k;
    '''

Inside the C code, every name is a local variable: the states (``q``), the global parameters
(``k``), the link parameters (``A_h``) and the forcings (``rain``). Set the time derivative of each
state in ``d_<state>``. ``upstream_<state>`` is the sum of that state over the upstream links (for
the states listed in ``dense``, by default the first one). ``t`` is the time in minutes. The math
functions of C (``pow``, ``exp``, ``fmax``, ...) are available.

The same model with Python functions::

    import numpy as np
    def equations(t, y, upstream, gp, p, forcing):
        # y: states of this link; upstream: array [num_parents, max_dim] of the upstream states
        inflow = upstream[:, 0].sum() + forcing[0] * p[0] * (0.001 / 3600.0)
        return [(inflow - y[0]) / gp[0]]
    m.equations = equations

Then run it on a network described by a global file::

    from asynch import Simulation
    with Simulation("my_network.gbl", model=m) as sim:
        sim.run()

The model number in the global file is ignored when a model is given (it is still written in the
output files).
"""
import ctypes
import hashlib
import keyword
import os
import re
import shlex
import subprocess
import sys
import sysconfig
import tempfile

import numpy as np

from . import _lib

_C_KEYWORDS = set("""auto break case char const continue default do double else enum extern float for goto if
inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void
volatile while _Bool _Complex _Imaginary bool true false NULL""".split())

# names used by the generated code
_RESERVED = {"t", "y_i", "y_p", "ans", "num_dof", "num_parents", "max_num_dof", "global_params", "params",
             "forcing_values", "qvs", "state", "user", "y", "dim", "num_global_params", "num_params",
             "discontinuity_state"}

_NONNEGATIVE = {None: 0, False: 0, "none": 0, "all": 1, True: 1, "discharge": 2}


class ModelError(Exception):
    """A problem in the definition of a model (names, sizes, compilation, or an error raised inside a
    Python model function during a run)."""


class Model:
    """A model defined outside the C source of ASYNCH.

    Parameters
    ----------
    states : list of str
        Names of the states, in order. State 0 should be the discharge [m3/s]: the peak flow output and
        the ``upstream_...`` sums of the parents use it.
    global_params : list of str
        Parameters that are the same at every link, given in the global file (in this order).
    params : list of str
        Parameters of each link read from the .prm file (in this order).
    derived_params : list of str
        Parameters of each link computed once from the others by :attr:`precalculations`.
    forcings : list of str
        Time-dependent inputs (rain, evaporation, ...), in the order of the global file.
    dense : list of str
        States that downstream links need (dense output), default: the first state.
    read_initial : list of str
        States read from the initial-state file, in order; must be the first states. Default: all.
        The others start at 0, unless :attr:`initialize` sets them.
    nonnegative : None, "all" or "discharge"
        Clip the states after every stage: "all" = every state >= 0, "discharge" = state 0 >= 1e-14 and
        the others >= 0 (as models 190 and 254). Ignored if :attr:`consistency` is set.
    param_factors : dict
        Factor applied to a parameter when it is read, e.g. ``{"L": 1000.0}`` for km -> m.
    area, hillslope_area : str
        Link parameters holding the upstream area and the hillslope area (written in the peak flow
        output), and ``areas_converted_to_m2`` if they were converted from km2 (then the peak output
        converts back).
    name : str
        Used for the name of the compiled library.

    Equations are set with the attributes :attr:`equations` (required), :attr:`precalculations`,
    :attr:`initialize` and :attr:`consistency`, each either C code (str) or a Python function, and
    :attr:`support_code` for C helper functions.
    """

    def __init__(self, states, global_params=(), params=(), derived_params=(), forcings=(), dense=None,
                 read_initial=None, nonnegative=None, param_factors=None, area=None, hillslope_area=None,
                 areas_converted_to_m2=False, min_error_tolerances=None, name="custom", jit=None):
        self.name = str(name)
        if jit not in (None, "numba"):
            raise ModelError("jit must be None or 'numba'")
        self.jit = jit
        self.states = list(states)
        self.global_params = list(global_params)
        self.params = list(params)
        self.derived_params = list(derived_params)
        self.forcings = list(forcings)
        self.dense = list(dense) if dense is not None else self.states[:1]
        self.read_initial = list(read_initial) if read_initial is not None else list(self.states)
        if nonnegative not in _NONNEGATIVE:
            raise ModelError("nonnegative must be None, 'all' or 'discharge'")
        self.nonnegative = nonnegative
        self.param_factors = dict(param_factors or {})
        self.area = area
        self.hillslope_area = hillslope_area
        self.areas_converted_to_m2 = bool(areas_converted_to_m2)
        self.min_error_tolerances = min_error_tolerances

        self.equations = None
        self.precalculations = None
        self.initialize = None
        self.consistency = None
        self.support_code = ""
        self.compiler = None           # command, default: $CC or the compiler that built Python, or cc
        self.cflags = "-O2"

        self._check_names()
        self._clib = None              # compiled library, kept alive while the model exists
        self._callbacks = []           # ctypes callbacks, kept alive while the model exists
        self._error = None             # first exception raised in a Python model function

    # -- names and sizes ------------------------------------------------------------------------------

    @property
    def all_params(self):
        """Link parameters: read from disk, then derived."""
        return self.params + self.derived_params

    def index(self, name):
        """Position of a state, link parameter, global parameter or forcing in its array."""
        for group in (self.states, self.all_params, self.global_params, self.forcings):
            if name in group:
                return group.index(name)
        raise KeyError(name)

    def _check_names(self):
        groups = [("state", self.states), ("global parameter", self.global_params), ("parameter", self.params),
                  ("derived parameter", self.derived_params), ("forcing", self.forcings)]
        seen = {}
        for kind, names in groups:
            for n in names:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", n):
                    raise ModelError("%s name %r is not a valid identifier" % (kind, n))
                if n in _C_KEYWORDS or keyword.iskeyword(n) or n in _RESERVED \
                        or n.startswith("d_") or n.startswith("upstream_"):
                    raise ModelError("%s name %r is reserved; choose another" % (kind, n))
                if n in seen:
                    raise ModelError("name %r is used twice (%s and %s)" % (n, seen[n], kind))
                seen[n] = kind
        if not self.states:
            raise ModelError("a model needs at least one state")
        for n in self.dense:
            if n not in self.states:
                raise ModelError("dense state %r is not a state" % n)
        if self.read_initial != self.states[:len(self.read_initial)]:
            raise ModelError("read_initial must be the first states, in order")
        for n in self.param_factors:
            if n not in self.params:
                raise ModelError("param_factors: %r is not a parameter read from disk" % n)
        for n in (self.area, self.hillslope_area):
            if n is not None and n not in self.all_params:
                raise ModelError("%r is not a link parameter" % n)

    # -- C code generation ------------------------------------------------------------------------------

    def c_source(self):
        """The C source compiled for this model (for C equations)."""
        self._check_names()
        out = ["/* Generated by the asynch Python package for model %r. */" % self.name,
               "#include <math.h>", "#include <stddef.h>", ""]
        if self.support_code:
            out += [_dedent(self.support_code), ""]

        def decl(names, array, const=True, offset=0):
            q = "const double" if const else "double"
            return ["    %s %s = %s[%d]; (void)%s;" % (q, n, array, i + offset, n) for i, n in enumerate(names)]

        # differential
        out.append("void asynch_model_differential(double t, const double * const y_i, unsigned int num_dof, "
                   "const double * const y_p, unsigned short num_parents, unsigned int max_num_dof, "
                   "const double * const global_params, const double * const params, "
                   "const double * const forcing_values, const void * const qvs, int state, void *user, "
                   "double *ans)")
        out.append("{")
        out += decl(self.global_params, "global_params")
        out += decl(self.all_params, "params")
        out += decl(self.forcings, "forcing_values")
        out += decl(self.states, "y_i")
        for n in self.states:
            out.append("    double d_%s = 0.0;" % n)
        for n in self.dense:
            k = self.states.index(n)
            out.append("    double upstream_%s = 0.0; (void)upstream_%s;" % (n, n))
            out.append("    for (unsigned int i = 0; i < num_parents; i++) upstream_%s += y_p[i * max_num_dof + %d];"
                       % (n, k))
        out.append("    (void)t; (void)num_dof; (void)qvs; (void)state; (void)user;")
        out.append("    {")
        out.append(_indent(_dedent(self.equations), 8))
        out.append("    }")
        for k, n in enumerate(self.states):
            out.append("    ans[%d] = d_%s;" % (k, n))
        out.append("}")
        out.append("")

        if isinstance(self.precalculations, str):
            out.append("void asynch_model_precalculations(const double * const global_params, "
                       "unsigned int num_global_params, double *params, unsigned int num_params, void *user)")
            out.append("{")
            out += decl(self.global_params, "global_params")
            out += decl(self.params, "params")
            out += ["    double %s = 0.0;" % n for n in self.derived_params]
            out.append("    (void)num_global_params; (void)num_params; (void)user;")
            out.append("    {")
            out.append(_indent(_dedent(self.precalculations), 8))
            out.append("    }")
            for i, n in enumerate(self.derived_params):
                out.append("    params[%d] = %s;" % (len(self.params) + i, n))
            out.append("}")
            out.append("")

        if isinstance(self.initialize, str):
            out.append("int asynch_model_initialize(const double * const global_params, unsigned int "
                       "num_global_params, const double * const params, unsigned int num_params, double *y, "
                       "unsigned int dim, void *user)")
            out.append("{")
            out += decl(self.global_params, "global_params")
            out += decl(self.all_params, "params")
            out += decl(self.states, "y", const=False)
            out.append("    int discontinuity_state = 0;")
            out.append("    (void)num_global_params; (void)num_params; (void)dim; (void)user;")
            out.append("    {")
            out.append(_indent(_dedent(self.initialize), 8))
            out.append("    }")
            for k, n in enumerate(self.states):
                out.append("    y[%d] = %s;" % (k, n))
            out.append("    return discontinuity_state;")
            out.append("}")
            out.append("")

        if isinstance(self.consistency, str):
            out.append("void asynch_model_consistency(double *y, unsigned int dim, const double * const "
                       "global_params, unsigned int num_global_params, const double * const params, "
                       "unsigned int num_params, void *user)")
            out.append("{")
            out += decl(self.global_params, "global_params")
            out += decl(self.all_params, "params")
            out += decl(self.states, "y", const=False)
            out.append("    (void)dim; (void)num_global_params; (void)num_params; (void)user;")
            out.append("    {")
            out.append(_indent(_dedent(self.consistency), 8))
            out.append("    }")
            for k, n in enumerate(self.states):
                out.append("    y[%d] = %s;" % (k, n))
            out.append("}")
            out.append("")
        return "\n".join(out)

    def _compiler(self):
        if self.compiler:
            return shlex.split(self.compiler)
        cc = os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc"
        return shlex.split(cc)[:1]

    def compile(self, cache_dir=None):
        """Compile the C code (if any) and load it. Done automatically when the model is used.
        The library is cached, keyed by the source and flags, in cache_dir (default:
        $ASYNCH_MODEL_CACHE or ~/.cache/asynch/models). Returns its path, or None for Python equations."""
        if not any(isinstance(f, str) for f in (self.equations, self.precalculations, self.initialize,
                                                   self.consistency)):
            return None
        if not isinstance(self.equations, str):
            raise ModelError("C code for precalculations/initialize/consistency needs C equations too")
        source = self.c_source()
        compiler = self._compiler()
        flags = shlex.split(self.cflags) + ["-fPIC", "-shared"]
        key = hashlib.sha256((source + "\0" + " ".join(compiler + flags)).encode()).hexdigest()[:16]
        cache_dir = cache_dir or os.environ.get("ASYNCH_MODEL_CACHE") or \
            os.path.join(os.path.expanduser("~"), ".cache", "asynch", "models")
        os.makedirs(cache_dir, exist_ok=True)
        base = os.path.join(cache_dir, "%s_%s" % (re.sub(r"\W", "_", self.name), key))
        lib_path = base + (".dylib" if sys.platform == "darwin" else ".so")
        if not os.path.exists(lib_path):
            # Every MPI process may compile at the same time: write to a private file, then rename
            fd, tmp_c = tempfile.mkstemp(suffix=".c", dir=cache_dir)
            with os.fdopen(fd, "w") as f:
                f.write(source)
            tmp_so = tmp_c[:-2] + ".so"
            cmd = compiler + flags + ["-o", tmp_so, tmp_c, "-lm"]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            if proc.returncode != 0:
                os.unlink(tmp_c)
                raise ModelError("compiling model %r failed:\n$ %s\n%s\n--- generated source ---\n%s"
                                 % (self.name, " ".join(cmd), proc.stdout, _numbered(source)))
            os.replace(tmp_c, base + ".c")
            os.replace(tmp_so, lib_path)
        self._clib = ctypes.CDLL(lib_path)
        return lib_path

    # -- installation into a solver -------------------------------------------------------------------

    def _fn(self, clib_name, python_func, ctype, wrapper):
        """Address of a model function: from the compiled library, compiled by Numba, or a ctypes callback."""
        if python_func is None:
            return None
        if isinstance(python_func, str):
            return ctypes.cast(getattr(self._clib, clib_name), ctypes.c_void_p).value
        if self.jit == "numba":
            cf = _numba_cfunc(self, clib_name, python_func)
            self._callbacks.append(cf)
            return cf.address
        cb = ctype(wrapper(python_func))
        self._callbacks.append(cb)
        return ctypes.cast(cb, ctypes.c_void_p).value

    def build_spec(self):
        """Create the C model description (AsynchModelSpec*). Used by Simulation; the caller frees it."""
        if self.equations is None:
            raise ModelError("model %r has no equations" % self.name)
        self._check_names()
        self.compile()
        L = _lib.lib()
        spec = L.Asynch_Model_Spec_Create(len(self.states), len(self.global_params), len(self.all_params),
                                          len(self.params), len(self.forcings))
        if not spec:
            raise ModelError("invalid model sizes (at most 10 forcings)")
        self._callbacks = []

        def check(ret, what):
            if ret:
                L.Asynch_Model_Spec_Free(spec)
                raise ModelError("could not set %s of model %r" % (what, self.name))

        check(L.Asynch_Model_Spec_Set_Differential(
            spec, self._fn("asynch_model_differential", self.equations, _lib.DIFFERENTIAL_ADDR, self._wrap_equations)),
            "the equations")
        if self.precalculations is not None:
            check(L.Asynch_Model_Spec_Set_Precalculations(spec, self._fn(
                "asynch_model_precalculations", self.precalculations, _lib.PRECALCULATIONS_ADDR, self._wrap_precalc)),
                "the precalculations")
        if self.initialize is not None:
            check(L.Asynch_Model_Spec_Set_Initialize(spec, self._fn(
                "asynch_model_initialize", self.initialize, _lib.INITIALIZE_ADDR, self._wrap_initialize)),
                "the initialization")
        if self.consistency is not None:
            check(L.Asynch_Model_Spec_Set_Check_Consistency(spec, self._fn(
                "asynch_model_consistency", self.consistency, _lib.CHECK_CONSISTENCY_ADDR, self._wrap_consistency)),
                "the consistency check")
        check(L.Asynch_Model_Spec_Set_Nonnegative(spec, _NONNEGATIVE[self.nonnegative]), "nonnegative")
        check(L.Asynch_Model_Spec_Set_Num_Initial_States(spec, len(self.read_initial)), "read_initial")
        dense = (ctypes.c_uint * len(self.dense))(*[self.states.index(n) for n in self.dense])
        check(L.Asynch_Model_Spec_Set_Dense_Indices(spec, len(self.dense), dense), "dense")
        if self.param_factors:
            factors = (ctypes.c_double * len(self.params))(*[float(self.param_factors.get(n, 1.0))
                                                               for n in self.params])
            check(L.Asynch_Model_Spec_Set_Param_Factors(spec, factors), "param_factors")
        area = self.all_params.index(self.area) if self.area else 0
        areah = self.all_params.index(self.hillslope_area) if self.hillslope_area else area
        if self.all_params:
            check(L.Asynch_Model_Spec_Set_Areas(spec, area, areah, self.areas_converted_to_m2), "areas")
        if self.min_error_tolerances is not None:
            check(L.Asynch_Model_Spec_Set_Min_Error_Tolerances(spec, int(self.min_error_tolerances)),
                  "min_error_tolerances")
        return spec

    # -- Python callbacks -----------------------------------------------------------------------------

    def _guard(self, func, fallback):
        """Run func; on an exception remember it (Simulation re-raises it) and return fallback()."""
        def call(*args):
            if self._error is not None:
                return fallback(*args)
            try:
                return func(*args)
            except BaseException as e:           # never let an exception cross into C
                self._error = e
                return fallback(*args)
        return call

    def _wrap_equations(self, f):
        n_states, n_gp, n_p, n_f = len(self.states), len(self.global_params), len(self.all_params), len(self.forcings)
        view, view2 = _views()
        empty = np.zeros(0)

        def rhs(t, y_i, num_dof, y_p, num_parents, max_dim, gp, p, forcing, qvs, state, user, ans):
            res = f(t, view(y_i, num_dof),
                    view2(y_p, num_parents, max_dim) if num_parents else np.zeros((0, max_dim)),
                    view(gp, n_gp) if n_gp else empty, view(p, n_p) if n_p else empty,
                    view(forcing, n_f) if n_f else empty)
            view(ans, n_states)[:] = res

        def zero(*args):
            # after an error: zero derivatives let the run end quickly (NaN could stall the step control)
            view(args[-1], n_states)[:] = 0.0
        return self._guard(rhs, zero)

    def _wrap_precalc(self, f):
        n_disk, n_all = len(self.params), len(self.all_params)
        view, _ = _views()

        def pre(gp, n_gp, p, n_p, user):
            params = view(p, n_all)
            res = f(view(gp, n_gp) if n_gp else np.zeros(0), params)
            if res is not None:
                params[n_disk:] = res
        return self._guard(pre, lambda *a: None)

    def _wrap_initialize(self, f):
        view, _ = _views()

        def init(gp, n_gp, p, n_p, y, dim, user):
            yy = view(y, dim)
            res = f(view(gp, n_gp) if n_gp else np.zeros(0), view(p, n_p) if n_p else np.zeros(0), yy)
            if res is not None:
                yy[:] = res
            return 0
        return self._guard(init, lambda *a: 0)

    def _wrap_consistency(self, f):
        view, _ = _views()

        def cons(y, dim, gp, n_gp, p, n_p, user):
            f(view(y, dim), view(gp, n_gp) if n_gp else np.zeros(0), view(p, n_p) if n_p else np.zeros(0))
        return self._guard(cons, lambda *a: None)

    def raise_pending_error(self):
        """Raise the exception of a Python model function, if one happened (called by Simulation)."""
        if self._error is not None:
            e, self._error = self._error, None
            raise ModelError("error in a Python function of model %r: %r" % (self.name, e)) from e


def _numba_cfunc(model, kind, f):
    """Compile a Python model function with Numba into a C function with the signature ASYNCH calls
    (DifferentialFunc, SpecPrecalculationsFunc, SpecInitializeFunc or CheckConsistencyFunc). The user function
    keeps the signature of the pure Python mode; it is compiled with numba.njit (nopython mode)."""
    try:
        import numba
        from numba import types, carray
    except ImportError:
        raise ModelError("jit='numba' needs the numba package (pip install numba)")
    fj = f if hasattr(f, "py_func") else numba.njit(f)
    f64, u32, dp, vp = types.float64, types.uint32, types.CPointer(types.float64), types.voidptr
    n_states, n_gp = len(model.states), len(model.global_params)
    n_p, n_f, n_disk = len(model.all_params), len(model.forcings), len(model.params)
    n_derived = n_p - n_disk

    if kind == "asynch_model_differential":
        sig = types.void(f64, dp, u32, dp, types.uint16, u32, dp, dp, dp, vp, types.int32, vp, dp)

        def rhs(t, y_i, num_dof, y_p, num_parents, max_dim, gp, p, fo, qvs, state, user, ans):
            res = fj(t, carray(y_i, (num_dof,)), carray(y_p, (num_parents, max_dim)), carray(gp, (n_gp,)),
                     carray(p, (n_p,)), carray(fo, (n_f,)))
            out = carray(ans, (n_states,))
            for k in range(n_states):
                out[k] = res[k]
        py = rhs
    elif kind == "asynch_model_precalculations":
        sig = types.void(dp, u32, dp, u32, vp)
        if n_derived:
            def pre(gp, ngp, p, np_, user):
                params = carray(p, (n_p,))
                res = fj(carray(gp, (ngp,)), params)
                for k in range(n_derived):
                    params[n_disk + k] = res[k]
        else:
            def pre(gp, ngp, p, np_, user):
                fj(carray(gp, (ngp,)), carray(p, (n_p,)))
        py = pre
    elif kind == "asynch_model_initialize":
        sig = types.int32(dp, u32, dp, u32, dp, u32, vp)

        def init(gp, ngp, p, np_, y, dim, user):
            yy = carray(y, (dim,))
            res = fj(carray(gp, (ngp,)), carray(p, (np_,)), yy)
            for k in range(dim):
                yy[k] = res[k]
            return 0
        py = init
    else:
        sig = types.void(dp, u32, dp, u32, dp, u32, vp)

        def cons(y, dim, gp, ngp, p, np_, user):
            fj(carray(y, (dim,)), carray(gp, (ngp,)), carray(p, (np_,)))
        py = cons
    try:
        return numba.cfunc(sig, nopython=True)(py)
    except Exception as e:
        raise ModelError("Numba could not compile %s of model %r (in jit='numba' mode, use only NumPy and math "
                         "operations Numba supports, and return a tuple or an array): %s" % (kind[13:], model.name, e))


def _views(limit=200000):
    """NumPy views of C arrays given by their address, cached: the same arrays (parameters of a link, the solver's
    work arrays) are passed again and again, and building a view costs more than the equations of a small model.
    The cache is emptied when it holds `limit` views, which bounds its memory on very large networks."""
    cache = {}
    as_array = np.ctypeslib.as_array
    c_double = ctypes.c_double

    def view(addr, n):
        key = (addr, n)
        v = cache.get(key)
        if v is None:
            if len(cache) >= limit:
                cache.clear()
            v = cache[key] = as_array((c_double * n).from_address(addr))
        return v

    def view2(addr, rows, cols):
        key = (addr, rows, cols)
        v = cache.get(key)
        if v is None:
            if len(cache) >= limit:
                cache.clear()
            v = cache[key] = as_array((c_double * (rows * cols)).from_address(addr)).reshape(rows, cols)
        return v
    return view, view2


def _dedent(code):
    import textwrap
    return textwrap.dedent(code or "").strip("\n")


def _indent(code, n):
    pad = " " * n
    return "\n".join(pad + l if l.strip() else l for l in code.splitlines())


def _numbered(source):
    return "\n".join("%4d  %s" % (i + 1, l) for i, l in enumerate(source.splitlines()))
