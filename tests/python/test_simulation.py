"""Tests of asynch.Simulation against the asynch program and against itself."""
import filecmp
import os
import shutil
import subprocess
import sys
import unittest

import numpy as np

import helpers
from asynch import Simulation, AsynchError, GlobalConfig, io
from asynch.config import Output, Selection


@helpers.requires_library
class TestRunLikeTheProgram(helpers.InExamples):
    """Simulation.run() writes the same files as the asynch program, to the last byte (1 process)."""

    def compare(self, folder, gbl, outputs):
        cli_dir = os.path.join(self.tmp, "cli")
        shutil.copytree(self.dir, cli_dir)
        proc = helpers.run_cli(gbl, os.path.join(cli_dir, folder))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        os.chdir(os.path.join(self.dir, folder))
        with Simulation(gbl) as sim:
            sim.run()
        for out in outputs:
            with self.subTest(output=out):
                self.assertTrue(filecmp.cmp(os.path.join(cli_dir, folder, out), out, shallow=False),
                                "%s differs from the asynch program" % out)

    @helpers.requires_exe
    def test_test_2015(self):
        self.compare(".", "test_2015.gbl", ["out_2015/test.dat", "out_2015/test.pea", "out_2015/test.rec"])

    @helpers.requires_exe
    def test_model_196_csv_h5(self):
        self.compare("more/model_196", "test196.gbl", ["results/test196_hydr.csv", "results/test196_peak.pea",
                                                        "results/test196_snap.h5"])

    @helpers.requires_exe
    def test_command_line_module(self):
        cli_dir = os.path.join(self.tmp, "cli")
        shutil.copytree(self.dir, cli_dir)
        helpers.run_cli("test_2015.gbl", cli_dir)
        proc = helpers.run_python("import sys; from asynch.__main__ import main; sys.exit(main(['run', 'test_2015.gbl']))",
                                  self.dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("11 links, 300 minutes simulated", proc.stdout)
        self.assertTrue(filecmp.cmp(os.path.join(cli_dir, "out_2015/test.dat"), "out_2015/test.dat", shallow=False))


@helpers.requires_library
class TestNetworkAndParameters(helpers.InExamples):

    def setUp(self):
        super().setUp()
        self.sim = Simulation("test_2015.gbl")

    def tearDown(self):
        self.sim.close()
        super().tearDown()

    def test_sizes(self):
        s = self.sim
        self.assertEqual(s.num_links, 11)
        self.assertEqual(s.num_links_local, 11)
        self.assertEqual((s.rank, s.num_procs), (0, 1))
        self.assertEqual(s.model_uid, 190)
        self.assertEqual(s.max_dim, 3)
        self.assertEqual(s.num_link_params, 8)
        self.assertEqual(s.num_disk_params, 3)
        self.assertEqual(s.num_forcings, 2)
        self.assertEqual(s.duration_total, 300.0)
        self.assertEqual(s.end - s.begin, 300 * 60)
        self.assertEqual(s.time, 0.0)

    def test_topology_matches_rvr(self):
        rvr = io.read_rvr("test.rvr")
        s = self.sim
        self.assertEqual(sorted(s.link_ids), sorted(rvr))
        for link, parents in rvr.items():
            self.assertEqual(sorted(s.parents(link)), sorted(parents))
            self.assertEqual(s.link_ids[s.location(link)], link)
            for p in parents:
                self.assertEqual(s.child(p), link)
            self.assertEqual(s.owner(link), 0)
        outlets = [l for l in rvr if s.child(l) is None]
        self.assertEqual(len(outlets), 1)
        with self.assertRaises(KeyError):
            s.location(999999)

    def test_parameters(self):
        s = self.sim
        np.testing.assert_array_equal(s.global_params, [0.33, 0.2, -0.1, 0.33, 0.1, 2.2917e-5])
        prm = io.read_prm("test.prm")
        for link, disk in prm.items():
            p = s.get_link_params(link)
            # model 190 converts L km -> m and A_h km2 -> m2 when reading
            np.testing.assert_allclose(p[:3], [disk[0], disk[1] * 1000, disk[2] * 1e6], rtol=1e-15)
            self.assertAlmostEqual(p[6], 0.33 * 0.001 / 60.0, delta=1e-20)          # c_1 = RC * 0.001/60

    def test_global_params_update_derived(self):
        s = self.sim
        g = s.global_params
        g[3] = 0.5
        s.global_params = g
        self.assertEqual(s.global_params[3], 0.5)
        link = s.link_ids[0]
        self.assertAlmostEqual(s.get_link_params(link)[6], 0.5 * 0.001 / 60.0, delta=1e-20)
        self.assertAlmostEqual(s.get_link_params(link)[7], 0.5 * 0.001 / 60.0, delta=1e-20)
        with self.assertRaises(AsynchError):
            s.global_params = [1.0, 2.0]

    def test_link_params(self):
        s = self.sim
        link = s.link_ids[3]
        p = s.get_link_params(link)
        s.set_link_params(link, [p[0], p[1] * 2, p[2]])        # longer channel -> smaller invtau
        q = s.get_link_params(link)
        self.assertEqual(q[1], p[1] * 2)
        self.assertAlmostEqual(q[5], p[5] / 2, delta=abs(p[5]) * 1e-14)
        with self.assertRaises(AsynchError):
            s.set_link_params(link, np.zeros(20))

    def test_forcing_values(self):
        # test.str: every link gets 40 mm/h at t = 0; evaporation from evap.mon (May)
        s = self.sim
        f = s.forcing_values(s.link_ids[0])
        self.assertEqual(f[0], 40.0)
        self.assertEqual(len(f), 2)

    def test_dot_file(self):
        self.sim.save_network_dot("net.dot")
        with open("net.dot") as f:
            text = f.read()
        self.assertEqual(text.count("->"), 10)


@helpers.requires_library
class TestStatesAndRuns(helpers.InExamples):

    def run_states(self, gbl="test_2015.gbl", **kw):
        with Simulation(gbl, **kw) as sim:
            sim.advance()
            return sim.states, sim.peaks

    def test_states_shape_and_values(self):
        with Simulation("test_2015.gbl") as sim:
            s0 = sim.states
            self.assertEqual(s0.shape, (11, 3))
            np.testing.assert_array_equal(s0, np.tile([1e-6, 0.0, 0.0], (11, 1)))   # test.uini
            sim.advance(60)
            self.assertEqual(sim.time, 60.0)
            t, y = sim.state(80)
            self.assertEqual(t, 60.0)
            np.testing.assert_array_equal(y, sim.states[sim.location(80)])
            self.assertGreater(y[0], 1e-3)

    def test_peaks_match_pea_file(self):
        with Simulation("test_2015.gbl") as sim:
            sim.run()
            t, v = sim.peaks
            ids = sim.link_ids
        pea = io.read_pea("out_2015/test.pea")
        for k, link in enumerate(ids):
            area, tp, peak = pea[link]
            self.assertAlmostEqual(tp, t[k], delta=5e-9)       # written with 8 decimals
            self.assertAlmostEqual(peak, v[k], delta=5e-9)

    def test_changed_global_parameter_equals_edited_file(self):
        """Setting RC from Python gives exactly the run of a global file with that RC."""
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.global_params[3] = 0.5
        cfg.write("rc05.gbl")
        ref, _ = self.run_states("rc05.gbl")
        with Simulation("test_2015.gbl") as sim:
            g = sim.global_params
            g[3] = 0.5
            sim.global_params = g
            sim.advance()
            np.testing.assert_array_equal(sim.states, ref)
        base, _ = self.run_states()
        self.assertGreater(np.abs(base[:, 0] - ref[:, 0]).max(), 1e-3)     # RC matters

    def test_config_object_equals_file(self):
        ref, _ = self.run_states()
        with Simulation(GlobalConfig.read("test_2015.gbl")) as sim:
            sim.advance()
            np.testing.assert_array_equal(sim.states, ref)

    def test_advance_in_pieces(self):
        """Stopping at intermediate times changes the step sequence, not the solution (within tolerances)."""
        ref, _ = self.run_states()
        with Simulation("test_2015.gbl") as sim:
            for target in (50, 125.5, 200):
                self.assertEqual(sim.advance(until=target), target)
            sim.advance(minutes=50)
            self.assertEqual(sim.time, 250.0)
            sim.advance()
            self.assertEqual(sim.time, 300.0)
            np.testing.assert_allclose(sim.states, ref, rtol=1e-3, atol=1e-5)
            with self.assertRaises(AsynchError):
                sim.advance(until=100)

    def test_set_states(self):
        with Simulation("test_2015.gbl") as sim:
            sim.advance(100)
            s = sim.states
            s[:, 0] *= 2.0
            sim.set_states(s)
            np.testing.assert_array_equal(sim.states, s)
            self.assertEqual(sim.time, 100.0)
            sim.advance()
            doubled = sim.states
        ref, _ = self.run_states()
        self.assertTrue(np.all(doubled[:, 0] >= ref[:, 0] * 0.999))
        with Simulation("test_2015.gbl") as sim:
            with self.assertRaises(AsynchError):
                sim.set_states(np.zeros((3, 3)))

    def test_restart_from_states(self):
        """Continuing from gathered states at the same time gives the same solution within tolerances."""
        ref, _ = self.run_states()
        with Simulation("test_2015.gbl") as sim:
            sim.advance(150)
            sim.set_states(sim.states)
            sim.advance()
            np.testing.assert_allclose(sim.states, ref, rtol=1e-3, atol=1e-5)

    def test_snapshot_to_path(self):
        with Simulation("test_2015.gbl") as sim:
            sim.advance(30)
            sim.snapshot("snap30.rec")
            self.assertEqual(sim.snapshot_path, "out_2015/test.rec")
            states = sim.states
            ids = sim.link_ids
        rec = io.read_rec("snap30.rec")
        for k, link in enumerate(ids):
            # .rec files hold 7 significant digits
            np.testing.assert_allclose(rec[link], states[k], rtol=5e-7, atol=1e-12)

    def test_initial_file_from_snapshot(self):
        """A snapshot used as initial state (.rec) restarts the run."""
        with Simulation("test_2015.gbl") as sim:
            sim.advance(30)
            sim.snapshot("snap30.rec")
            at30 = sim.states
        with Simulation("test_2015.gbl", load=False) as sim:
            sim.set_initial_file("snap30.rec")
            sim.load()
            np.testing.assert_allclose(sim.states, at30, rtol=5e-7, atol=1e-12)     # 7 digits in .rec
            with self.assertRaises(AsynchError):
                sim.set_initial_file("snap30.rec")               # after load
        with Simulation("test_2015.gbl", load=False) as sim:
            with self.assertRaises(AsynchError):
                sim.set_initial_file("test.prm")

    def test_deactivate_forcing(self):
        with Simulation("test_2015.gbl") as sim:
            sim.activate_forcing(0, False)                      # no rain
            sim.advance()
            dry = sim.states
            with self.assertRaises(AsynchError):
                sim.activate_forcing(9)
        wet, _ = self.run_states()
        self.assertLess(dry[:, 0].max(), wet[:, 0].max() / 10)

    def test_peaks_path(self):
        with Simulation("test_2015.gbl", load=False) as sim:
            self.assertEqual(sim.peaks_path, "out_2015/test")
            sim.peaks_path = "out_2015/other.pea"
            with self.assertRaises(AsynchError):
                sim.peaks_path = "out_2015/other.txt"
            sim.load()
            with self.assertRaises(AsynchError):
                sim.peaks_path = "out_2015/late.pea"             # the file is already prepared
            sim.run()
        self.assertTrue(os.path.exists("out_2015/other.pea"))


@helpers.requires_library
class TestCustomOutputs(helpers.InExamples):

    def test_output_functions(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.outputs = ["Time", "State1", "S1Double", "LinkId", "Q32"]
        cfg.hydrographs = Output(2, 5.0, "out_2015/custom.csv")
        cfg.write("custom.gbl")
        with Simulation("custom.gbl", load=False) as sim:
            sim.set_output("S1Double", lambda link, t, y: y[1], states=[1])
            sim.set_output("LinkId", lambda link, t, y: link, dtype=int)
            sim.set_output("Q32", lambda link, t, y: y[0], states=[0], dtype=np.float32)
            with self.assertRaises(AsynchError):
                sim.set_output("NotListed", lambda link, t, y: 0.0)
            sim.load()
            sim.run()
            self.assertEqual(sim.output_errors(), {})
        data = io.read_csv("out_2015/custom.csv")
        self.assertEqual(sorted(data), [3, 80])           # test.sav
        for link, rows in data.items():
            np.testing.assert_allclose(rows[:, 2], rows[:, 1], rtol=5e-7, atol=1e-12)   # S1Double == State1
            self.assertTrue(np.all(rows[:, 3] == link))
            self.assertGreater(rows[:, 4].max(), 0.1)

    def test_undefined_output_is_reported(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.outputs = ["Time", "Mine"]
        cfg.write("undefined.gbl")
        with self.assertRaises(AsynchError):
            Simulation("undefined.gbl").close()

    def test_output_errors_are_collected(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.outputs = ["Time", "Bad"]
        cfg.write("bad.gbl")
        with Simulation("bad.gbl", load=False) as sim:
            sim.set_output("Bad", lambda link, t, y: 1 / 0)
            sim.load()
            sim.run()
            self.assertIsInstance(sim.output_errors()["Bad"], ZeroDivisionError)

    def test_peakflow_function(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.peakflow_function = "Mine"
        cfg.write("mypeaks.gbl")
        with Simulation("mypeaks.gbl", load=False) as sim:
            sim.set_peakflow_output("Mine", lambda link, t, y, p, g, conv, area: "%d %.3f\n" % (link, y[0]))
            sim.load()
            sim.run()
            t, v = sim.peaks
            ids = sim.link_ids
        with open("out_2015/test.pea") as f:
            lines = f.read().split("\n")[3:]
        got = dict((int(l.split()[0]), float(l.split()[1])) for l in lines if l.strip())
        for k, link in enumerate(ids):
            self.assertAlmostEqual(got[link], v[k], places=3)


@helpers.requires_library
class TestErrors(helpers.InExamples):

    def test_missing_global_file(self):
        with self.assertRaises(FileNotFoundError):
            Simulation("nope.gbl")

    def test_missing_input_file(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.parameters.path = "missing.prm"
        cfg.write("m.gbl")
        with self.assertRaises(FileNotFoundError) as e:
            Simulation("m.gbl")
        self.assertIn("missing.prm", str(e.exception))

    def test_missing_output_folder(self):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.hydrographs.path = "no_such_folder/test.dat"
        cfg.write("m.gbl")
        with self.assertRaises(FileNotFoundError):
            Simulation("m.gbl")

    def test_closed(self):
        sim = Simulation("test_2015.gbl")
        sim.close()
        sim.close()                                     # twice is harmless
        with self.assertRaises(AsynchError):
            sim.advance()

    def test_not_loaded(self):
        with Simulation("test_2015.gbl", load=False) as sim:
            with self.assertRaises(AsynchError):
                sim.states
            with self.assertRaises(AsynchError):
                sim.advance()


@helpers.requires_library
class TestLargeNetwork(unittest.TestCase):
    """B-06: more than 65 535 links (the count was stored in 16 bits)."""

    def test_70000_links(self):
        import tempfile
        sys.path.insert(0, os.path.join(helpers.REPO, "tests", "data_generators"))
        from make_synthetic_network import write_network
        tmp = tempfile.mkdtemp()
        old = os.getcwd()
        try:
            folder = os.path.join(tmp, "big")
            n = write_network(folder, 70000, minutes=10)
            os.chdir(folder)
            with Simulation("big.gbl") as sim:
                self.assertEqual(n, 70000)
                self.assertEqual(sim.num_links, 70000)
                self.assertEqual(len(sim.link_ids), 70000)
                self.assertEqual(sim.location(70000), sim.num_links - 1 - (sim.link_ids[::-1] == 70000).argmax())
                self.assertEqual(len(sim.parents(1)), 10)        # 9 side streams + the next reach
                sim.advance()
                self.assertEqual(sim.states.shape, (70000, 3))
                self.assertTrue(np.all(np.isfinite(sim.states)))
        finally:
            os.chdir(old)
            shutil.rmtree(tmp, ignore_errors=True)


@helpers.requires_library
@unittest.skipUnless(helpers.has_mpirun(), "mpirun not found")
class TestMPI(helpers.InExamples):
    """Two processes: every process sees all states; results agree with one process within the tolerance
    of the solver (asynchronous runs are not bit-reproducible across process counts, R-05)."""

    CODE = """
import numpy as np
from asynch import Simulation
with Simulation("test_2015.gbl") as sim:
    sim.advance()
    s = sim.states
    t, v = sim.peaks
    local = sim.num_links_local
    owners = [sim.owner(l) for l in sim.link_ids]
    np.save("states_%d.npy" % sim.rank, s)
    print("rank", sim.rank, "of", sim.num_procs, "local", local, "owners", sorted(set(owners)))
"""

    def test_two_processes(self):
        with Simulation("test_2015.gbl") as sim:
            sim.advance()
            ref = sim.states
        proc = helpers.run_python(self.CODE, self.dir, np=2)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("rank 0 of 2", proc.stdout)
        self.assertIn("rank 1 of 2", proc.stdout)
        self.assertIn("owners [0, 1]", proc.stdout)
        s0, s1 = np.load("states_0.npy"), np.load("states_1.npy")
        np.testing.assert_array_equal(s0, s1)                   # gathered on every process
        np.testing.assert_allclose(s0, ref, rtol=1e-3, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
