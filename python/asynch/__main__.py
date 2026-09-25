"""
Command line of the Python package.

    python3 -m asynch run file.gbl             # same as the asynch program
    python3 -m asynch info file.gbl            # what a global file contains, and the network size
    python3 -m asynch library                  # which libasynch is used

With MPI: mpirun -np 4 python3 -m asynch run file.gbl
"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m asynch", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command")
    run = sub.add_parser("run", help="run a global file and write its outputs")
    run.add_argument("gbl")
    run.add_argument("-v", "--verbose", action="store_true", help="progress messages of the C library")
    info = sub.add_parser("info", help="summarise a global file and its network")
    info.add_argument("gbl")
    sub.add_parser("library", help="print the path of the libasynch used")
    a = ap.parse_args(argv)

    if a.command == "library":
        from . import find_library
        print(find_library())
        return 0

    if a.command in ("run", "info"):
        from .solver import Simulation
        if a.command == "run":
            with Simulation(a.gbl, verbose=a.verbose) as sim:
                sim.run()
                if sim.rank == 0:
                    print("%s: %d links, %g minutes simulated" % (a.gbl, sim.num_links, sim.time))
            return 0
        with Simulation(a.gbl, load=False) as sim:
            c = sim.config
            sim.load(prepare_outputs=False)
            if sim.rank == 0:
                print("global file     %s" % a.gbl)
                print("model           %s" % c.model)
                print("period          %s -> %s (%g minutes)" % (c.begin, c.end, sim.duration_total))
                print("links           %d (%d computed by this process)" % (sim.num_links, sim.num_links_local))
                print("states per link %d" % sim.max_dim)
                print("global params   %s" % " ".join("%g" % v for v in sim.global_params))
                print("link params     %d (%d read from disk)" % (sim.num_link_params, sim.num_disk_params))
                print("forcings        %d" % sim.num_forcings)
                print("outputs         %s" % ", ".join(c.outputs))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
