Releases Notes
==============

ASYNCH release notes provide information on the features and improvements in each release. This page includes release notes for major releases and minor (bugfix) releases. If you are upgrading from an earlier version of ASYNCH, you will find essential information in the Breaking Changes associated with the relevant release notes.

Version 1.5
-----------

Released 2026-09-26. Every change, with its effect on numerical results, is in the :doc:`changelog`; the problems found
and fixed are explained in :doc:`guide/07_improvements_explained`.

Breaking Changes
~~~~~~~~~~~~~~~~

* **Model 254 results change.** The baseflow equation of 2015 is restored: a line added in 2021 kept the baseflow state
  ``q_b`` at 0 (S-02). Total discharge changes by at most 0.0003 m³/s on Clear Creek; the baseflow output was wrong since
  2021. Apart from models 105 and 263 (below), all other models give the same results as 1.4.3.
* **Runs stop earlier, with a message, instead of failing silently:** a missing or read-only output folder (checked
  before computing; exit code 1), a numerical solver index other than 0, 1 or 2, a model number without equations
  (200, 260, 300, 301, 315, 607, 2000), a link with more than 16 upstream links. An initial-state file with fewer values
  than the model has states gives a warning, and the missing values are 0 (they came from random memory).
* **Model 263** reads 16 values per link from its parameter file. In **models 105 and 263**, the states that have no
  equation keep their initial values (their results depended on leftover memory, B-26).
* **C API:** ``Asynch_Get_Num_Links`` returns ``unsigned int`` (it returned ``unsigned short``, wrong above 65 535
  links). The library is also built as a shared library, ``libasynch.so``.
* **Python:** the old interface (``py/``, ``asynchdist.py``) is replaced by the package ``asynch`` (``python/``).

New Features
~~~~~~~~~~~~

* A ready-made wheel for Linux (x86-64, glibc 2.31 or newer), attached to the release: ``pip install`` it and the
  Python package, the library and the ``asynch`` program are there, with nothing to compile; MPI comes with it (the
  ``mpich`` package of PyPI, with ``mpiexec``).
* The Python package ``asynch``, installed with ``pip`` or ``make install-python``: run a global file (identical output
  files), advance step by step, read and change states and parameters, add outputs, read and write every file format,
  and define new models with equations in C, Numba or Python (:doc:`guide/10_python`, :doc:`python_api`). Works with
  MPI (``mpirun -n 4 python3 script.py``) and mpi4py.
* ``asynch_api.h``: a C interface for other languages and for custom models defined outside the source code.
* ``make check`` runs 23 C unit tests, 70 Python tests and every example against the reference results of the original
  repository (:doc:`guide/09_reproducibility`). GitHub Actions run it on every push.
* Per-link solver settings (``.rkd`` files) and solver methods 0 and 1 work (they did not, B-14 and B-13).
* A ``Dockerfile`` for a ready-made environment, and this documentation website.

Version 1.4
-----------

Breaking Changes
~~~~~~~~~~~~~~~~

The signature of the function that implements the differential equations has an extra parameter ``max_num_dim``. This is required because data assimilation uses a variable number of equations at links, the maximum number of degree of freedom beeing known at runtime.

.. code-block:: c

  typedef void (DifferentialFunc) (
    double t,
    const double * const y_i, unsigned int num_dof,
    const double * const y_p, unsigned short num_parents, unsigned int max_num_dof,
    const double * const global_params,
    const double * const params,
    const double * const forcing_values,
    const QVSData * const qvs,
    int state,
    void *user,
    double *ans);

New Features
~~~~~~~~~~~~

This release introduces :ref:`Data Assimilation`.

An additional, more compact HDF5 format for the time series is available, see option ``6`` of :ref:`Time Series Location`.

Three new models are available:

Constant Runoff Model ``195``:
  * based on ``190`` with precipitation forcing replaced by runoff and infiltration forcings to describe spatial variability of such processes, and including an additional state for rainfall accumulation.

Top Layer Model ``256``:
  * based on ``254``;
  * has a new state variable ``ans[7]`` : accumulated evapotranspiration;
  * has one more toplayer storage to link parameter ``k_tl = global_params[12]``;
  * has a flux component from toplayer storage to channel that represents the interflow :math:`q_{tl} = k_{tl} s_t`.

Top Layer Model ``257``:
  * based on ``256`` but channel velocity is spatialized as a function of the Horton order;
  * the Horton order is an additional local parameter.

Version 1.3
-----------

This release is the result of a loong run profiling and optimization work.

Memory footprint improvements, better data structure reduce the memory usage typically by a factor two. If you have memory available you may want to increase the number of buffers, see :ref:`Buffer Sizes`.

Performance improvements, ASYNCH runs about 30% faster.

Version 1.2
-----------

Breaking Changes
~~~~~~~~~~~~~~~~

The global file structure has changed. The time of the simulation is now given in absolute time, see :ref:`Simulation period`.

The snapshots in HDF5 format has changed, see :ref:`Ini HDF5 Files`.

New Features
~~~~~~~~~~~~

Time series outputs can be written in HDF5 format, see :ref:`Time Series Location`.
