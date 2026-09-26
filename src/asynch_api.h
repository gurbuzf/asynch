#if !defined(ASYNCH_API_H)
#define ASYNCH_API_H

/// \file asynch_api.h
/// Additional C interface of ASYNCH, designed for other languages (the Python package in python/)
/// and for tests. It complements asynch_interface.h with two rules:
///   * only plain types, arrays and opaque handles are exchanged: a caller never needs to know the
///     layout of an internal structure (Link, GlobalVars, ...), so it cannot get out of sync with it;
///   * a link is designated by its *location*, 0 .. N-1, the index used everywhere inside ASYNCH;
///     Asynch_Find_Link converts a link id (as in the .rvr file) to its location.
///
/// Functions marked *collective* must be called by every MPI process of the solver.

#include <stdbool.h>
#include <asynch_interface.h>

// ---------------------------------------------------------------------------------------------------
// MPI and solver creation
// ---------------------------------------------------------------------------------------------------

/// Initialises MPI if it is not initialised yet. Returns 1 if this call initialised it, 0 otherwise.
int Asynch_MPI_Init(void);

/// Finalises MPI if it is initialised and not finalised yet. Returns 1 if this call finalised it.
int Asynch_MPI_Finalize(void);

/// Creates a solver on MPI_COMM_WORLD (MPI must be initialised, see Asynch_MPI_Init).
AsynchSolver* Asynch_Init_World(bool verbose);

/// Creates a solver on the communicator given by its Fortran handle (with mpi4py: comm.py2f()).
AsynchSolver* Asynch_Init_Fortran_Comm(int fortran_comm, bool verbose);

/// Rank of this process in the solver's communicator.
int Asynch_Get_Rank(AsynchSolver* asynch);

/// Number of processes in the solver's communicator.
int Asynch_Get_Num_Procs(AsynchSolver* asynch);

// ---------------------------------------------------------------------------------------------------
// Network
// ---------------------------------------------------------------------------------------------------

/// Id (as in the .rvr file) of the link at location loc.
unsigned int Asynch_Get_Link_ID(AsynchSolver* asynch, unsigned int loc);

/// Location of the link with the given id, or -1 if there is no such link.
long Asynch_Find_Link(AsynchSolver* asynch, unsigned int id);

/// Rank of the process that computes the link at location loc (after partitioning), -1 before.
int Asynch_Get_Link_Owner(AsynchSolver* asynch, unsigned int loc);

/// Number of upstream links (parents) of the link at location loc.
unsigned int Asynch_Get_Link_Num_Parents(AsynchSolver* asynch, unsigned int loc);

/// Writes the ids of the parents of the link at location loc into ids; returns their number.
unsigned int Asynch_Get_Link_Parents(AsynchSolver* asynch, unsigned int loc, unsigned int* ids);

/// Id of the downstream link (child) of the link at location loc, or -1 for an outlet.
long Asynch_Get_Link_Child(AsynchSolver* asynch, unsigned int loc);

/// Number of states of the link at location loc (after Asynch_Initialize_Model; 0 if not known here).
unsigned int Asynch_Get_Link_Dim(AsynchSolver* asynch, unsigned int loc);

/// Largest number of states of any link (after Asynch_Initialize_Model).
unsigned int Asynch_Get_Max_Dim(AsynchSolver* asynch);

// ---------------------------------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------------------------------

/// Number of parameters per link, including those computed by the precalculations.
unsigned int Asynch_Get_Num_Link_Params(AsynchSolver* asynch);

/// Number of parameters per link read from the .prm file (or database).
unsigned int Asynch_Get_Num_Disk_Params(AsynchSolver* asynch);

/// Copies the parameters of the link at location loc into params (Asynch_Get_Num_Link_Params values).
/// Returns 0, or 1 if the parameters of this link are not stored on this process.
int Asynch_Get_Link_Params(AsynchSolver* asynch, unsigned int loc, double* params);

/// Sets the first n parameters of the link at location loc. Returns 0, or 1 if the link is not stored
/// on this process or n is too large. After changing parameters read from disk, call
/// Asynch_Update_Precalculations so that the derived parameters follow.
int Asynch_Set_Link_Params(AsynchSolver* asynch, unsigned int loc, const double* params, unsigned int n);

/// Recomputes the derived link parameters (precalculations) from the current global and link
/// parameters, e.g. after Asynch_Set_Global_Parameters. Call after Asynch_Initialize_Model.
/// Returns 0, or 1 if the model is not initialised yet.
int Asynch_Update_Precalculations(AsynchSolver* asynch);

// ---------------------------------------------------------------------------------------------------
// States, peaks, forcings
// ---------------------------------------------------------------------------------------------------

/// Time reached by the solver [minutes since the start].
double Asynch_Get_Current_Time(AsynchSolver* asynch);

/// Latest state of the link at location loc (Asynch_Get_Link_Dim values) and its time [min].
/// Returns 0, or 1 if the link is not computed by this process.
int Asynch_Get_Link_State(AsynchSolver* asynch, unsigned int loc, double* y, double* t);

/// *Collective.* Latest states of all links, on every process: states[loc * max_dim + k] is state k of the
/// link at location loc (unused entries are 0). states must hold N * Asynch_Get_Max_Dim values.
int Asynch_Gather_States(AsynchSolver* asynch, double* states);

