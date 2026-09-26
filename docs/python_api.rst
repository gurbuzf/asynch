Python API reference
====================

Generated from the documentation strings of the package ``asynch`` (folder ``python/`` of the repository). The
tutorial is :doc:`guide/10_python`. Import names::

    from asynch import Simulation, Model, GlobalConfig, io

Every method of :class:`~asynch.Simulation` that says *collective* must be called by every MPI process.

Simulation
----------

.. autoclass:: asynch.Simulation
   :members:

.. autoexception:: asynch.AsynchError

Model
-----

.. automodule:: asynch.model
   :no-members:

.. autoclass:: asynch.Model
   :members: c_source, compile, index, all_params

.. autoexception:: asynch.ModelError

Global files
------------

.. automodule:: asynch.config
   :no-members:

.. autoclass:: asynch.GlobalConfig
   :members: read, parse, text, write, copy

.. autoclass:: asynch.Forcing
   :members: none, storm_file, uniform, monthly

.. autoclass:: asynch.Output
.. autoclass:: asynch.PeakOutput
.. autoclass:: asynch.Snapshot
.. autoclass:: asynch.Selection
.. autoclass:: asynch.FileRef

Input and output files
----------------------

.. automodule:: asynch.io
   :members:

Low level: the C functions
--------------------------

.. automodule:: asynch._lib
   :members: find_library, lib, mpi_init
