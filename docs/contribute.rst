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

Once you are happy with your changes in the ``develop`` branch and ran a couple of test simulations, here is the procedure to release a new version ``x.y.z`` (e.g. ``1.5.0``):

Branch
~~~~~~

Create a branch for the release following the ``release-x.y.z`` naming scheme and `semantic versionning <http://semver.org/>`__ rules :

.. code-block:: sh

  git branch release-x.y.z

Edit
~~~~

Edit the release notes (``doc/release_notes.rst``).

Edit ``configure.ac`` to bump the version number:

.. code::

  AC_INIT([asynch], [x.y.z], [samuel-debionne@uiowa.edu])

Commit your changes.

.. code-block:: sh

  git add configure.ac doc/release_notes.rst
  git commit -m "Bump version number to x.y.z"
  git push

Generate the tarball
~~~~~~~~~~~~~~~~~~~~

In a new empty folder, run the following commands to clone the repository, generate the configure script and the tarball.

.. code-block:: sh

  git clone https://github.com/Iowa-Flood-Center/asynch.git
  git checkout release-x.y.z
  autoreconf -i
  mkdir build && cd build
  export TAR_OPTIONS="--owner=0 --group=0 --numeric-owner"
  ../configure
  make dist

That should generate a ``release-x.y.z.tar.gz`` that needs to be tested.

Test the tarball
~~~~~~~~~~~~~~~~

In a new empty folder, follow  the instructions in :doc:`guide/01_setup`:

.. code-block:: sh

  tar xf release-x.y.z.tar.gz
  cd release-x.y.z
  mkdir build && cd build
  ../configure CFLAGS="-O2 -DNDEBUG"
  make
  make check
  make install

Adjust the release branch if there is any problem with the build (e.g. missing header file).

Release on Github
~~~~~~~~~~~~~~~~~

Merge the release branch ``release-x.y.z`` to ``master``. The easiest way is to submit a new Pull Request. The *base* branch should be ``Iowa-Flood-Center/asynch`` / ``master`` and the *compare* branch ``Iowa-Flood-Center/asynch`` / ``release-x.y.z``.


Review your Pull Request, or better let someone else do the review. If everything looks good, and the GitHub Actions checks (tests and documentation, ``.github/workflows``) pass, do a *"Merge and Squash"*.

You can safely delete the release branch at this point.

Click on *"Draft a new release"* in `Releases <https://github.com/Iowa-Flood-Center/asynch/releases>`_:

=============== ===============
Field           Value
=============== ===============
Tag version     vx.y.z (v1.5.0)
Release title   Pick a city in Iowa
Description     A short version of the release notes
=============== ===============

Attach the tarball that was generated in the previous step. This is usefull because the tarball does not require the target computer to have autotools installed.

Ready? *"Publish Release"*! Every followers of the repo get notified of the new version. Good job!
