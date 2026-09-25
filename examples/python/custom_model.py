#!/usr/bin/env python3
"""
A model defined in Python (compiled C code), with a custom output and a custom peak flow format.

This is the example of the old Python interface (asynchdist_custom.py, Python 2), ported to the
`asynch` package. The model is model 190 plus three states that keep track of water:
  s_rain  accumulated rain that reached the surface store [m]
  s_run   accumulated runoff from the surface store [m]
  q_b     baseflow part of the discharge [m3/s]
It is the built-in model 191 without its reservoir option, so the script can check itself against it.

    cd examples
    python3 python/custom_model.py          # writes out_2015/custom.csv and out_2015/custom.pea

The global file is made from test_2015.gbl in Python (no file to edit by hand).
"""
import numpy as np

from asynch import Simulation, Model, GlobalConfig, io
from asynch.config import Forcing, Output

model = Model(
    name="linear_hillslope_extras",
    states=["q", "s_p", "s_a", "s_rain", "s_run", "q_b"],
    global_params=["v_r", "lambda_1", "lambda_2", "RC", "v_h", "v_g", "v_B"],
    params=["A_i", "L_i", "A_h"],                        # from the .prm file: km2, km, km2
    derived_params=["k2", "k3", "invtau", "c_1", "c_2"],
    forcings=["rain", "evap", "reservoir"],              # mm/h, mm/month, (unused here)
    param_factors={"L_i": 1000.0, "A_h": 1e6},           # km -> m, km2 -> m2
    read_initial=["q", "s_p", "s_a"],                    # the .uini gives 3 values
    dense=["q", "q_b"],                                  # downstream links need q and q_b
    nonnegative="discharge",
    area="A_i", hillslope_area="A_h",
)

model.precalculations = """
    k2 = v_h * L_i / A_h * 60.0;                               /* [1/min] */
    k3 = v_g * L_i / A_h * 60.0;                               /* [1/min] */
    invtau = 60.0 * v_r * pow(A_i, lambda_2) / ((1.0 - lambda_1) * L_i);
    c_1 = RC * (0.001 / 60.0);                                 /* mm/h -> m/min, fast runoff part */
    c_2 = (1.0 - RC) * (0.001 / 60.0);                         /* infiltration part */
"""

model.initialize = """
    s_rain = 0.0;
    s_run = 0.0;
    q_b = q;                    /* start with all the discharge as baseflow */
"""

model.equations = """
    double q_pl = k2 * s_p, q_al = k3 * s_a;                    /* hillslope outflows */
    double e_pot = evap * (1e-3 / (30.0 * 24.0 * 60.0));       /* mm/month -> m/min */
    double C_p = 0.0, C_a = 0.0, C_T = 0.0;
    if (e_pot > 0.0) { C_p = s_p / e_pot; C_a = s_a / e_pot; C_T = C_p + C_a; }
    double corr = (C_T > 1.0) ? 1.0 / C_T : 1.0;
    double e_p = corr * C_p * e_pot, e_a = corr * C_a * e_pot;

    double inflow = -q + (q_pl + q_al) * A_h / 60.0;
    for (unsigned int i = 0; i < num_parents; i++) inflow += y_p[i * max_num_dof];
    d_q = invtau * pow(q, lambda_1) * inflow;

    d_s_p = rain * c_1 - q_pl - e_p;
    d_s_a = rain * c_2 - q_al - e_a;

    d_s_rain = rain * c_1;
    d_s_run = q_pl;
    double base = q_al * A_h - q_b * 60.0;
    for (unsigned int i = 0; i < num_parents; i++) base += y_p[i * max_num_dof + 5] * 60.0;
    d_q_b = base * (v_B / L_i);
"""
# The parents are added one by one and (v_B / L_i) is computed first, as in the built-in model, so that
# every operation is rounded the same way. Written with upstream_q and upstream_q_b, the results differ
# from model 191 only in the last bit (about 1e-16).

# Global file: test_2015.gbl with 7 global parameters (v_B = 0.75), a third forcing (none), and outputs
cfg = GlobalConfig.read("test_2015.gbl")
cfg.model = 191
cfg.global_params = cfg.global_params + [0.75]
cfg.forcings.append(Forcing.none())
cfg.outputs = ["Time", "LinkID", "State0", "State5"]
cfg.peakflow_function = "NewClassic"
cfg.hydrographs = Output(2, 5.0, "out_2015/custom.csv")
cfg.peaks.path = "out_2015/custom.pea"
cfg.snapshot.flag = 0
cfg.abstol, cfg.reltol = [1e-3] * 6, [1e-6] * 6
cfg.abstol_dense, cfg.reltol_dense = [1e-3] * 6, [1e-6] * 6
cfg.initial_state.path = "custom_191.uini"
io.write_uini("custom_191.uini", 191, [1e-6, 0.0, 0.0])          # as test.uini, for model 191
cfg.write("custom_191.gbl")


def new_classic(link_id, peak_time, peak, params, global_params, conversion, area_idx):
    """One line of the peak file: the old example wrote twice the link id, to show it is custom."""
    return "%d %.4f %.8f %.8f\n" % (2 * link_id, conversion * params[area_idx], peak_time, peak[0])


with Simulation("custom_191.gbl", model=model, load=False) as sim:
    sim.set_output("LinkID", lambda link_id, t, y: link_id, dtype=int)
    sim.set_peakflow_output("NewClassic", new_classic)
    sim.load()
    sim.run()
    custom = sim.states

with Simulation("custom_191.gbl", load=False) as sim:           # the same, with built-in model 191
    sim.set_output("LinkID", lambda link_id, t, y: link_id, dtype=int)
    sim.set_peakflow_output("NewClassic", new_classic)
    sim.peaks_path = "out_2015/builtin191.pea"
    sim.load()
    sim.advance(write=False)
    builtin = sim.states
    if sim.rank == 0:
        print("states at the end, custom model vs built-in model 191: %s (max difference %g)"
              % ("identical" if np.array_equal(custom, builtin) else "different", np.abs(custom - builtin).max()))
        print("outlet: q = %.6f m3/s, of which baseflow q_b = %.6f m3/s"
              % tuple(custom[sim.location(80)][[0, 5]]))
