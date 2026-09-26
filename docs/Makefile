# Build the documentation: `make -C docs html` (see conf.py for the requirements)
SPHINXBUILD ?= sphinx-build
SOURCEDIR    = .
BUILDDIR     = _build

.PHONY: html clean
html:
	$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"
clean:
	rm -rf "$(BUILDDIR)" .doxygen
