#!/usr/bin/env python3
"""
Change a parameter from Python and rerun: the peak flow at the outlet for several runoff coefficients.

    cd examples
    python3 python/sensitivity.py

Each run starts from the initial state of the global file. Changing the global parameters also recomputes
the parameters every link derives from them (here c_1 = RC * 0.001/60 of model 190).
"""
import numpy as np

from asynch import Simulation

outlet = 80
lines = ["RC     peak at link %d [m3/s]   time of peak [h]" % outlet]
for rc in (0.2, 0.33, 0.5, 0.7):
    with Simulation("test_2015.gbl") as sim:
        g = sim.global_params
        g[3] = rc                                      # v_r, lambda_1, lambda_2, RC, v_h, v_g
        sim.global_params = g
        sim.advance(write=False)                       # no output files
        t, q = sim.peaks
        k = sim.location(outlet)
        lines.append("%.2f %24.4f %18.2f" % (rc, q[k], t[k] / 60.0))
        rank = sim.rank
if rank == 0:                                          # with mpirun, every process runs this script
    print("\n".join(lines))
