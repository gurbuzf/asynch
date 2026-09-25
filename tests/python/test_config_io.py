"""Tests of asynch.config (global files) and asynch.io (input and output files). No C library needed."""
import glob
import os
import tempfile
import unittest

import numpy as np

import helpers
from asynch import io
from asynch.config import GlobalConfig, Forcing, Output, PeakOutput, Snapshot, Selection, FileRef

ALL_GBL = sorted(glob.glob(os.path.join(helpers.EXAMPLES, "*.gbl")) +
                 glob.glob(os.path.join(helpers.EXAMPLES, "more", "*", "*.gbl")))


def value_lines(text):
    """The lines ASYNCH reads: not empty, not starting with %; the text after a % is a comment."""
    out = []
    for l in text.splitlines():
        if l.strip() and not l.startswith("%"):
            out.append(l.split("%")[0].split())
            if l.startswith("#"):         # end mark: ASYNCH reads nothing after it
                break
    return out


def _read(path):
    with open(path) as f:
        return f.read()


class TestGlobalConfig(unittest.TestCase):

    def test_examples_found(self):
        self.assertGreaterEqual(len(ALL_GBL), 9)

    def test_read_example(self):
        c = GlobalConfig.read(os.path.join(helpers.EXAMPLES, "test_2015.gbl"))
        self.assertEqual(c.model, 190)
        self.assertEqual(c.begin, "2014-05-01 00:00")
        self.assertEqual(c.end, "2014-05-01 05:00")
        self.assertEqual(c.outputs, ["Time", "State0"])
        self.assertEqual(c.global_params, [0.33, 0.2, -0.1, 0.33, 0.1, 2.2917e-5])
        self.assertEqual(c.topology, FileRef(0, "test.rvr"))
        self.assertEqual(c.initial_state, FileRef(1, "test.uini"))
        self.assertEqual(c.forcings, [Forcing(1, "test.str"), Forcing(7, "evap.mon", first=1398902400, last=1588291200)])
        self.assertEqual(c.hydrographs, Output(1, 5.0, "out_2015/test.dat"))
        self.assertEqual(c.peaks, PeakOutput(1, "out_2015/test.pea"))
        self.assertEqual(c.hydrograph_links, Selection(1, "test.sav"))
        self.assertEqual(c.peak_links, Selection(3))
        self.assertEqual(c.snapshot, Snapshot(1, None, "out_2015/test.rec"))
        self.assertEqual((c.facmin, c.facmax, c.fac), (0.1, 10.0, 0.9))
        self.assertIsNone(c.rkd)
        self.assertEqual(c.solver, 2)
        self.assertEqual(c.abstol, [1e-3, 1e-3, 1e-3])
        self.assertEqual(c.reltol_dense, [1e-6, 1e-6, 1e-6])

    def test_round_trip_every_example(self):
        """read -> write -> read gives the same settings, and the same values in the order ASYNCH reads them."""
        for path in ALL_GBL:
            with self.subTest(gbl=os.path.relpath(path, helpers.EXAMPLES)):
                original = _read(path)
                c = GlobalConfig.parse(original)
                text = c.text()
                self.assertEqual(GlobalConfig.parse(text), c)
                a, b = value_lines(original), value_lines(text)
                self.assertEqual(len(a), len(b))
                for la, lb in zip(a, b):
                    # same words, numbers compared as numbers ("5.0" == "5", ".1" == "0.1")
                    self.assertEqual(len(la), len(lb), (la, lb))
                    for wa, wb in zip(la, lb):
                        try:
                            self.assertEqual(float(wa), float(wb))
                        except ValueError:
                            self.assertEqual(wa, wb)

    def test_rkd_example(self):
        c = GlobalConfig.read(os.path.join(helpers.EXAMPLES, "test_rkd.gbl"))
        self.assertEqual(c.rkd, "test.rkd")
        self.assertIn("1 test.rkd", c.text())

    def test_build_from_scratch(self):
        c = GlobalConfig(model=254, begin="2020-01-01 00:00", end=1577923200, global_params=[1.0, 2.0],
                         forcings=[Forcing.uniform("r.ustr"), Forcing.monthly("e.mon", 0, 10),
                                   Forcing(2, "bins/rain", 10, 5.0, 100, 200), Forcing.none()],
                         hydrographs=Output(5, 15.0, "o.h5"), snapshot=Snapshot(4, 60.0, "snap.h5"),
                         abstol=[1e-4] * 7, reltol=[1e-6] * 7, abstol_dense=[1e-4] * 7, reltol_dense=[1e-6] * 7)
        again = GlobalConfig.parse(c.text())
        self.assertEqual(again, c)
        self.assertEqual(again.end, 1577923200)
        self.assertEqual(again.forcings[2], Forcing(2, "bins/rain", 10, 5.0, 100, 200))
        self.assertEqual(again.snapshot, Snapshot(4, 60.0, "snap.h5"))

    def test_database_blocks(self):
        c = GlobalConfig(forcings=[Forcing(3, "rain.dbc", 10, 60.0, 1000, 2000), Forcing(9, "r.dbc", increment=5, first=10, last=20)],
                         hydrographs=Output(3, 5.0, "out.dbc", "hydro_table"), peaks=PeakOutput(2, "p.dbc", "peaks"),
                         snapshot=Snapshot(2, None, "s.dbc", "snaps"), initial_state=FileRef(3, "ini.dbc", "1500000000"))
        self.assertEqual(GlobalConfig.parse(c.text()), c)

    def test_errors(self):
        with self.assertRaises(TypeError):
            GlobalConfig(no_such_setting=1)
        text = GlobalConfig().text()
        with self.assertRaises(ValueError):
            GlobalConfig.parse(text.replace("# %End of file", ""))           # missing end mark
        with self.assertRaises(ValueError):
            GlobalConfig.parse(text[:200])                                   # truncated
        with self.assertRaises(ValueError):
            Forcing(12, "x").lines()