/// *Collective.* Sets the states of all links at time t [minutes since the start] and resets the solver
/// there, so that Asynch_Advance continues from these states. states has the layout of
/// Asynch_Gather_States. Returns 0.
int Asynch_Set_States(AsynchSolver* asynch, double t, const double* states);

/// *Collective.* Peak of state 0 (discharge) of every link since the start, and its time [min], on every
/// process: peak_value[loc], peak_time[loc]. Links without peak output get 0. Returns 0.
int Asynch_Gather_Peakflows(AsynchSolver* asynch, double* peak_time, double* peak_value);

/// Number of forcings of the model (rain, evaporation, ...).
unsigned int Asynch_Get_Num_Forcings(AsynchSolver* asynch);

/// Current value of each forcing at the link at location loc. Returns 0, or 1 if not computed here.
int Asynch_Get_Link_Forcings(AsynchSolver* asynch, unsigned int loc, double* values);

// ---------------------------------------------------------------------------------------------------
// Custom models defined outside the C source (e.g. in Python)
// ---------------------------------------------------------------------------------------------------

/// Opaque description of a model: sizes, equations and options.
typedef struct AsynchModelSpec AsynchModelSpec;

/// Derived parameters of one link. params has num_params values; the first num_disk_params were read
/// from the .prm file (after the conversion factors), the others are to be computed here.
typedef void SpecPrecalculationsFunc(
    const double * const global_params, unsigned int num_global_params,
    double *params, unsigned int num_params,
    void *user);

/// Initial states of one link. On entry, y holds the states read from the initial-state file (the
/// first num_read states, see Asynch_Model_Spec_Set_Num_Initial_States) and 0 for the others.
/// Returns the discontinuity state (0 if unused).
typedef int SpecInitializeFunc(
    const double * const global_params, unsigned int num_global_params,
    const double * const params, unsigned int num_params,
    double *y, unsigned int dim,
    void *user);

/// Creates a model description. num_disk_params <= num_params. Every other setting has a default:
/// all states read from the initial file, dense output of state 0, no precalculations, no
/// consistency check, no conversion of the .prm values. Returns NULL if a size is invalid.
AsynchModelSpec* Asynch_Model_Spec_Create(
    unsigned int num_states, unsigned int num_global_params,
    unsigned int num_params, unsigned int num_disk_params,
    unsigned int num_forcings);

/// Frees a model description (not while a solver still uses it).
void Asynch_Model_Spec_Free(AsynchModelSpec* spec);

/// The right-hand side dy/dt (required). Its `user` argument is the pointer set by
/// Asynch_Model_Spec_Set_User.
int Asynch_Model_Spec_Set_Differential(AsynchModelSpec* spec, DifferentialFunc* func);

/// Derived parameters (optional).
int Asynch_Model_Spec_Set_Precalculations(AsynchModelSpec* spec, SpecPrecalculationsFunc* func);

/// Initial states not read from file (optional).
int Asynch_Model_Spec_Set_Initialize(AsynchModelSpec* spec, SpecInitializeFunc* func);

/// Number of states read from the initial-state file (the first n; default: all).
int Asynch_Model_Spec_Set_Num_Initial_States(AsynchModelSpec* spec, unsigned int n);

/// States interpolated for downstream links (default: {0}). Every state used through y_p in the
/// differential function must be listed.
int Asynch_Model_Spec_Set_Dense_Indices(AsynchModelSpec* spec, unsigned int n, const unsigned int* indices);

/// Built-in consistency check applied after every stage and step: 0 = none (default),
/// 1 = every state >= 0, 2 = state 0 >= 1e-14 and every other state >= 0 (as models 190 and 254).
int Asynch_Model_Spec_Set_Nonnegative(AsynchModelSpec* spec, int mode);

/// Custom consistency check (replaces the built-in one). Its `user` argument is the spec's user pointer.
int Asynch_Model_Spec_Set_Check_Consistency(AsynchModelSpec* spec, CheckConsistencyFunc* func);

/// Factors applied to the parameters read from disk (num_disk_params values), e.g. 1000 to convert km to m.
int Asynch_Model_Spec_Set_Param_Factors(AsynchModelSpec* spec, const double* factors);

/// Position of the upstream area and of the hillslope area in the link parameters (used by the peak
/// output), and whether they were converted from km2 to m2 (then the peak output converts back).
int Asynch_Model_Spec_Set_Areas(AsynchModelSpec* spec, unsigned int area_idx, unsigned int areah_idx, bool converted_to_m2);

/// Minimum number of error tolerances per link in the global file (default: num_states).
int Asynch_Model_Spec_Set_Min_Error_Tolerances(AsynchModelSpec* spec, unsigned int n);

/// Pointer passed as `user` to the model functions (default NULL).
int Asynch_Model_Spec_Set_User(AsynchModelSpec* spec, void* user);

/// Uses spec as the model of this solver, instead of the model number of the global file.
/// Must be called before Asynch_Parse_GBL. Returns 0, or 1 if the spec is incomplete.
int Asynch_Install_Model(AsynchSolver* asynch, AsynchModelSpec* spec);

#endif //ASYNCH_API_H
