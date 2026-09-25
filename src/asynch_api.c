// Additional C interface of ASYNCH for other languages and tests. See asynch_api.h.

#if HAVE_CONFIG_H
#include <config.h>
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(HAVE_MPI)
#include <mpi.h>
#endif

#include <globals.h>
#include <structs.h>
#include <rksteppers.h>
#include <models/definitions.h>
#include <models/check_consistency.h>

#include <asynch_interface.h>
#include <asynch_api.h>


// ---------------------------------------------------------------------------------------------------
// MPI and solver creation
// ---------------------------------------------------------------------------------------------------

int Asynch_MPI_Init(void)
{
    int flag = 0;
    MPI_Initialized(&flag);
    if (flag)
        return 0;
    MPI_Init(NULL, NULL);
    return 1;
}

int Asynch_MPI_Finalize(void)
{
    int initialized = 0, finalized = 0;
    MPI_Initialized(&initialized);
    MPI_Finalized(&finalized);
    if (!initialized || finalized)
        return 0;
    MPI_Finalize();
    return 1;
}

AsynchSolver* Asynch_Init_World(bool verbose)
{
    return Asynch_Init(MPI_COMM_WORLD, verbose);
}

AsynchSolver* Asynch_Init_Fortran_Comm(int fortran_comm, bool verbose)
{
    return Asynch_Init(MPI_Comm_f2c((MPI_Fint)fortran_comm), verbose);
}

int Asynch_Get_Rank(AsynchSolver* asynch)
{
    return asynch->my_rank;
}

int Asynch_Get_Num_Procs(AsynchSolver* asynch)
{
    return asynch->np;
}


// ---------------------------------------------------------------------------------------------------
// Network
// ---------------------------------------------------------------------------------------------------

//true if loc designates a link of a loaded network
static bool valid_loc(const AsynchSolver* asynch, unsigned int loc)
{
    return asynch && asynch->sys && loc < asynch->N;
}

//true if the link at loc is computed by this process
static bool is_mine(const AsynchSolver* asynch, unsigned int loc)
{
    return valid_loc(asynch, loc) && asynch->assignments && asynch->assignments[loc] == asynch->my_rank
        && asynch->sys[loc].my != NULL;
}

unsigned int Asynch_Get_Link_ID(AsynchSolver* asynch, unsigned int loc)
{
    return valid_loc(asynch, loc) ? asynch->sys[loc].ID : 0;
}

long Asynch_Find_Link(AsynchSolver* asynch, unsigned int id)
{
    if (!asynch || !asynch->id_to_loc)
        return -1;
    //id_to_loc is sorted by id (see riversys.c)
    unsigned int lo = 0, hi = asynch->N;
    while (lo < hi)
    {
        unsigned int mid = lo + (hi - lo) / 2;
        if (asynch->id_to_loc[mid].id < id)
            lo = mid + 1;
        else
            hi = mid;
    }
    if (lo < asynch->N && asynch->id_to_loc[lo].id == id)
        return (long)asynch->id_to_loc[lo].loc;
    return -1;
}

int Asynch_Get_Link_Owner(AsynchSolver* asynch, unsigned int loc)
{
    if (!valid_loc(asynch, loc) || !asynch->assignments)
        return -1;
    return asynch->assignments[loc];
}

unsigned int Asynch_Get_Link_Num_Parents(AsynchSolver* asynch, unsigned int loc)
{
    return valid_loc(asynch, loc) ? asynch->sys[loc].num_parents : 0;
}

unsigned int Asynch_Get_Link_Parents(AsynchSolver* asynch, unsigned int loc, unsigned int* ids)
{
    if (!valid_loc(asynch, loc))
        return 0;
    Link* link = &asynch->sys[loc];
    for (unsigned int i = 0; i < link->num_parents; i++)
        ids[i] = link->parents[i]->ID;
    return link->num_parents;
}

long Asynch_Get_Link_Child(AsynchSolver* asynch, unsigned int loc)
{
    if (!valid_loc(asynch, loc) || !asynch->sys[loc].child)
        return -1;
    return (long)asynch->sys[loc].child->ID;
}

