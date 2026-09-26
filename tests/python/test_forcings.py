"""Rain given in every file format gives the same simulation.

The same rain, different at every link (so that a mix-up of links would show), is written as a .str file (the
reference), as binary files (global file flag 2), gzipped binary files (flag 6) and irregular binary files (flag 5),
and run on the test network of the examples. The states at the end must be identical.
"""
import os
import unittest

import numpy as np

import helpers
from asynch import Simulation, GlobalConfig, io
from asynch.config import Forcing

BEGIN = 1398902400          # 2014-05-01 00:00 UTC, the start of test_2015.gbl
STEP = 100                  # minutes between rain changes


@helpers.requires_library
class TestForcingFormats(helpers.InExamples):

    def setUp(self):
        super().setUp()
        self.links = list(io.read_rvr("test.rvr"))              # file order = order of the binary files
        # link k (in file order): 40 + k mm/h, then 20 + k, then 0
        self.values = [[40.0 + k for k in range(len(self.links))],
                       [20.0 + k for k in range(len(self.links))],
                       [0.0] * len(self.links)]
        os.makedirs("bin", exist_ok=True)

    def run_with(self, forcing, name):
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.forcings[0] = forcing
        cfg.hydrographs.flag = 0
        cfg.snapshot.flag = 0
        cfg.write(name)
        with Simulation(name) as sim:
            sim.advance(write=False)
            return sim.states, sim.peaks[1]

    def reference(self):
        io.write_str("rain.str", {link: [(i * STEP, self.values[i][k]) for i in range(3)]
                                  for k, link in enumerate(self.links)})
        return self.run_with(Forcing.storm_file("rain.str"), "str.gbl")

    def test_binary(self):
        ref = self.reference()
        io.write_binary_forcing("bin/rain_", {i: self.values[i] for i in range(3)})
        got = self.run_with(Forcing(2, "bin/rain_", increment=10, file_time=float(STEP), first=0, last=2), "bin.gbl")
        np.testing.assert_array_equal(got[0], ref[0])
        np.testing.assert_array_equal(got[1], ref[1])

    def test_gzipped_binary(self):
        ref = self.reference()
        io.write_binary_forcing("bin/rain_", {i: self.values[i] for i in range(3)}, compress=True)
        got = self.run_with(Forcing(6, "bin/rain_", increment=10, file_time=float(STEP), first=0, last=2), "gz.gbl")
        np.testing.assert_array_equal(got[0], ref[0])
        np.testing.assert_array_equal(got[1], ref[1])

    def test_irregular_binary(self):
        ref = self.reference()
        frames = {BEGIN + i * STEP * 60: {link: self.values[i][k] for k, link in enumerate(self.links)
                                          if self.values[i][k] != 0.0}          # zeros may be left out
                  for i in range(3)}
        io.write_irregular_binary_forcing("bin/irr_", frames)
        got = self.run_with(Forcing(5, "bin/irr_", increment=10, file_time=float(STEP), first=BEGIN,
                                    last=BEGIN + 3 * STEP * 60), "irr.gbl")
        np.testing.assert_array_equal(got[0], ref[0])
        np.testing.assert_array_equal(got[1], ref[1])

    def test_missing_binary_file(self):
        """A missing file of the range is reported before the C library would stop every process."""
        io.write_binary_forcing("bin/gap_", {0: self.values[0], 2: self.values[2]})        # no file 1
        cfg = GlobalConfig.read("test_2015.gbl")
        cfg.forcings[0] = Forcing(2, "bin/gap_", increment=10, file_time=float(STEP), first=0, last=2)
        cfg.write("gap.gbl")
        with self.assertRaises(FileNotFoundError) as e:
            Simulation("gap.gbl")
        self.assertIn("bin/gap_<index> for index 1", str(e.exception))

    def test_rain_matters(self):
        """The comparison above is not trivial: another rain gives other states."""
        ref = self.reference()
        io.write_binary_forcing("bin/other_", {0: [10.0] * len(self.links), 1: [0.0] * len(self.links)})
        got = self.run_with(Forcing(2, "bin/other_", increment=10, file_time=float(STEP), first=0, last=1), "o.gbl")
        self.assertGreater(np.abs(got[0] - ref[0]).max(), 1e-3)


if __name__ == "__main__":
    unittest.main()
