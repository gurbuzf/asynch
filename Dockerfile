# ASYNCH in a container: every dependency installed, ASYNCH compiled, tested and installed.
#
#   docker build -t asynch .                                  # build the image (5-10 minutes)
#   docker run --rm -it asynch                                # open a shell inside it
#   docker run --rm -it -v "$PWD/mywork:/work" asynch         # ... with a folder of your computer
#
# Inside the container:  cd /asynch/examples && mpirun -n 2 asynch test.gbl
# Full instructions: docs/guide/01_setup.md, section "Option B: Docker".

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# C and Fortran compilers (configure needs Fortran for its BLAS check), build tools, MPI, HDF5, PostgreSQL client, zlib, the C test framework,
# and Python with the packages used by tools/python and tests/regression.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc gfortran make autoconf automake libtool pkg-config \
        openmpi-bin libopenmpi-dev \
        libhdf5-dev hdf5-tools \
        libpq-dev zlib1g-dev check \
        python3 python3-numpy python3-h5py python3-matplotlib \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The source code (see .dockerignore for what is left out)
COPY . /asynch
WORKDIR /asynch

# Build in /asynch/build, run the unit tests, install the `asynch` program in /usr/local/bin
RUN autoreconf --install \
    && mkdir -p build && cd build \
    && ../configure CFLAGS="-O3 -DNDEBUG -Wno-format-security" \
    && make -j"$(nproc)" \
    && make check \
    && make install

# Work as a normal user: MPI refuses to run as root without extra flags. The user gets id 1000,
# the usual id of the first account on Linux/WSL, so that files written in a mounted folder
# belong to you (the base image's own "ubuntu" user, which has id 1000, is removed first).
RUN userdel --remove ubuntu \
    && useradd --create-home --uid 1000 hydro \
    && chown -R hydro /asynch && mkdir -p /work && chown hydro /work
USER hydro
WORKDIR /asynch/examples

CMD ["bash"]