unsigned int Asynch_Get_Link_Dim(AsynchSolver* asynch, unsigned int loc)
{
    return valid_loc(asynch, loc) ? asynch->sys[loc].dim : 0;
}

unsigned int Asynch_Get_Max_Dim(AsynchSolver* asynch)
{
    return (asynch && asynch->globals) ? asynch->globals->max_dim : 0;
}


// ---------------------------------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------------------------------

unsigned int Asynch_Get_Num_Link_Params(AsynchSolver* asynch)
{
    return (asynch && asynch->globals) ? asynch->globals->num_params : 0;
}

unsigned int Asynch_Get_Num_Disk_Params(AsynchSolver* asynch)
{
    return (asynch && asynch->globals) ? asynch->globals->num_disk_params : 0;
}

int Asynch_Get_Link_Params(AsynchSolver* asynch, unsigned int loc, double* params)
{
    if (!valid_loc(asynch, loc) || !asynch->sys[loc].params)
        return 1;
    memcpy(params, asynch->sys[loc].params, asynch->globals->num_params * sizeof(double));
    return 0;
}

int Asynch_Set_Link_Params(AsynchSolver* asynch, unsigned int loc, const double* params, unsigned int n)
{
    if (!valid_loc(asynch, loc) || !asynch->sys[loc].params || n > asynch->globals->num_params)
        return 1;
    memcpy(asynch->sys[loc].params, params, n * sizeof(double));
    return 0;
}

int Asynch_Update_Precalculations(AsynchSolver* asynch)
{
    if (!asynch || !asynch->setup_initmodel)
        return 1;

    GlobalVars* globals = asynch->globals;
    AsynchModel* model = asynch->model;
    for (unsigned int i = 0; i < asynch->N; i++)
    {
        Link* link = &asynch->sys[i];
        if (!link->params || !link->my)
            continue;
        //Same calls as Initialize_Model (riversys.c)
        if (model && model->routines)
            model->precalculations(link, globals->global_params, link->params, link->has_dam, asynch->ExternalInterface);
        else
            Precalculations(link, globals->global_params, globals->num_global_params, link->params,
                globals->num_disk_params, globals->num_params, link->has_dam, globals->model_uid, asynch->ExternalInterface);
    }
    return 0;
}


// ---------------------------------------------------------------------------------------------------
// States, peaks, forcings
// ---------------------------------------------------------------------------------------------------

double Asynch_Get_Current_Time(AsynchSolver* asynch)
{
    return (asynch && asynch->globals) ? asynch->globals->t : 0.0;
}

int Asynch_Get_Link_State(AsynchSolver* asynch, unsigned int loc, double* y, double* t)
{
    if (!is_mine(asynch, loc) || !asynch->sys[loc].my->list.tail)
        return 1;
    const Link* link = &asynch->sys[loc];
    memcpy(y, link->my->list.tail->y_approx, link->dim * sizeof(double));
    if (t)
        *t = link->my->list.tail->t;
    return 0;
}

int Asynch_Gather_States(AsynchSolver* asynch, double* states)
{
    unsigned int N = asynch->N, max_dim = asynch->globals->max_dim;
    memset(states, 0, (size_t)N * max_dim * sizeof(double));
    for (unsigned int i = 0; i < asynch->my_N; i++)
    {
        const Link* link = asynch->my_sys[i];
        memcpy(states + (size_t)link->location * max_dim, link->my->list.tail->y_approx, link->dim * sizeof(double));
    }
    //Each value is non zero on its owner only, so the sum is exact
    MPI_Allreduce(MPI_IN_PLACE, states, (int)(N * max_dim), MPI_DOUBLE, MPI_SUM, asynch->comm);
    return 0;
}

