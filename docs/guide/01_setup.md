# 1. Setting up: install ASYNCH and run a first simulation

This chapter takes you from an empty computer to a finished model run. Choose **one** option:

| Option | Your computer | Effort | Tested |
|---|---|---|---|
| **A. Native install** | Ubuntu 24.04 (or Windows with WSL2 running Ubuntu 24.04) | 15 minutes | yes, command by command on a fresh Ubuntu 24.04 |
| **B. Docker** | any: Windows, macOS, Linux | 10 minutes + download | yes: image built, all examples and tests run inside |
| C. Other systems | Fedora, macOS without Docker | varies | no; notes only, prefer B |

Commands are shown in grey boxes. Type them (or copy them) in a **terminal**, the text window of
your system: "Terminal" on Ubuntu and macOS, "Ubuntu" (WSL) or PowerShell on Windows. Lines starting with `#` are
comments; you do not need to type them. After each step, "you should see" tells you what success looks like.

---

## Option A: native install on Ubuntu 24.04

### A.0 (Windows only) Get Ubuntu inside Windows with WSL2

WSL2 runs a real Ubuntu inside Windows 10/11. Open **PowerShell as administrator** and type:

```
wsl --install -d Ubuntu-24.04
```

Restart when asked. Then open "Ubuntu 24.04" from the Start menu, choose a user name and password,
and follow the rest of Option A in that window. (This step is Microsoft's standard procedure; it
could not be tested in the Linux environment where this guide was written.)

### A.1 Install the software ASYNCH needs

```bash
sudo apt-get update
sudo apt-get install -y git ca-certificates gcc gfortran make autoconf automake libtool pkg-config \
    openmpi-bin libopenmpi-dev libhdf5-dev hdf5-tools libpq-dev zlib1g-dev check \
    python3 python3-numpy python3-h5py python3-matplotlib
```

`sudo` asks for your password: this installs system software. What each package is for:

| Packages | Why ASYNCH needs them |
|---|---|
| `gcc`, `gfortran`, `make` | the C compiler, a Fortran compiler (the build configuration tests for it) and the build tool |
| `autoconf`, `automake`, `libtool`, `pkg-config` | the "autotools", which prepare the build for your computer |
| `openmpi-bin`, `libopenmpi-dev` | MPI, to run on several processors (`mpirun`) |
| `libhdf5-dev`, `hdf5-tools` | HDF5, the binary format of many outputs, plus the `h5dump` viewer |
| `libpq-dev` | PostgreSQL client (reading/writing a database, optional at run time) |
| `zlib1g-dev` | reading compressed rain files |
| `check` | the C unit-test framework |
| `git`, `ca-certificates` | downloading the code (ca-certificates lets git check the identity of github.com) |
| `python3-numpy`, `python3-h5py`, `python3-matplotlib` | reading and plotting results, and the regression tests |

*You should see* the installation end without `E:` (error) lines.

### A.2 Download the code

```bash
cd ~
git clone https://github.com/gurbuzf/asynch.git
cd asynch
git checkout modernization
```

*You should see* `Switched to branch 'modernization'` (or `Already on 'modernization'`).
The folder `~/asynch` now holds the code; all commands below are run from inside it.

### A.3 Build (compile) ASYNCH

