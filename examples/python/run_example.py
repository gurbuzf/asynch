#!/usr/bin/env python3
"""
Run an example global file from Python and look at the results, without reading any output file.

    cd examples
    python3 python/run_example.py                 # test_2015.gbl
    python3 python/run_example.py clearcreek_2015.gbl

Writes the same output files as `asynch test_2015.gbl`, and prints the peak flow of the five largest links.
"""
import sys

import numpy as np

from asynch import Simulation

gbl = sys.argv[1] if len(sys.argv) > 1 else "test_2015.gbl"

with Simulation(gbl) as sim:
    if sim.rank == 0:                                  # with mpirun, every process runs this script
        print("%s: model %d, %d links, %g minutes" % (gbl, sim.model_uid, sim.num_links, sim.duration_total))
    sim.run()                                          # integrate, then write the outputs of the global file
    peak_time, peak_q = sim.peaks
    ids = sim.link_ids
    if sim.rank == 0:
        print("link   peak discharge [m3/s]   time of peak [h]")
        for k in np.argsort(peak_q)[::-1][:5]:
            print("%-6d %20.4f %18.2f" % (ids[k], peak_q[k], peak_time[k] / 60.0))