int Asynch_Set_States(AsynchSolver* asynch, double t, const double* states)
{
    unsigned int N = asynch->N, max_dim = asynch->globals->max_dim;

    //Asynch_Set_System_State expects the states of the links stored here (computed or received), in
    //location order, one after the other
    size_t size = 0;
    for (unsigned int i = 0; i < N; i++)
        if (asynch->sys[i].my)
            size += asynch->sys[i].dim;
    double *packed = malloc((size ? size : 1) * sizeof(double));
    size_t pos = 0;
    for (unsigned int i = 0; i < N; i++)
    {
        const Link* link = &asynch->sys[i];
        if (!link->my)
            continue;
        memcpy(packed + pos, states + (size_t)i * max_dim, link->dim * sizeof(double));
        pos += link->dim;
    }

    Asynch_Set_System_State(asynch, t, packed);
    asynch->globals->t = t;
    free(packed);
    return 0;
}

int Asynch_Gather_Peakflows(AsynchSolver* asynch, double* peak_time, double* peak_value)
{
    unsigned int N = asynch->N;
    memset(peak_time, 0, N * sizeof(double));
    memset(peak_value, 0, N * sizeof(double));
    for (unsigned int i = 0; i < asynch->my_N; i++)
    {
        const Link* link = asynch->my_sys[i];
        if (link->peak_flag && link->peak_value)
        {
            peak_time[link->location] = link->peak_time;
            peak_value[link->location] = link->peak_value[0];
        }
    }
    MPI_Allreduce(MPI_IN_PLACE, peak_time, (int)N, MPI_DOUBLE, MPI_SUM, asynch->comm);
    MPI_Allreduce(MPI_IN_PLACE, peak_value, (int)N, MPI_DOUBLE, MPI_SUM, asynch->comm);
    return 0;
}

unsigned int Asynch_Get_Num_Forcings(AsynchSolver* asynch)
{
    return (asynch && asynch->globals) ? asynch->globals->num_forcings : 0;
}

int Asynch_Get_Link_Forcings(AsynchSolver* asynch, unsigned int loc, double* values)
{
    if (!is_mine(asynch, loc) || !asynch->sys[loc].my->forcing_values)
        return 1;
    memcpy(values, asynch->sys[loc].my->forcing_values, asynch->globals->num_forcings * sizeof(double));
    return 0;
}


// ---------------------------------------------------------------------------------------------------
// Custom models
// ---------------------------------------------------------------------------------------------------

struct AsynchModelSpec
{
    AsynchModel model;              //!< The model given to the solver; its callbacks are the adapters below

    unsigned int num_states;
    unsigned int num_global_params;
    unsigned int num_params;
    unsigned int num_disk_params;
    unsigned int num_forcings;
    unsigned int num_read;          //!< States read from the initial-state file
    unsigned int num_dense;
    unsigned int *dense_indices;
    unsigned int area_idx, areah_idx;
    bool convertarea;
    unsigned int min_error_tolerances;
    double *factors;                //!< [num_disk_params] or NULL

    DifferentialFunc *differential;
    SpecPrecalculationsFunc *precalculations;
    SpecInitializeFunc *initialize;
    CheckConsistencyFunc *check_consistency;
    int nonnegative;
    void *user;
};

//Consistency checks for the modes of Asynch_Model_Spec_Set_Nonnegative
static void Consistency_None(
    double *y, unsigned int dim,
    const double * const global_params, unsigned int num_global_params,
    const double * const params, unsigned int num_params,
    void *user)
{
}

static void Consistency_AllNonnegative(
    double *y, unsigned int dim,
    const double * const global_params, unsigned int num_global_params,
    const double * const params, unsigned int num_params,
    void *user)
{
    for (unsigned int i = 0; i < dim; i++)
        if (y[i] < 0.0)
            y[i] = 0.0;
}

//Initial states: those read from file, the others 0 (riversys.c), nothing more
static int Initialize_Keep(
    const double * const global_params, unsigned int num_global_params,
    const double * const params, unsigned int num_params,
    double *y, unsigned int dim,
    void *user)
{
    return 0;
}

//Adapters between AsynchModel and the spec. They receive the spec as `external`
//(Asynch_Install_Model sets asynch->ExternalInterface), or as link->user for initialize_eqs.

