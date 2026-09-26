AUTOMAKE_OPTIONS = subdir-objects

SUBDIRS = src tests tools
ACLOCAL_AMFLAGS = -I m4
EXTRA_DIST = LICENSE README.md examples

# The Python package (python/asynch). `make install` installs the C library it uses; this installs the package
# itself into the Python environment of PYTHON_FOR_ASYNCH (a virtual environment, or add PIP_FLAGS=--user):
#   make install-python                         # python3 -m pip install <source>/python
#   make install-python PYTHON_FOR_ASYNCH=~/venv/bin/python
PYTHON_FOR_ASYNCH = python3
PIP_FLAGS =
install-python:
	$(PYTHON_FOR_ASYNCH) -m pip install --no-build-isolation $(PIP_FLAGS) $(abs_top_srcdir)/python

.PHONY: install-python

dist-hook:
	rm -f $(distdir)/examples/.gitignore
#	mkdir $(distdir)/docs
#	cp -R $(srcdir)/docs/.build/html $(distdir)/docs
