"""Every built-in model that ASYNCH can integrate runs a one-hour simulation on a 3-link network.

The inputs are generic, not physical: distinct parameter values (0.2, 0.237, 0.274, ...), all initial states 0.1,
1 mm/h of every forcing for 30 minutes. The test checks that each model loads, integrates to the end and keeps
finite states; it exercises the setup, equations and time-step routines of every model, including those with
algebraic states (models 21-23, 40, 255, 261, 262). It does not check that the numbers are hydrologically right:
the examples and their reference results do that for the models they use.
"""
import os
import shutil
import tempfile
import unittest

import numpy as np

import helpers
from asynch import Simulation, GlobalConfig, io
from asynch.config import FileRef, Forcing, Output, Selection

MODELS = [0, 1, 2, 3, 4, 5, 6, 15, 19, 20, 21, 22, 23, 40, 60, 101, 105, 190, 191, 192, 193, 194, 195, 196,
          219, 225, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 262, 263, 264, 400, 401, 402, 403, 404,
          405, 604, 605, 606, 608, 609, 654]

# These run, but with the generic parameters above they become so stiff (e.g. model 601: 1 700 m3/s after one
# minute on a 0.2 km2 catchment) that one hour takes minutes, or (model 30) the step size falls below 1e-12 min,
# which debug builds stop on: they need realistic parameters.
NEED_REALISTIC_PARAMETERS = [30, 261, 601, 602, 603]

# No equations in ASYNCH (refused by Initialize_Model; see tests/check_asynch.c): 200, 260, 300, 301, 315, 607, 2000.


@helpers.requires_library
class TestEveryModelRuns(unittest.TestCase):

    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix="asynch-models-")
        os.chdir(self.tmp)
        self.net = {1: [2, 3], 2: [], 3: []}
        io.write_rvr("n.rvr", self.net)
        io.write_ustr("f.ustr", [(0, 1.0), (30, 0.0)])

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_model(self, uid):
        cfg = GlobalConfig(
            model=uid, begin="2020-07-01 00:00", end="2020-07-01 01:00",
            global_params=[0.3 + 0.1 * i for i in range(40)],        # more than any model needs
            topology=FileRef(0, "n.rvr"), parameters=FileRef(0, "n.prm"), initial_state=FileRef(1, "n.uini"),
            forcings=[Forcing.uniform("f.ustr")] * 10,               # more than any model needs
            hydrographs=Output(0), peak_links=Selection(0),
            abstol=[1e-3] * 12, reltol=[1e-3] * 12, abstol_dense=[1e-3] * 12, reltol_dense=[1e-3] * 12)
        cfg.write("n.gbl")
        io.write_uini("n.uini", uid, [0.1] * 32)                     # extra values are not read
        io.write_prm("n.prm", {k: [1.0] for k in self.net})         # placeholder, to read the sizes
        with Simulation("n.gbl", load=False) as sim:
            n = sim.num_disk_params
        p = [0.2 + 0.037 * i for i in range(n)]
        if uid == 257:
            p[3] = 3.0                                               # a stream order, 1 to 10
        io.write_prm("n.prm", {k: p for k in self.net})
        with Simulation("n.gbl") as sim:
            sim.advance(write=False)
            self.assertEqual(sim.time, 60.0)
            return sim.states

    def test_models(self):
        for uid in MODELS:
            with self.subTest(model=uid):
                states = self.run_model(uid)
                self.assertEqual(states.shape[0], 3)
                self.assertTrue(np.all(np.isfinite(states)), "model %d: %s" % (uid, states))


if __name__ == "__main__":
    unittest.main()
