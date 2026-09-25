"""Tests of asynch.model: models defined in Python, in C code or as Python functions.

Two kinds of checks:
* the built-in model 190 rewritten through the Python package gives exactly the same numbers;
* simple models with a known exact solution, on networks written from Python, match that solution.
"""
import math
import os
import shutil
import tempfile
import unittest

import numpy as np

import helpers
from asynch import Simulation, Model, ModelError, AsynchError, GlobalConfig, io
from asynch.config import FileRef, Forcing, Output, Selection


def model190(backend):
    """Model 190 (src/models/equations.c, LinearHillslope_MonthlyEvap), written with the Python package."""
    m = Model(name="m190_" + backend, states=["q", "s_p", "s_a"],
              global_params=["v_r", "lambda_1", "lambda_2", "RC", "v_h", "v_g"],
              params=["A_i", "L_i", "A_h"], derived_params=["k2", "k3", "invtau", "c_1", "c_2"],
              forcings=["rain", "evap"], nonnegative="discharge",
              param_factors={"L_i": 1000.0, "A_h": 1e6}, area="A_i", hillslope_area="A_h")
    if backend == "c":
        m.precalculations = """
            k2 = v_h * L_i / A_h * 60.0;
            k3 = v_g * L_i / A_h * 60.0;
            invtau = 60.0 * v_r * pow(A_i, lambda_2) / ((1.0 - lambda_1) * L_i);
            c_1 = RC * (0.001 / 60.0);
            c_2 = (1.0 - RC) * (0.001 / 60.0);
        """
        # The parents are added one by one, in the order of the built-in model: floating-point sums
        # depend on the order, and this test asks for identical numbers.
        m.equations = """
            double q_pl = k2 * s_p, q_al = k3 * s_a;
            double e_pot = evap * (1e-3 / (30.0 * 24.0 * 60.0));
            double C_p = 0.0, C_a = 0.0, C_T = 0.0;
            if (e_pot > 0.0) { C_p = s_p / e_pot; C_a = s_a / e_pot; C_T = C_p + C_a; }
            double Corr = (C_T > 1.0) ? 1.0 / C_T : 1.0;
            double e_p = Corr * C_p * e_pot, e_a = Corr * C_a * e_pot;
            double inflow = -q + (q_pl + q_al) * A_h / 60.0;
            for (unsigned int i = 0; i < num_parents; i++) inflow += y_p[i * max_num_dof];
            d_q = invtau * pow(q, lambda_1) * inflow;
            d_s_p = rain * c_1 - q_pl - e_p;
            d_s_a = rain * c_2 - q_al - e_a;
        """
    else:
        def precalculations(g, p):
            A_i, L_i, A_h = p[0], p[1], p[2]
            return [g[4] * L_i / A_h * 60.0, g[5] * L_i / A_h * 60.0,
                    60.0 * g[0] * A_i ** g[2] / ((1.0 - g[1]) * L_i),
                    g[3] * (0.001 / 60.0), (1.0 - g[3]) * (0.001 / 60.0)]

        def equations(t, y, upstream, g, p, f):
            q, s_p, s_a = y[0], y[1], y[2]
            k2, k3, invtau, c_1, c_2 = p[3], p[4], p[5], p[6], p[7]
            q_pl, q_al = k2 * s_p, k3 * s_a
            e_pot = f[1] * (1e-3 / (30.0 * 24.0 * 60.0))
            C_p = C_a = C_T = 0.0
            if e_pot > 0.0:
                C_p, C_a = s_p / e_pot, s_a / e_pot
                C_T = C_p + C_a
            corr = 1.0 / C_T if C_T > 1.0 else 1.0
            e_p, e_a = corr * C_p * e_pot, corr * C_a * e_pot
            inflow = -q + (q_pl + q_al) * p[2] / 60.0
            for i in range(upstream.shape[0]):
                inflow += upstream[i, 0]
            return [invtau * q ** g[1] * inflow, f[0] * c_1 - q_pl - e_p, f[0] * c_2 - q_al - e_a]

        m.precalculations = precalculations
        m.equations = equations
    return m


