# The same sources are built twice:
#  - libasynch.a  (static) is linked into the programs asynch and assim; results do not depend on
#    this choice, it only keeps the programs self-contained.
#  - libasynch.la (shared, libasynch.so once installed) is loaded by the Python package (python/).
lib_LIBRARIES = libasynch.a
lib_LTLIBRARIES = libasynch.la

ASYNCH_SOURCES = \
  globals.c \
  advance.c \
  asynch_interface.c \
  asynch_api.c \
  blas.c \
  comm.c \
  compression.c \
  config_gbl.c \
  data_types.c \
  date_manip.c \
  db.c \
  forcings.c forcings_io.c \
  io.c \
  misc.c \
  outputs.c \
  partition.c \
  processdata.c \
  riversys.c \
  rksteppers.c \
  sort.c \
  system.c \
  models/check_consistency.c \
  models/output_constraints.c \
  models/check_state.c \
  models/definitions.c \
  models/equations.c \
  solvers/dopri5_dense.c \
  solvers/lagrange.c \
  solvers/radau.c \
  solvers/rk3_2_dense.c \
  solvers/rk4_3_dense.c \
  steppers/explicit.c \
  steppers/explicit_index1.c \
  steppers/explicit_index1_dam.c \
  steppers/forced.c \
  advance.h \
  asynch_interface.h \
  asynch_api.h \
  blas.h \
  comm.h \
  compression.h \
  config_gbl.h \
  constants.h \
  data_types.h \
  date_manip.h \
  db.h \
  forcings.h forcings_io.h \
  globals.h \
  io.h \
  libpq_fwd.h \
  minmax.h \
  misc.h \
  outputs.h \
  partition.h \
  processdata.h \
  riversys.h \
  rkmethods.h \
  rksteppers.h \
  sort.h \
  structs.h \
  structs_fwd.h \
  system.h \
  models/check_consistency.h \
  models/output_constraints.h \
  models/check_state.h \
  models/definitions.h \
  models/equations.h \
  models/model.h \
  solvers/lagrange.h

libasynch_a_SOURCES = $(ASYNCH_SOURCES)
libasynch_la_SOURCES = $(ASYNCH_SOURCES)
libasynch_la_CFLAGS = $(AM_CFLAGS)
libasynch_la_LDFLAGS = -version-info 0:0:0 $(HDF5_LDFLAGS) $(POSTGRESQL_LDFLAGS)
libasynch_la_LIBADD = $(HDF5_LIBS) $(POSTGRESQL_LIBS) -lm

bin_PROGRAMS = asynch
asynch_SOURCES = optparse.c optparse.h asynch_cli.c
asynch_LDADD = libasynch.a $(HDF5_LIBS) $(POSTGRESQL_LIBS) $(METIS_LIBS)
asynch_LDFLAGS = $(HDF5_LDFLAGS) $(POSTGRESQL_LDFLAGS) $(METIS_LDFLAGS)

# If PETSc is available, add the assim source files to asynch an build the assim CLI
if USE_PETSC

libasynch_la_SOURCES += \
  assim/ancillary.c \
  assim/linear_least_squares.c \
  assim/models.c

libasynch_a_SOURCES += \
  assim/ancillary.c \
  assim/linear_least_squares.c \
  assim/models.c \
  assim/ancillary.h \
  assim/linear_least_squares.h \
  assim/models.h \
  assim/structs.h

bin_PROGRAMS += assim

assim_SOURCES = optparse.c optparse.h assim_cli.c
assim_LDADD = libasynch.a $(HDF5_LIBS) $(POSTGRESQL_LIBS) $(METIS_LIBS) $(PETSC_LIBS)
assim_LDFLAGS = $(HDF5_LDFLAGS) $(POSTGRESQL_LDFLAGS) $(METIS_LDFLAGS) $(PETSC_LDFLAGS)

endif

include_HEADERS = structs.h structs_fwd.h asynch_interface.h asynch_api.h

AM_CFLAGS = $(HDF5_CPPFLAGS) $(POSTGRESQL_CPPFLAGS) $(METIS_CPPFLAGS) $(PETSC_CFLAGS)
