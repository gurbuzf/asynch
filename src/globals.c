// Definitions of the global variables declared in globals.h.
// They live in the library (not in each program) so that the library can also be used
// as a shared library, e.g. from Python. Asynch_Init sets them from the MPI communicator.
#include <globals.h>

int my_rank = 0;    //!< Rank of this MPI process (0 .. np-1)
int np = 0;         //!< Number of MPI processes