@helpers.requires_library
class TestModel190(helpers.InExamples):
    """Model 190 through the Python package: identical to the built-in model, to the last bit."""

    def run_model(self, model):
        with Simulation("test_2015.gbl", model=model) as sim:
            sim.advance(write=False)
            return sim.states, sim.peaks, [sim.get_link_params(l) for l in sim.link_ids]

    def check_identical(self, backend):
        ref = self.run_model(None)
        got = self.run_model(model190(backend))
        np.testing.assert_array_equal(got[0], ref[0])
        np.testing.assert_array_equal(got[1][0], ref[1][0])
        np.testing.assert_array_equal(got[1][1], ref[1][1])
        np.testing.assert_array_equal(np.array(got[2]), np.array(ref[2]))

    @helpers.requires_compiler
    def test_c_code(self):
        self.check_identical("c")

    def test_python_functions(self):
        self.check_identical("py")

    @helpers.requires_compiler
    @helpers.requires_exe
    def test_output_files_identical_to_program(self):
        """The files written with the C-code model 190 are those of the asynch program."""
        import filecmp
        cli = os.path.join(self.tmp, "cli")
        shutil.copytree(self.dir, cli)
        helpers.run_cli("test_2015.gbl", cli)
        with Simulation("test_2015.gbl", model=model190("c")) as sim:
            sim.run()
        for f in ("out_2015/test.dat", "out_2015/test.pea", "out_2015/test.rec"):
            self.assertTrue(filecmp.cmp(os.path.join(cli, f), f, shallow=False), f)

    @helpers.requires_compiler
    def test_generated_source(self):
        m = model190("c")
        src = m.c_source()
        self.assertIn("const double A_h = params[2];", src)
        self.assertIn("ans[2] = d_s_a;", src)
        path = m.compile()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(m.compile(), path)                      # cached


