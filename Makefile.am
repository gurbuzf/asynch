AUTOMAKE_OPTIONS = subdir-objects

SUBDIRS = src tests tools
ACLOCAL_AMFLAGS = -I m4
EXTRA_DIST = LICENSE README.md CHANGELOG.md Dockerfile examples python docs

# The Python package (python/asynch). `make install` installs the C library it uses; this installs the package
# itself into the Python environment of PYTHON_FOR_ASYNCH (a virtual environment, or add PIP_FLAGS=--user):
#   make install-python                         # python3 -m pip install <source>/python
#   make install-python PYTHON_FOR_ASYNCH=~/venv/bin/python
PYTHON_FOR_ASYNCH = python3
PIP_FLAGS =
install-python:
	$(PYTHON_FOR_ASYNCH) -m pip install --no-build-isolation $(PIP_FLAGS) $(abs_top_srcdir)/python

.PHONY: install-python

# the source archive (make dist) holds sources only: no caches, builds or generated documentation
dist-hook:
	rm -f $(distdir)/examples/.gitignore
	rm -rf $(distdir)/python/build $(distdir)/docs/_build $(distdir)/docs/.doxygen
	find $(distdir) \( -name __pycache__ -o -name '*.egg-info' -o -name '*.pyc' \) -prune -exec rm -rf {} +