static void Spec_SetParamSizes(GlobalVars* globals, void* external)
{
    AsynchModelSpec* spec = (AsynchModelSpec*)external;

    globals->uses_dam = 0;
    globals->num_params = spec->num_params;
    globals->dam_params_size = 0;
    globals->area_idx = spec->area_idx;
    globals->areah_idx = spec->areah_idx;
    globals->num_disk_params = spec->num_disk_params;
    globals->convertarea_flag = spec->convertarea;
    globals->num_forcings = spec->num_forcings;
    globals->min_error_tolerances = spec->min_error_tolerances;

    //Same rule as the built-in models (SetParamSizes, models/definitions.c)
    if (globals->num_global_params < spec->num_global_params)
    {
        printf("\nError: Obtained %u global parameters from the .gbl file. Expected %u for this custom model.\n",
            globals->num_global_params, spec->num_global_params);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    if (globals->num_global_params > spec->num_global_params)
        printf("\nWarning: Obtained %u global parameters from the .gbl file. Expected %u for this custom model.\n",
            globals->num_global_params, spec->num_global_params);
}

static void Spec_Convert(double *params, unsigned int model_uid, void* external)
{
    AsynchModelSpec* spec = (AsynchModelSpec*)external;
    if (spec->factors)
        for (unsigned int i = 0; i < spec->num_disk_params; i++)
            params[i] *= spec->factors[i];
}

static void Spec_Routines(Link* link, unsigned int model_uid, unsigned int exp_imp, unsigned short has_dam, void* external)
{
    AsynchModelSpec* spec = (AsynchModelSpec*)external;

    link->dim = spec->num_states;
    link->diff_start = 0;
    link->no_ini_start = spec->num_read;

    link->num_dense = spec->num_dense;
    link->dense_indices = (unsigned int*)realloc(link->dense_indices, spec->num_dense * sizeof(unsigned int));
    memcpy(link->dense_indices, spec->dense_indices, spec->num_dense * sizeof(unsigned int));

    link->solver = &ExplicitRKSolver;
    link->differential = spec->differential;
    link->jacobian = NULL;
    link->algebraic = NULL;
    link->check_state = NULL;
    //The steppers always call check_consistency, so it is never NULL
    if (spec->check_consistency)
        link->check_consistency = spec->check_consistency;
    else if (spec->nonnegative == 1)
        link->check_consistency = &Consistency_AllNonnegative;
    else if (spec->nonnegative == 2)
        link->check_consistency = &CheckConsistency_Nonzero_AllStates_q;
    else
        link->check_consistency = &Consistency_None;

    //Passed as `user` to the model functions
    link->user = spec->user;
}

static void Spec_Precalculations(Link* link, const double * const global_params, double * const params, unsigned short has_dam, void* external)
{
    AsynchModelSpec* spec = (AsynchModelSpec*)external;
    if (spec->precalculations)
        spec->precalculations(global_params, spec->num_global_params, params, spec->num_params, spec->user);
}

AsynchModelSpec* Asynch_Model_Spec_Create(
    unsigned int num_states, unsigned int num_global_params,
    unsigned int num_params, unsigned int num_disk_params,
    unsigned int num_forcings)
{
    if (num_states == 0 || num_disk_params > num_params || num_forcings > ASYNCH_MAX_DB_CONNECTIONS - ASYNCH_DB_LOC_FORCING_START)
        return NULL;

    AsynchModelSpec* spec = calloc(1, sizeof(AsynchModelSpec));
    if (!spec)
        return NULL;

    spec->num_states = num_states;
    spec->num_global_params = num_global_params;
    spec->num_params = num_params;
    spec->num_disk_params = num_disk_params;
    spec->num_forcings = num_forcings;
    spec->num_read = num_states;
    spec->num_dense = 1;
    spec->dense_indices = calloc(1, sizeof(unsigned int));
    spec->area_idx = 0;
    spec->areah_idx = 0;
    spec->convertarea = false;
    spec->min_error_tolerances = num_states;
    return spec;
}

void Asynch_Model_Spec_Free(AsynchModelSpec* spec)
{
    if (!spec)
        return;
    free(spec->dense_indices);
    free(spec->factors);
    free(spec);
}

int Asynch_Model_Spec_Set_Differential(AsynchModelSpec* spec, DifferentialFunc* func)
{
    if (!spec || !func)
        return 1;
    spec->differential = func;
    return 0;
}

int Asynch_Model_Spec_Set_Precalculations(AsynchModelSpec* spec, SpecPrecalculationsFunc* func)
{
    if (!spec)
        return 1;
    spec->precalculations = func;
    return 0;
}

int Asynch_Model_Spec_Set_Initialize(AsynchModelSpec* spec, SpecInitializeFunc* func)
{
    if (!spec)
        return 1;
    spec->initialize = func;
    return 0;
}

int Asynch_Model_Spec_Set_Num_Initial_States(AsynchModelSpec* spec, unsigned int n)
{
    if (!spec || n > spec->num_states)
        return 1;
    spec->num_read = n;
    return 0;
}

int Asynch_Model_Spec_Set_Dense_Indices(AsynchModelSpec* spec, unsigned int n, const unsigned int* indices)
{
    if (!spec || n == 0 || n > spec->num_states)
        return 1;
    for (unsigned int i = 0; i < n; i++)
        if (indices[i] >= spec->num_states)
            return 1;
    unsigned int *copy = malloc(n * sizeof(unsigned int));
    if (!copy)
        return 1;
    memcpy(copy, indices, n * sizeof(unsigned int));
    free(spec->dense_indices);
    spec->dense_indices = copy;
    spec->num_dense = n;
    return 0;
}

int Asynch_Model_Spec_Set_Nonnegative(AsynchModelSpec* spec, int mode)
{
    if (!spec || mode < 0 || mode > 2)
        return 1;
    spec->nonnegative = mode;
    return 0;
}

int Asynch_Model_Spec_Set_Check_Consistency(AsynchModelSpec* spec, CheckConsistencyFunc* func)
{
    if (!spec)
        return 1;
    spec->check_consistency = func;
    return 0;
}

int Asynch_Model_Spec_Set_Param_Factors(AsynchModelSpec* spec, const double* factors)
{
    if (!spec)
        return 1;
    free(spec->factors);
    spec->factors = NULL;
    if (factors && spec->num_disk_params)
    {
        spec->factors = malloc(spec->num_disk_params * sizeof(double));
        if (!spec->factors)
            return 1;
        memcpy(spec->factors, factors, spec->num_disk_params * sizeof(double));
    }
    return 0;
}

int Asynch_Model_Spec_Set_Areas(AsynchModelSpec* spec, unsigned int area_idx, unsigned int areah_idx, bool converted_to_m2)
{
    if (!spec || area_idx >= spec->num_params || areah_idx >= spec->num_params)
        return 1;
    spec->area_idx = area_idx;
    spec->areah_idx = areah_idx;
    spec->convertarea = converted_to_m2;
    return 0;
}

int Asynch_Model_Spec_Set_Min_Error_Tolerances(AsynchModelSpec* spec, unsigned int n)
{
    if (!spec)
        return 1;
    spec->min_error_tolerances = n;
    return 0;
}

int Asynch_Model_Spec_Set_User(AsynchModelSpec* spec, void* user)
{
    if (!spec)
        return 1;
    spec->user = user;
    return 0;
}

int Asynch_Install_Model(AsynchSolver* asynch, AsynchModelSpec* spec)
{
    if (!asynch || !spec || !spec->differential || asynch->setup_gbl)
        return 1;

    AsynchModel* model = &spec->model;
    memset(model, 0, sizeof(AsynchModel));
    model->dim = (unsigned short)spec->num_states;
    model->no_ini_start = spec->num_read;
    model->num_global_params = spec->num_global_params;
    model->num_params = spec->num_params;
    model->num_disk_params = spec->num_disk_params;
    model->num_forcings = spec->num_forcings;
    model->set_param_sizes = &Spec_SetParamSizes;
    model->convert = &Spec_Convert;
    model->routines = &Spec_Routines;
    model->precalculations = &Spec_Precalculations;
    model->initialize_eqs = spec->initialize ? spec->initialize : &Initialize_Keep;

    //Asynch_Custom_Model keeps a partitioning routine set earlier
    Asynch_Custom_Model(asynch, model);
    asynch->ExternalInterface = spec;
    return 0;
}
