#!/usr/bin/env python3
"""
Everything from Python: a new network, its input files, the global file and a new model.

A chain of 5 links (link 1 is the outlet), each a linear reservoir dq/dt = (inflow - q) / k, with
inflow = discharge from upstream + rain falling on the hillslope. 20 mm/h of rain falls for one hour.
The script writes its files into a new folder, runs, and compares the outlet with the exact solution of
the rain-free recession for the first link (a check that the solver does what the equations say).

    python3 python/new_network.py [folder]
"""
import math
import os
import sys

from asynch import Simulation, Model, GlobalConfig, io
from asynch.config import FileRef, Forcing, Output, PeakOutput, Selection

folder = sys.argv[1] if len(sys.argv) > 1 else "chain_example"
os.makedirs(folder, exist_ok=True)
os.chdir(folder)

n = 5
io.write_rvr("chain.rvr", {k: ([k + 1] if k < n else []) for k in range(1, n + 1)})    # k+1 flows into k
io.write_prm("chain.prm", {k: [2.0] for k in range(1, n + 1)})                         # hillslope area [km2]
io.write_uini("chain.uini", 0, [0.0])                                                    # dry start
io.write_ustr("rain.ustr", [(0, 20.0), (60, 0.0)])                                       # mm/h
io.write_sav("outlet.sav", [1])

cfg = GlobalConfig(
    model=0, begin="2020-06-01 00:00", end="2020-06-01 06:00",
    outputs=["Time", "State0"], global_params=[30.0],                                    # k = 30 min
    topology=FileRef(0, "chain.rvr"), parameters=FileRef(0, "chain.prm"),
    initial_state=FileRef(1, "chain.uini"), forcings=[Forcing.uniform("rain.ustr")],
    hydrographs=Output(2, 10.0, "chain.csv"), hydrograph_links=Selection(1, "outlet.sav"),
    peaks=PeakOutput(1, "chain.pea"), peak_links=Selection(3),
    abstol=[1e-8], reltol=[1e-8], abstol_dense=[1e-8], reltol_dense=[1e-8])
cfg.write("chain.gbl")

model = Model(name="linear_reservoir", states=["q"], global_params=["k"], params=["A_h"], forcings=["rain"],
              param_factors={"A_h": 1e6}, area="A_h", hillslope_area="A_h")
model.equations = """
    double inflow = upstream_q + rain * A_h * (0.001 / 3600.0);    /* mm/h on m2 -> m3/s */
    d_q = (inflow - q) / k;
"""

with Simulation("chain.gbl", model=model) as sim:
    sim.advance(until=60)                              # end of the rain
    q_top_60 = sim.state(n)[1][0]                      # most upstream link: no inflow from upstream
    sim.run()
    t, q = sim.peaks
    for link in range(1, n + 1):
        k = sim.location(link)
        print("link %d: peak %.4f m3/s at %.1f min" % (link, q[k], t[k]))
    # the most upstream link is a single reservoir: exact solution during the rain
    Q = 20.0 * 2e6 * 0.001 / 3600.0
    print("link %d at 60 min: %.8f m3/s (exact %.8f)" % (n, q_top_60, Q * (1 - math.exp(-60 / 30.0))))
print("files in %s: %s" % (os.getcwd(), ", ".join(sorted(os.listdir(".")))))