Compiling translates the C source code into a program. It is done in three commands; they are
explained in detail in [06_c_primer.md §6.1](06_c_primer.md#61-how-a-c-program-is-built).

```bash
autoreconf --install
cd build
../configure CFLAGS="-O3 -DNDEBUG -Wno-format-security"
make -j4
```

* `autoreconf --install` prepares the build scripts (run it once after downloading).
* `../configure` checks that everything from A.1 is installed. *You should see* it end with
  `config.status: creating config.h`. If it stops with an `error:`, see [Troubleshooting](#troubleshooting).
* `make -j4` compiles, using 4 processors. It prints many lines, including some `warning:`
  lines; those are normal. *You should see* it end without an `Error` line.

The program is now `~/asynch/build/src/asynch`. Check it:

```bash
./src/asynch --version
```

*You should see* `This is asynch 1.4.3`.

### A.4 Check that the results are right

```bash
make check
```

This runs three sets of tests (chapter 9) and takes about a minute:

* `check_asynch`: 22 C unit tests (the solver's coefficient tables, every built-in model's setup, ...);
* `run_python_tests.sh`: 62 tests of the Python package (chapter 10), with the library just built;
* `run_regression.sh`: every example, compared with the reference results shipped with the original ASYNCH.

*You should see* `# PASS:  3` and `# FAIL:  0` at the end. The details are in `tests/*.log`; for example
`tests/run_regression.sh.log` lists the examples as `PASS` or `XFAIL` (a known, documented difference) and ends with
`0 unexpected failure(s)`.

### A.5 Run your first simulation

```bash
cd ../examples
mpirun -n 2 ../build/src/asynch test.gbl
```

`mpirun -n 2` starts ASYNCH on 2 processors. *You should see*:

```
Beginning initialization...
...
Model type is 190.
Process 0 (2 total) is good to go with 7 links.
Process 1 (2 total) is good to go with 4 links.
...
Computations complete. Total time for calculations: 0.01...

Results written to file outputs.h5.
Peakflows written to file test.pea.
```

Then the larger example: the Clear Creek basin in Iowa, 6 359 links, model 254:

```bash
mpirun -n 2 ../build/src/asynch clearcreek.gbl
```

You have run the model. Chapter 2 explains what went in, what came out, and how to change it.

**Optional: make `asynch` available everywhere.** `sudo make install && sudo ldconfig` (run in `~/asynch/build`)
copies the program to `/usr/local/bin` and the library `libasynch.so` to `/usr/local/lib`, after which you can type
`asynch` instead of `../build/src/asynch`.

### A.6 (optional) Use ASYNCH from Python

```bash
export PYTHONPATH=~/asynch/python          # add this line to ~/.bashrc to keep it
cd ~/asynch/examples
python3 python/run_example.py
```

*You should see* `test_2015.gbl: model 190, 11 links, 300 minutes` followed by the five largest peak flows. The package
uses the library of the build folder, or the installed one after `sudo make install`. Chapter 10 explains the
package, another way to install it, and how to write new models with it.

---

## Option B: Docker (Windows, macOS, Linux)

Docker runs a small, ready-made Linux system (a **container**) on your computer. The recipe for it,
`Dockerfile` in the repository, installs everything, compiles ASYNCH, checks it and installs it.

### B.1 Install Docker

* Windows and macOS: install **Docker Desktop** from <https://www.docker.com/products/docker-desktop/> and start it.
* Linux: install Docker Engine (<https://docs.docker.com/engine/install/>), then allow your user to use it:
  `sudo usermod -aG docker $USER`, and log out and in again.

*You should see* a version number when you type `docker --version`.

### B.2 Download the code and build the image

```bash
git clone https://github.com/gurbuzf/asynch.git
cd asynch
git checkout modernization
docker build -t asynch .
```

(Without git, download the ZIP of the `modernization` branch from GitHub instead, and open a terminal in the unpacked folder.)
The build takes 5–10 minutes the first time. *You should see* it end with `naming to docker.io/library/asynch`.
During the build, the C unit test runs; its lines `PASS: check_asynch` and `# ERROR: 0` show it passed.

### B.3 Run the examples inside the container

```bash
docker run --rm -it asynch
```

You are now in a terminal *inside* the container, in the examples folder. Try:

```bash
mpirun -n 2 asynch test.gbl
python3 ../tests/regression/run_examples.py --np 2
python3 python/run_example.py              # the Python package (chapter 10) is ready to use
exit
```

`exit` leaves the container. `--rm` means the container is deleted when you leave, so **anything written
inside it is lost**, unless it was written to a shared folder (next step).

### B.4 Work with your own files (a shared folder)

Create a folder for your work, then share it with the container as `/work`:

```bash
mkdir -p mywork
docker run --rm -it -v "$PWD/mywork:/work" asynch
```

Inside the container, copy the examples into it, run, and the results stay on your computer:

```bash
cp -r /asynch/examples /work/
cd /work/examples
mpirun -n 2 asynch clearcreek.gbl
exit
```

You will find `mywork/examples/clearcreek.h5` and `clearcreek.pea` on your computer.

* On Windows PowerShell write `${PWD}` instead of `$PWD`.
* On Linux, if your user id is not 1000 (check with `id -u`) and you get `Permission denied` in `/work`,
  add `--user "$(id -u):$(id -g)"` after `docker run`.

---

## Option C: other systems (not tested)

These were **not tested** for this guide. If anything fails, use Option B.

* **Fedora / RHEL / Rocky**: `sudo dnf install git gcc gcc-gfortran make autoconf automake libtool pkgconf
  openmpi-devel hdf5-devel libpq-devel zlib-devel check-devel python3-numpy python3-h5py python3-matplotlib`,
  then `module load mpi/openmpi-x86_64` (or add `/usr/lib64/openmpi/bin` to your `PATH`), then steps A.2–A.5.
* **macOS with Homebrew**: `brew install gcc autoconf automake libtool pkg-config open-mpi hdf5 libpq check`
  (the Fortran compiler comes with `gcc`). The build may need to be told where Homebrew keeps HDF5 and libpq.

---

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `configure: error: cannot compile a simple Fortran program` | the Fortran compiler is missing: install `gfortran` |
| `configure: error: ... MPI` or `mpicc: command not found` | MPI is missing: install `openmpi-bin libopenmpi-dev` |
| `autoreconf: command not found` | install `autoconf automake libtool` |
| `mpirun has detected an attempt to run as root` | you are root (e.g. in a container): run as a normal user, or add `--allow-run-as-root` |
| `There are not enough slots available` | you asked for more processes than processors: use a smaller `-n`, or add `--oversubscribe` |
| `error: externally-managed-environment` from `pip` | on Ubuntu 24.04, install Python packages with `apt` (`python3-numpy`, ...), as in A.1 |
| `Error: file ... not found` when running | ASYNCH looks for input files relative to the folder you are in: `cd` into the folder of the `.gbl` |
| `Fatal glibc error: malloc.c ...` with `clearcreek.gbl` | an old version of ASYNCH (bug B-01, fixed); make sure you built the `modernization` branch |

## Build variants (for developers)

The `CFLAGS` given to `configure` choose how the program is compiled. Use a separate build folder for each:

| `CFLAGS` | Use |
|---|---|
| `-O3 -DNDEBUG` | normal use: fastest; internal checks (`assert`) off |
| `-O0 -g` | debugging with `gdb`: slow, but every variable can be inspected |
| `-O1 -g -fsanitize=address,undefined` (plus `LDFLAGS="-fsanitize=address,undefined"`) | finding memory errors, see [09_reproducibility.md](09_reproducibility.md) |
