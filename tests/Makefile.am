# `make check` runs, in this order:
#   check_asynch          C unit tests (check_asynch.c, needs libcheck)
#   run_python_tests.sh   tests of the Python package against the library just built (tests/python)
#   run_regression.sh     every example, compared with the reference results (tests/regression)
TESTS = check_asynch run_python_tests.sh run_regression.sh
check_PROGRAMS = check_asynch
check_asynch_SOURCES = check_asynch.c
check_asynch_LDADD = $(top_builddir)/src/libasynch.a $(CHECK_LIBS) $(HDF5_LIBS) $(POSTGRESQL_LIBS) -lm
check_asynch_LDFLAGS = $(HDF5_LDFLAGS) $(POSTGRESQL_LDFLAGS)

AM_CFLAGS = -I$(srcdir)/../src $(CHECK_CFLAGS) $(HDF5_CPPFLAGS) $(POSTGRESQL_CPPFLAGS)

AM_TESTS_ENVIRONMENT = \
  ASYNCH_LIBRARY=$(abs_top_builddir)/src/.libs/libasynch.so; export ASYNCH_LIBRARY; \
  ASYNCH_EXE=$(abs_top_builddir)/src/asynch; export ASYNCH_EXE; \
  srcdir=$(srcdir); export srcdir;

EXTRA_DIST = run_python_tests.sh run_regression.sh python regression data_generators