class TestIO(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def path(self, name):
        return os.path.join(self.tmp, name)

    def test_rvr_prm_round_trip(self):
        net = {1: [2, 3], 2: [], 3: [4], 4: []}
        io.write_rvr(self.path("n.rvr"), net)
        self.assertEqual(io.read_rvr(self.path("n.rvr")), net)
        prm = {1: [1.5, 0.2, 0.1], 2: [0.1, 0.3, 0.1], 3: [0.3, 0.5, 0.2], 4: [0.1, 0.1, 0.1]}
        io.write_prm(self.path("n.prm"), prm)
        back = io.read_prm(self.path("n.prm"))
        self.assertEqual(sorted(back), [1, 2, 3, 4])
        for k in prm:
            np.testing.assert_array_equal(back[k], prm[k])

    def test_read_example_network(self):
        rvr = io.read_rvr(os.path.join(helpers.EXAMPLES, "test.rvr"))
        self.assertEqual(len(rvr), 11)
        n_parents = sum(len(v) for v in rvr.values())
        self.assertEqual(n_parents, 10)                    # a tree: every link but the outlet has one child
        prm = io.read_prm(os.path.join(helpers.EXAMPLES, "test.prm"))
        self.assertEqual(sorted(prm), sorted(rvr))
        self.assertTrue(all(len(v) == 3 for v in prm.values()))

    def test_forcing_writers(self):
        io.write_ustr(self.path("r.ustr"), [(0, 20.0), (30, 10.0), (60, 0.0)])
        self.assertEqual(_read(self.path("r.ustr")).split(), "3 0.0 20.0 30.0 10.0 60.0 0.0".split())
        io.write_str(self.path("r.str"), {1: [(0, 1.0)], 2: [(0, 2.0), (10, 0.0)]})
        tok = _read(self.path("r.str")).split()
        self.assertEqual(tok[:5], ["2", "1", "1", "0.0", "1.0"])
        io.write_mon(self.path("e.mon"), range(12))
        self.assertEqual(len(_read(self.path("e.mon")).split()), 12)
        with self.assertRaises(ValueError):
            io.write_mon(self.path("bad.mon"), [1, 2])

    def test_initial_state_writers(self):
        io.write_uini(self.path("a.uini"), 190, [1e-6, 0, 0])
        self.assertEqual(_read(self.path("a.uini")).split(), ["190", "0.0", "1e-06", "0.0", "0.0"])
        io.write_ini(self.path("a.rec"), 190, {1: [1, 2, 3], 5: [4, 5, 6]}, time=10)
        rec = io.read_rec(self.path("a.rec"))
        np.testing.assert_array_equal(rec[5], [4, 5, 6])
        io.write_sav(self.path("a.sav"), [3, 1])
        self.assertEqual(_read(self.path("a.sav")), "3\n1\n")

    def test_read_reference_outputs(self):
        ref = os.path.join(helpers.EXAMPLES, "results")
        dat = io.read_hydrographs(os.path.join(ref, "test.dat"))
        self.assertIn(80, dat)
        self.assertEqual(dat[80].shape[1], 2)
        pea = io.read_pea(os.path.join(ref, "test.pea"))
        self.assertEqual(len(pea), 11)
        rec = io.read_snapshot(os.path.join(ref, "test.rec"))
        self.assertEqual(len(rec), 11)
        self.assertEqual(len(rec[80]), 3)
        with self.assertRaises(ValueError):
            io.read_hydrographs("x.txt")


if __name__ == "__main__":
    unittest.main()
