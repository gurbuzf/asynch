Python API
==========

ASYNCH is used from Python through the package in the ``python/`` folder of the repository. It loads the
shared library ``libasynch.so`` (built and installed with ASYNCH) with ``ctypes``. The full description, with
installation, tutorial and reference, is the chapter *Using ASYNCH from Python* of the guide:
``docs/guide/10_python.md``.

The previous interface (``asynch_py``, ``asynchdist.py``), written for Python 2, no longer worked with the C
library and has been removed.

Running a global file:

.. code-block:: python

  from asynch import Simulation

  with Simulation("test_2015.gbl") as sim:   # read the file, load network, parameters, states, forcings
      sim.run()                              # integrate, then write the outputs of the global file
      q = sim.states[:, 0]                   # discharge of every link (order of sim.link_ids)
      peak_time, peak_q = sim.peaks

Changing parameters and continuing:

.. code-block:: python

  with Simulation("test_2015.gbl") as sim:
      sim.advance(60)                        # the first hour
      g = sim.global_params
      g[3] = 0.5                             # model 190: runoff coefficient
      sim.global_params = g                  # derived link parameters are recomputed
      sim.run()

A custom model, with equations in C compiled on the fly:

.. code-block:: python

  from asynch import Model, Simulation

  m = Model(states=["q"], global_params=["k"], params=["A_h"], forcings=["rain"], param_factors={"A_h": 1e6})
  m.equations = """
      d_q = (upstream_q + rain * A_h * (0.001 / 3600.0) - q) / k;
  """
  with Simulation("my_network.gbl", model=m) as sim:
      sim.run()

Custom time series outputs (``Simulation.set_output``), custom peak flow formats
(``Simulation.set_peakflow_output``), global files built in Python (``asynch.config.GlobalConfig``), readers and
writers of the file formats (``asynch.io``) and MPI runs (``mpirun -n 4 python3 script.py``) are described in the guide.