class Network:
    """A small setup written from Python: a chain of links, one state per link, no rain unless given."""

    def __init__(self, folder, links=1, minutes=60, q0=1.0, rain=None, model=0, num_states=1, tol=1e-12):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        f = lambda n: os.path.join(folder, n)
        # chain: link 1 is the outlet, link k+1 flows into link k
        io.write_rvr(f("chain.rvr"), {k: ([k + 1] if k < links else []) for k in range(1, links + 1)})
        io.write_prm(f("chain.prm"), {k: [1.0e6] for k in range(1, links + 1)})       # A_h = 1 km2 in m2
        io.write_uini(f("chain.uini"), model, [q0] + [0.0] * (num_states - 1))
        forcings = []
        if rain is not None:
            io.write_ustr(f("rain.ustr"), rain)
            forcings = [Forcing.uniform("rain.ustr")]
        self.config = GlobalConfig(
            model=model, begin="2020-01-01 00:00", end="2020-01-01 %02d:%02d" % (minutes // 60, minutes % 60),
            global_params=[10.0], topology=FileRef(0, "chain.rvr"), parameters=FileRef(0, "chain.prm"),
            initial_state=FileRef(1, "chain.uini"), forcings=forcings,
            hydrographs=Output(1, 1.0, "chain.dat"), hydrograph_links=Selection(3), peak_links=Selection(0),
            abstol=[tol] * num_states, reltol=[tol] * num_states,
            abstol_dense=[tol] * num_states, reltol_dense=[tol] * num_states)
        self.config.write(f("chain.gbl"))


def reservoir(backend, forcings=()):
    """dq/dt = (inflow - q) / k at every link; inflow = upstream discharge (+ rain * A_h if a forcing)."""
    m = Model(name="reservoir_" + backend, states=["q"], global_params=["k"], params=["A_h"], forcings=forcings,
              area="A_h", hillslope_area="A_h")
    if backend == "c":
        rain = " + rain * A_h * (0.001 / 3600.0)" if forcings else ""
        m.equations = "d_q = (upstream_q%s - q) / k;" % rain
    else:
        def eq(t, y, up, g, p, f):
            inflow = up[:, 0].sum() + (f[0] * p[0] * (0.001 / 3600.0) if len(f) else 0.0)
            return [(inflow - y[0]) / g[0]]
        m.equations = eq
    return m


@helpers.requires_library
class TestExactSolutions(unittest.TestCase):
    """Linear reservoirs have exact solutions; the solver must match them to its tolerance."""

    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix="asynch-model-")

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def solve(self, model, **kw):
        net = Network(os.path.join(self.tmp, model.name + "_%d" % len(os.listdir(self.tmp))), **kw)
        os.chdir(net.folder)
        with Simulation("chain.gbl", model=model) as sim:
            sim.run()
            ids = list(sim.link_ids)
            states = sim.states
        return {l: states[i] for i, l in enumerate(ids)}, io.read_dat("chain.dat")

    def check_backends(self, backends=("c", "py")):
        for b in backends:
            if b == "c" and not helpers.has_compiler():
                continue
            yield b

    def test_single_reservoir(self):
        """One link, no inflow: q(t) = q0 exp(-t/k)."""
        for b in self.check_backends():
            with self.subTest(backend=b):
                final, hydro = self.solve(reservoir(b), links=1, minutes=60)
                self.assertAlmostEqual(final[1][0], math.exp(-60 / 10.0), delta=1e-9)
                t, q = hydro[1][:, 0], hydro[1][:, 1]
                np.testing.assert_allclose(q, np.exp(-t / 10.0), rtol=1e-6, atol=1e-9)   # .dat has 7 digits

    def test_chain_of_two(self):
        """Two links starting at q0 = 1: upstream q2 = exp(-t/k), outlet q1 = exp(-t/k) (1 + t/k).
        Needs the dense output of the upstream link between its own steps."""
        for b in self.check_backends():
            with self.subTest(backend=b):
                final, _ = self.solve(reservoir(b), links=2, minutes=30)
                t, k = 30.0, 10.0
                self.assertAlmostEqual(final[2][0], math.exp(-t / k), delta=1e-9)
                self.assertAlmostEqual(final[1][0], math.exp(-t / k) * (1 + t / k), delta=1e-8)

    def test_chain_of_five(self):
        """n links in a chain, all starting at 1: q_1(t) = exp(-t/k) sum_{j<n} (t/k)^j / j!."""
        n, t, k = 5, 45.0, 10.0
        for b in self.check_backends():
            with self.subTest(backend=b):
                final, _ = self.solve(reservoir(b), links=n, minutes=45)
                for i in range(1, n + 1):
                    m = n - i + 1                       # link i has m links upstream, itself included
                    exact = math.exp(-t / k) * sum((t / k) ** j / math.factorial(j) for j in range(m))
                    self.assertAlmostEqual(final[i][0], exact, delta=1e-8, msg="link %d" % i)

    def test_constant_rain(self):
        """Rain r [mm/h] on A_h [m2], q0 = 0: q(t) = Q (1 - exp(-t/k)) with Q = r A_h 0.001/3600."""
        Q = 36.0 * 1e6 * 0.001 / 3600.0            # 36 mm/h on 1 km2 = 10 m3/s
        for b in self.check_backends():
            with self.subTest(backend=b):
                final, _ = self.solve(reservoir(b, forcings=["rain"]), links=1, minutes=40, q0=0.0,
                                      rain=[(0, 36.0), (1000, 36.0)])
                self.assertAlmostEqual(final[1][0], Q * (1 - math.exp(-40 / 10.0)), delta=1e-8)

    def test_rain_that_stops(self):
        """Rain for 20 min then none: the forcing change is a discontinuity the solver steps on."""
        Q, k = 10.0, 10.0
        q20 = Q * (1 - math.exp(-20 / k))
        exact = q20 * math.exp(-(50 - 20) / k)
        for b in self.check_backends():
            with self.subTest(backend=b):
                final, _ = self.solve(reservoir(b, forcings=["rain"]), links=1, minutes=50, q0=0.0,
                                      rain=[(0, 36.0), (20, 0.0)])
                self.assertAlmostEqual(final[1][0], exact, delta=1e-8)


