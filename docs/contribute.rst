.. _contributing-to-asynch:

Contributing to Asynch
======================

You are here to help on Asynch? Awesome, feel welcome and read the following sections in order to know what and how to work on something. If you get stuck at any point you can create a `ticket on GitHub`_.

.. _ticket on GitHub: https://github.com/Iowa-Flood-Center/asynch/issues

Contributing to development
---------------------------

If you want to deep dive and help out with development on Read the Docs, then first get the project installed locally according to the :ref:`Installation` instruction. After that is done we suggest you have a look at tickets in our issue tracker that are labelled `Good First Bug`_. These are meant to be a great way to get a smooth start and won't put you in front of the most complex parts of the system.

If you are up to more challenging tasks with a bigger scope, then there are a set of tickets with a `Enhancement`_ tag. These tickets have a general overview and description of the work required to finish. If you want to start somewhere, this would be a good place to start. That said, these aren't necessarily the easiest tickets. They are simply things that are explained. If you still didn't find something to work on, search for the `Sprintable`_ label. Those tickets are meant to be standalone and can be worked on ad-hoc.

When contributing code, then please follow the standard Contribution Guidelines set forth at `contribution-guide.org`_.

.. _Enhancement: https://github.com/Iowa-Flood-Center/asynch/issues?direction=desc&labels=enhancement&page=1&sort=updated&state=open
.. _Good First Bug: https://github.com/rtfd/readthedocs.org/issues?q=is%3Aopen+is%3Aissue+label%3A%22Good+First+Bug%22
.. _Sprintable: https://github.com/rtfd/readthedocs.org/issues?q=is%3Aopen+is%3Aissue+label%3ASprintable
.. _contribution-guide.org: http://www.contribution-guide.org/#submitting-bugs

Keeping the documentation updated
---------------------------------

When a change affects users (input formats, models, global file options, the Python package, ...), update the
documentation in the same commit, and record the change in ``CHANGELOG.md``.

Documentation structure
~~~~~~~~~~~~~~~~~~~~~~~

The documentation lives in ``docs/`` and is built with `Sphinx <https://www.sphinx-doc.org>`__:

* ``docs/guide/*.md``: the guide (Markdown, read by MyST; it also reads well on GitHub);
* ``docs/*.rst``: the reference manual (reStructuredText);
* the Python API pages are generated from the docstrings of ``python/asynch`` (autodoc), and the C API pages from the
  comments of ``src/asynch_interface.h``, ``src/asynch_api.h`` and ``src/models/model.h`` (Doxygen and breathe);
* ``docs/conf.py`` is the configuration; ``docs/index.md`` the home page and table of contents.

Working locally
~~~~~~~~~~~~~~~

.. code-block:: sh

   python3 -m venv ~/docs-venv
   ~/docs-venv/bin/pip install -r docs/requirements.txt
   sudo apt-get install doxygen                 # optional: without it the C API pages show a note
   ~/docs-venv/bin/sphinx-build -b html docs docs/_build/html

Open ``docs/_build/html/index.html`` in a browser.

Publishing
~~~~~~~~~~

The GitHub Actions workflow ``.github/workflows/docs.yml`` builds the documentation on every push and publishes it
with GitHub Pages. It needs, once, *Settings > Pages > Source: GitHub Actions* in the repository.


Managing releases
-----------------

Versions follow `semantic versioning <https://semver.org/>`__: ``x.y.z``. To release version ``x.y.z``:

1. Set the version in ``configure.ac`` (``AC_INIT([asynch], [x.y.z], ...)``), ``python/pyproject.toml`` and
   ``python/asynch/__init__.py`` (``__version__``).
2. In ``CHANGELOG.md``, rename the section ``[Unreleased]`` to ``[x.y.z] - YYYY-MM-DD``, with a short summary of the
   version at its top, and start a new empty ``[Unreleased]`` section. Add the version to :doc:`release_notes`: what
   changes for a user, breaking changes first.
3. Build and run ``make check`` (:doc:`guide/09_reproducibility`); compare the examples with the previous version with
   ``tests/regression/run_examples.py --compare-to``.
4. Commit, then create and push the tag:

   .. code-block:: sh

      git tag -a vx.y.z -m "ASYNCH x.y.z"
      git push origin vx.y.z

The workflow ``.github/workflows/release.yml`` then checks that the tag matches ``configure.ac``, builds ASYNCH, runs
``make check``, and publishes the GitHub release. Its description is the summary of the version from
``CHANGELOG.md`` with the title of every change. Three files are attached:

* ``asynch-x.y.z.tar.gz``, made by ``make dist``: the sources with a ready ``configure`` script, which build without
  autotools (``./configure && make && make check``);
* the Python package as a wheel (it uses the ``libasynch.so`` built from the sources);
* the documentation website as a zip file, to read offline.