@helpers.requires_library
class TestModelFeatures(unittest.TestCase):

    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix="asynch-model-")

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def two_state(self, backend):
        """q (read from file) and a storage v (not read, starts at 2 q), with a derived parameter k2 = 2 k."""
        m = Model(name="two_" + backend, states=["q", "v"], global_params=["k"], params=["A_h"],
                  derived_params=["k2"], read_initial=["q"], dense=["q", "v"], area="A_h", hillslope_area="A_h")
        if backend == "c":
            m.precalculations = "k2 = 2.0 * k;"
            m.initialize = "v = 2.0 * q;"
            m.equations = "d_q = (upstream_q - q) / k2; d_v = upstream_v - v;"
            m.consistency = "if (q < 0.25) q = 0.25;"
        else:
            m.precalculations = lambda g, p: [2.0 * g[0]]
            m.initialize = lambda g, p, y: [y[0], 2.0 * y[0]]

            def eq(t, y, up, g, p, f):
                return [(up[:, 0].sum() - y[0]) / p[1], up[:, 1].sum() - y[1]]
            m.equations = eq

            def cons(y, g, p):
                if y[0] < 0.25:
                    y[0] = 0.25
            m.consistency = cons
        return m

    def test_initialize_precalculations_consistency(self):
        for b in ("c", "py"):
            if b == "c" and not helpers.has_compiler():
                continue
            with self.subTest(backend=b):
                net = Network(os.path.join(self.tmp, b), links=2, minutes=60, num_states=2, tol=1e-10)
                os.chdir(net.folder)
                with Simulation("chain.gbl", model=self.two_state(b)) as sim:
                    np.testing.assert_array_equal(sim.states, [[1.0, 2.0], [1.0, 2.0]])     # v = 2 q
                    self.assertEqual(sim.get_link_params(1)[1], 20.0)                       # k2 = 2 k
                    g = sim.global_params
                    g[0] = 5.0
                    sim.global_params = g
                    self.assertEqual(sim.get_link_params(1)[1], 10.0)                       # recomputed
                    sim.advance()
                    s = sim.states
                # without the floor, q2 = exp(-60/10) = 0.0025; the consistency check keeps it >= 0.25
                self.assertGreaterEqual(s[:, 0].min(), 0.25)
                self.assertAlmostEqual(s[:, 0].min(), 0.25, delta=1e-12)
                # v at the upstream link: dv/dt = -v, v(0) = 2
                self.assertAlmostEqual(s[:, 1].min(), 2.0 * math.exp(-60.0), delta=1e-9)

    def test_python_error_is_raised(self):
        m = Model(name="broken", states=["q"], global_params=["k"], params=["A_h"])

        def eq(t, y, up, g, p, f):
            raise ValueError("boom")
        m.equations = eq
        net = Network(os.path.join(self.tmp, "b"), links=1, minutes=10)
        os.chdir(net.folder)
        # the equations are first evaluated while loading (initial step sizes)
        with self.assertRaises(ModelError) as e:
            Simulation("chain.gbl", model=m)
        self.assertIn("boom", str(e.exception))

        calls = []

        def later(t, y, up, g, p, f):
            if t > 5.0:
                raise ValueError("late boom")
            calls.append(t)
            return [-y[0] / g[0]]
        m.equations = later
        with Simulation("chain.gbl", model=m) as sim:
            with self.assertRaises(ModelError) as e:
                sim.advance()
            self.assertIn("late boom", str(e.exception))
            self.assertTrue(calls)

    @helpers.requires_compiler
    def test_compile_error_shows_source(self):
        m = Model(name="bad_c", states=["q"])
        m.equations = "d_q = undefined_name;"
        with self.assertRaises(ModelError) as e:
            m.compile()
        self.assertIn("undefined_name", str(e.exception))
        self.assertIn("generated source", str(e.exception))

    def test_bad_definitions(self):
        with self.assertRaises(ModelError):
            Model(states=[])
        with self.assertRaises(ModelError):
            Model(states=["q", "q"])
        with self.assertRaises(ModelError):
            Model(states=["q"], params=["t"])                  # reserved
        with self.assertRaises(ModelError):
            Model(states=["q"], params=["double"])             # C keyword
        with self.assertRaises(ModelError):
            Model(states=["q"], params=["2x"])
        with self.assertRaises(ModelError):
            Model(states=["q"], params=["d_x"])
        with self.assertRaises(ModelError):
            Model(states=["q", "s"], dense=["x"])
        with self.assertRaises(ModelError):
            Model(states=["q", "s"], read_initial=["s"])       # must be the first states
        with self.assertRaises(ModelError):
            Model(states=["q"], params=["a"], param_factors={"b": 2.0})
        with self.assertRaises(ModelError):
            Model(states=["q"], nonnegative="sometimes")
        with self.assertRaises(ModelError):
            Model(states=["q"]).build_spec()                   # no equations
        m = Model(states=["q", "s"], params=["a", "b"], global_params=["g"], forcings=["r"])
        self.assertEqual([m.index(n) for n in ("s", "b", "g", "r")], [1, 1, 0, 0])

    def test_global_file_too_short_for_model(self):
        m = Model(name="needs3", states=["q"], global_params=["a", "b", "c"])
        m.equations = lambda t, y, up, g, p, f: [0.0]
        net = Network(os.path.join(self.tmp, "c"), links=1, minutes=10)
        os.chdir(net.folder)
        with self.assertRaises(AsynchError):
            Simulation("chain.gbl", model=m)
        m2 = Model(name="rain", states=["q"], forcings=["rain"])
        m2.equations = lambda t, y, up, g, p, f: [0.0]
        with self.assertRaises(AsynchError):
            Simulation("chain.gbl", model=m2)


if __name__ == "__main__":
    unittest.main()
