// Unit tests of the ASYNCH library (C), run by `make check`. Uses the Check framework (libcheck).
//
// What is tested here, without input files:
//   dates      calendar helper
//   sort       sorting and the id -> location lookup used everywhere
//   rk         the Runge-Kutta tables of the three solvers: order conditions, error estimators, dense output,
//              and the observed order of accuracy on y' = y
//   models     the setup of every built-in model: sizes and indices consistent, and the functions that the
//              solver calls unconditionally are set
//   equations  a few properties of the model 190 equations and of the consistency checks
//   api        argument checks of the model specification (asynch_api.h)
// The regression tests (tests/regression) and the Python tests (tests/python) run complete simulations.

#if HAVE_CONFIG_H
#include <config.h>
#endif

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>

#include <check.h>
#include <mpi.h>

#include <structs.h>
#include <date_manip.h>
#include <sort.h>
#include <rkmethods.h>
#include <models/definitions.h>
#include <models/equations.h>
#include <models/check_consistency.h>
#include <asynch_api.h>

// ---------------------------------------------------------------------------------------------------
// dates
// ---------------------------------------------------------------------------------------------------

START_TEST(test_date_manip_days_in_month)
{
    ck_assert_int_eq(days_in_month(0, 1995), 31);
    ck_assert_int_eq(days_in_month(1, 1995), 28);
    ck_assert_int_eq(days_in_month(2, 1995), 31);
    ck_assert_int_eq(days_in_month(3, 1995), 30);
    ck_assert_int_eq(days_in_month(1, 2000), 29);     // divisible by 400: leap
    ck_assert_int_eq(days_in_month(1, 2016), 29);
    ck_assert_int_eq(days_in_month(11, 2016), 31);
    int total = 0;
    for (int m = 0; m < 12; m++)
        total += days_in_month(m, 2019);
    ck_assert_int_eq(total, 365);
}
END_TEST

// ---------------------------------------------------------------------------------------------------
// sort
// ---------------------------------------------------------------------------------------------------

static int cmp_uint(const void *a, const void *b)
{
    unsigned int x = *(const unsigned int*)a, y = *(const unsigned int*)b;
    return (x > y) - (x < y);
}

START_TEST(test_merge_sort_1D)
{
    srand(1);
    for (unsigned int n = 1; n < 200; n += 7)
    {
        unsigned int *a = malloc(n * sizeof(unsigned int)), *b = malloc(n * sizeof(unsigned int));
        for (unsigned int i = 0; i < n; i++)
            a[i] = b[i] = (unsigned int)(rand() % 50);         // with repeated values
        merge_sort_1D(a, n);
        qsort(b, n, sizeof(unsigned int), cmp_uint);
        ck_assert_int_eq(memcmp(a, b, n * sizeof(unsigned int)), 0);
        free(a);
        free(b);
    }
}
END_TEST

START_TEST(test_id_to_loc_lookup)
{
    // Every id is found at its location; ids that are not in the network give N + 1
    unsigned int sizes[] = { 1, 2, 3, 10, 1000, 70000 };
    for (unsigned int s = 0; s < sizeof(sizes) / sizeof(sizes[0]); s++)
    {
        unsigned int N = sizes[s];
        Lookup *lookup = malloc(N * sizeof(Lookup));
        for (unsigned int i = 0; i < N; i++)
        {
            lookup[i].id = 3 * ((i * 7919u) % N) + 5;      // shuffled, spaced ids (5, 8, 11, ...)
            lookup[i].loc = i;
        }
        merge_sort_by_ids(lookup, N);
        for (unsigned int i = 1; i < N; i++)
            ck_assert_uint_lt(lookup[i - 1].id, lookup[i].id);
        for (unsigned int i = 0; i < N; i++)
        {
            unsigned int id = 3 * ((i * 7919u) % N) + 5;
            ck_assert_uint_eq(find_link_by_idtoloc(id, lookup, N), i);
            ck_assert_uint_eq(find_link_by_idtoloc(id + 1, lookup, N), N + 1);
        }
        ck_assert_uint_eq(find_link_by_idtoloc(0, lookup, N), N + 1);
        ck_assert_uint_eq(find_link_by_idtoloc(3 * N + 10, lookup, N), N + 1);
        free(lookup);
    }
}
END_TEST

// ---------------------------------------------------------------------------------------------------
// Runge-Kutta tables
// ---------------------------------------------------------------------------------------------------

typedef void (MethodBuilder)(RKMethod*);
static MethodBuilder *builders[] = { RKDense3_2, TheRKDense4_3, DOPRI5_dense };
static const char *names[] = { "RK 3(2)", "RK 4(3)", "Dormand-Prince 5(4)" };

static void build(int k, RKMethod *m)
{
    memset(m, 0, sizeof(RKMethod));
    builders[k](m);
}

static void release(RKMethod *m)
{
    free(m->b);
    free(m->b_theta);
    free(m->b_theta_deriv);
    free(m->w);
}

#define A_(m, i, j) ((m)->A[(i) * (m)->num_stages + (j)])

START_TEST(test_rk_order_conditions)
{
    RKMethod m;
    build(_i, &m);
    unsigned int s = m.num_stages, p = m.localorder;
    const double tol = 1e-14;

    // explicit: A strictly lower triangular
    for (unsigned int i = 0; i < s; i++)
        for (unsigned int j = i; j < s; j++)
            ck_assert_msg(A_(&m, i, j) == 0.0, "%s: A[%u][%u] != 0", names[_i], i, j);

    // c_i = sum_j A_ij
    for (unsigned int i = 0; i < s; i++)
    {
        double r = 0.0;
        for (unsigned int j = 0; j < s; j++)
            r += A_(&m, i, j);
        ck_assert_msg(fabs(r - m.c[i]) < tol, "%s: row sum %u = %.17g, c = %.17g", names[_i], i, r, m.c[i]);
    }

    // quadrature conditions sum_i b_i c_i^(k-1) = 1/k, k = 1..p
    for (unsigned int k = 1; k <= p; k++)
    {
        double sum = 0.0;
        for (unsigned int i = 0; i < s; i++)
            sum += m.b[i] * pow(m.c[i], k - 1);
        ck_assert_msg(fabs(sum - 1.0 / k) < tol, "%s: sum b c^%u = %.17g, expected 1/%u", names[_i], k - 1, sum, k);
    }

    // order 3: sum b_i A_ij c_j = 1/6; order 4: sum b A c^2 = 1/12, sum b c A c = 1/8, sum b A A c = 1/24
    double bAc = 0.0, bAc2 = 0.0, bcAc = 0.0, bAAc = 0.0;
    for (unsigned int i = 0; i < s; i++)
    {
        double Ac = 0.0, Ac2 = 0.0, AAc = 0.0;
        for (unsigned int j = 0; j < s; j++)
        {
            Ac += A_(&m, i, j) * m.c[j];
            Ac2 += A_(&m, i, j) * m.c[j] * m.c[j];
            double Acj = 0.0;
            for (unsigned int l = 0; l < s; l++)
                Acj += A_(&m, j, l) * m.c[l];
            AAc += A_(&m, i, j) * Acj;
        }
        bAc += m.b[i] * Ac;
        bAc2 += m.b[i] * Ac2;
        bcAc += m.b[i] * m.c[i] * Ac;
        bAAc += m.b[i] * AAc;
    }
    if (p >= 3)
        ck_assert_msg(fabs(bAc - 1.0 / 6.0) < tol, "%s: sum b A c = %.17g", names[_i], bAc);
    if (p >= 4)
    {
        ck_assert_msg(fabs(bAc2 - 1.0 / 12.0) < tol, "%s: sum b A c^2 = %.17g", names[_i], bAc2);
        ck_assert_msg(fabs(bcAc - 1.0 / 8.0) < tol, "%s: sum b c A c = %.17g", names[_i], bcAc);
        ck_assert_msg(fabs(bAAc - 1.0 / 24.0) < tol, "%s: sum b A A c = %.17g", names[_i], bAAc);
    }
    release(&m);
}
END_TEST

START_TEST(test_rk_error_estimators)
{
    // e and d are differences of two consistent formulas: their coefficients add up to 0
    RKMethod m;
    build(_i, &m);
    //(the tables have num_stages entries; for Dormand-Prince the 7th stage is the first of the next step)
    double se = 0.0, sd = 0.0, scale_e = 0.0, scale_d = 0.0;
    for (unsigned int i = 0; i < m.num_stages; i++)
    {
        se += m.e[i];
        sd += m.d[i];
        scale_e += fabs(m.e[i]);
        scale_d += fabs(m.d[i]);
    }
    //relative to the size of the coefficients (the d of Dormand-Prince are printed with 15 digits)
    ck_assert_msg(fabs(se) < 1e-14 * scale_e, "%s: sum e = %g", names[_i], se);
    ck_assert_msg(fabs(sd) < 1e-14 * scale_d, "%s: sum d = %g", names[_i], sd);
    release(&m);
}
END_TEST

START_TEST(test_rk_dense_output)
{
    RKMethod m;
    build(_i, &m);
    unsigned int s = m.num_stages;
    double *bt = malloc(s * sizeof(double)), *bd = malloc(s * sizeof(double));
    double *bp = malloc(s * sizeof(double)), *bm = malloc(s * sizeof(double));

    // theta = 1 is the step itself, theta = 0 its start
    m.dense_b(1.0, bt);
    for (unsigned int i = 0; i < s; i++)
        ck_assert_msg(fabs(bt[i] - m.b[i]) < 1e-14, "%s: b(1)[%u] = %.17g, b = %.17g", names[_i], i, bt[i], m.b[i]);
    m.dense_b(0.0, bt);
    for (unsigned int i = 0; i < s; i++)
        ck_assert_msg(fabs(bt[i]) < 1e-15, "%s: b(0)[%u] = %g", names[_i], i, bt[i]);

    for (double theta = 0.05; theta < 1.0; theta += 0.1)
    {
        // consistency: sum_i b_i(theta) = theta (a constant slope is integrated exactly)
        m.dense_b(theta, bt);
        double sum = 0.0;
        for (unsigned int i = 0; i < s; i++)
            sum += bt[i];
        ck_assert_msg(fabs(sum - theta) < 1e-14, "%s: sum b(%g) = %.17g", names[_i], theta, sum);

        // b'(theta) is the derivative of b(theta) (RK 4(3) does not provide b')
        if (!m.dense_bderiv)
            continue;
        const double eps = 1e-6;
        m.dense_bderiv(theta, bd);
        m.dense_b(theta + eps, bp);
        m.dense_b(theta - eps, bm);
        for (unsigned int i = 0; i < s; i++)
            ck_assert_msg(fabs((bp[i] - bm[i]) / (2 * eps) - bd[i]) < 1e-7, "%s: b'(%g)[%u]", names[_i], theta, i);
    }
    free(bt); free(bd); free(bp); free(bm);
    release(&m);
}
END_TEST

// One step of the method on y' = y from y(0) = 1; returns y(h), and in dense[] the dense output at theta.
static double rk_step_exp(const RKMethod *m, double h, double theta, double *dense)
{
    unsigned int s = m->num_stages;
    double k[16], bt[16];
    for (unsigned int i = 0; i < s; i++)
    {
        double y = 1.0;
        for (unsigned int j = 0; j < i; j++)
            y += h * A_(m, i, j) * k[j];
        k[i] = y;                                     // f(y) = y
    }
    double y1 = 1.0;
    for (unsigned int i = 0; i < s; i++)
        y1 += h * m->b[i] * k[i];
    m->dense_b(theta, bt);
    *dense = 1.0;
    for (unsigned int i = 0; i < s; i++)
        *dense += h * bt[i] * k[i];
    return y1;
}

START_TEST(test_rk_observed_order)
{
    // The local error of one step is O(h^(p+1)); halving h divides it by about 2^(p+1).
    // The dense output has order d_order: its local error is O(h^(d_order+1)).
    RKMethod m;
    build(_i, &m);
    unsigned int p = m.localorder;
    double dense, err[2], derr[2], h = 0.2;
    for (int r = 0; r < 2; r++, h /= 2)
    {
        err[r] = fabs(rk_step_exp(&m, h, 0.5, &dense) - exp(h));
        derr[r] = fabs(dense - exp(0.5 * h));
    }
    double order = log2(err[0] / err[1]) - 1.0;
    double dorder = log2(derr[0] / derr[1]) - 1.0;
    ck_assert_msg(fabs(order - p) < 0.3, "%s: observed order %.2f, expected %u", names[_i], order, p);
    ck_assert_msg(dorder > m.d_order - 0.3, "%s: dense output order %.2f, expected at least %u", names[_i], dorder, m.d_order);
    release(&m);
}
END_TEST

// ---------------------------------------------------------------------------------------------------
// built-in models
// ---------------------------------------------------------------------------------------------------

// Every model number known to SetParamSizes.
static const unsigned short model_uids[] = {
    0, 1, 2, 3, 4, 5, 6, 15, 19, 20, 21, 22, 23, 30, 40, 60, 101, 105, 190, 191, 192, 193, 194, 195, 196, 200, 219,
    225, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 300, 301, 315, 400, 401,
    402, 403, 404, 405, 601, 602, 603, 604, 605, 606, 607, 608, 609, 654, 2000 };

// Model numbers that have sizes but no equations in ASYNCH: 200 is meant for another program (SIMPLE),
// 260 has its equation commented out, 300, 301, 315, 607 and 2000 have no InitRoutines branch.
// Initialize_Model refuses them with an error message instead of crashing at the first step.
static const unsigned short unusable_uids[] = { 200, 260, 300, 301, 315, 607, 2000 };

static bool is_unusable(unsigned short uid)
{
    for (unsigned int k = 0; k < sizeof(unusable_uids) / sizeof(unusable_uids[0]); k++)
        if (unusable_uids[k] == uid)
            return true;
    return false;
}

// SetParamSizes prints a warning when the global file gives more global parameters than the model needs;
// the tests give many, so standard output is silenced meanwhile.
static int saved_stdout = -1;
static void quiet(void) { fflush(stdout); saved_stdout = dup(1); int fd = open("/dev/null", O_WRONLY); dup2(fd, 1); close(fd); }
static void loud(void) { fflush(stdout); dup2(saved_stdout, 1); close(saved_stdout); }

// Problems are collected for all models, then reported together.
static char problems[8192];
static void problem(const char *fmt, unsigned int uid, unsigned int a, unsigned int b)
{
    size_t n = strlen(problems);
    snprintf(problems + n, sizeof(problems) - n, "\n  model %u: ", uid);
    n = strlen(problems);
    snprintf(problems + n, sizeof(problems) - n, fmt, a, b);
}

START_TEST(test_model_sizes)
{
    problems[0] = '\0';
    for (unsigned int k = 0; k < sizeof(model_uids) / sizeof(model_uids[0]); k++)
    {
        unsigned short uid = model_uids[k];
        GlobalVars g;
        memset(&g, 0, sizeof(g));
        g.model_uid = uid;
        g.num_global_params = 100;
        quiet();
        SetParamSizes(&g, NULL);
        loud();
        if (g.num_disk_params > g.num_params)
            problem("%u parameters read from disk, but room for %u", uid, g.num_disk_params, g.num_params);
        if (g.num_params && (g.area_idx >= g.num_params || g.areah_idx >= g.num_params))
            problem("area indices %u/%u out of range", uid, g.area_idx, g.areah_idx);
        if (g.num_forcings > ASYNCH_MAX_DB_CONNECTIONS - ASYNCH_DB_LOC_FORCING_START)
            problem("%u forcings (at most %u)", uid, g.num_forcings, ASYNCH_MAX_DB_CONNECTIONS - ASYNCH_DB_LOC_FORCING_START);
    }
    ck_assert_msg(problems[0] == '\0', "model sizes:%s", problems);
}
END_TEST

START_TEST(test_model_routines)
{
    // For every model (no dam, no reservoir, explicit solver): the state vector is described consistently,
    // and the functions the time-step routines always call are set.
    problems[0] = '\0';
    for (unsigned int k = 0; k < sizeof(model_uids) / sizeof(model_uids[0]); k++)
    {
        unsigned short uid = model_uids[k];
        if (is_unusable(uid))
            continue;
        Link link;
        memset(&link, 0, sizeof(link));
        link.ID = 1;
        quiet();
        InitRoutines(&link, uid, 0, 0, NULL);
        loud();
        if (link.dim == 0)
            problem("dim = 0%.0u%.0u", uid, 0, 0);
        if (!(link.diff_start <= link.no_ini_start && link.no_ini_start <= link.dim))
            problem("no_ini_start %u, dim %u", uid, link.no_ini_start, link.dim);
        if (link.num_dense == 0)
            problem("no dense state%.0u%.0u", uid, 0, 0);
        for (unsigned int i = 0; i < link.num_dense; i++)
            if (link.dense_indices[i] >= link.dim)
                problem("dense index %u >= dim %u", uid, link.dense_indices[i], link.dim);
        if (!link.solver)
            problem("no solver%.0u%.0u", uid, 0, 0);
        if (!link.differential)
            problem("no equations%.0u%.0u", uid, 0, 0);
        if (!link.check_consistency)
            problem("no consistency check (called at every stage)%.0u%.0u", uid, 0, 0);
        free(link.dense_indices);
    }
    ck_assert_msg(problems[0] == '\0', "model routines:%s", problems);
}
END_TEST

START_TEST(test_model_without_equations)
{
    for (unsigned int k = 0; k < sizeof(unusable_uids) / sizeof(unusable_uids[0]); k++)
    {
        Link link;
        memset(&link, 0, sizeof(link));
        quiet();
        InitRoutines(&link, unusable_uids[k], 0, 0, NULL);
        loud();
        ck_assert_msg(link.differential == NULL, "model %u now has equations: move it to the tested models",
            unusable_uids[k]);
        free(link.dense_indices);
    }
}
END_TEST


// Every usable model evaluated once at a generic point: parameters and global parameters with distinct values
// (so that no difference of two of them is 0), states = 0.1, two upstream links with states 0.1, forcings = 1. The derivatives must be
// finite numbers. Each model runs in a child process, so that a crash is reported as a failure of that model.
static int evaluate_model(unsigned short uid)
{
    GlobalVars g;
    memset(&g, 0, sizeof(g));
    g.model_uid = uid;
    g.num_global_params = 64;
    SetParamSizes(&g, NULL);

    double gp[64], params[128], y[64], yp[2 * 64], forcing[16], ans[64];
    for (unsigned int i = 0; i < 64; i++) gp[i] = 0.3 + 0.1 * i;      // distinct: differences of parameters are not 0
    for (unsigned int i = 0; i < 128; i++) params[i] = 0.2 + 0.037 * i;  // distinct, and never 1 (lambda_1 = 1 divides by 0)
    for (unsigned int i = 0; i < 16; i++) forcing[i] = 1.0;

    Link link;
    memset(&link, 0, sizeof(link));
    link.ID = 1;
    link.num_params = g.num_params;
    link.params = params;
    InitRoutines(&link, uid, 0, 0, NULL);
    if (uid == 257)
        params[3] = 3.0;                        // model 257: parameter 3 is a stream order, 1 to 10
    ConvertParams(params, uid, NULL);
    Precalculations(&link, gp, g.num_global_params, params, g.num_disk_params, g.num_params, 0, uid, NULL);

    unsigned int dim = link.dim;
    for (unsigned int i = 0; i < dim; i++) y[i] = 0.1;
    for (unsigned int i = 0; i < 2 * 64; i++) yp[i] = 0.1;
    // the discontinuity state, as the solver gets it (-1 = no dam for the dam models)
    int state = ReadInitData(gp, g.num_global_params, params, g.num_params, NULL, 0, y, dim, uid, link.diff_start,
        link.no_ini_start, NULL, NULL);
    if (link.check_state)
        state = link.check_state(y, dim, gp, g.num_global_params, params, g.num_params, NULL, false, NULL);
    if (link.algebraic)
        link.algebraic(y, dim, gp, params, NULL, state, NULL, y);
    for (unsigned int i = 0; i < 64; i++) ans[i] = 0.0;
    link.differential(0.0, y, dim, yp, 2, dim, gp, params, forcing, NULL, state, NULL, ans);
    for (unsigned int i = link.diff_start; i < dim; i++)
        if (!isfinite(ans[i]))
            return 2;
    return 0;
}

START_TEST(test_model_equations_finite)
{
    problems[0] = '\0';
    for (unsigned int k = 0; k < sizeof(model_uids) / sizeof(model_uids[0]); k++)
    {
        unsigned short uid = model_uids[k];
        if (is_unusable(uid))
            continue;
        fflush(stdout);
        pid_t pid = fork();
        if (pid == 0)
        {
            quiet();
            exit(evaluate_model(uid));          // exit, not _exit: coverage builds write their counters at exit
        }
        int status = 0;
        waitpid(pid, &status, 0);
        if (WIFSIGNALED(status))
            problem("crashed (signal %u)%.0u", uid, WTERMSIG(status), 0);
        else if (WEXITSTATUS(status) == 2)
            problem("a derivative is not a finite number%.0u%.0u", uid, 0, 0);
        else if (WEXITSTATUS(status) != 0)
            problem("exit status %u%.0u", uid, WEXITSTATUS(status), 0);
    }
    ck_assert_msg(problems[0] == '\0', "model equations:%s", problems);
}
END_TEST

// ---------------------------------------------------------------------------------------------------
// equations
// ---------------------------------------------------------------------------------------------------

START_TEST(test_model190_recession)
{
    // No rain, no evaporation, empty hillslope, no parents: dq/dt = -invtau q^(lambda_1) q
    double g[6] = { 0.33, 0.2, -0.1, 0.33, 0.1, 2.2917e-5 };
    double p[8] = { 1.5, 500.0, 2e5, 0 };
    Link link;
    memset(&link, 0, sizeof(link));
    Precalculations(&link, g, 6, p, 3, 8, 0, 190, NULL);
    ck_assert(p[5] > 0.0);                                           // invtau
    ck_assert(fabs(p[6] - 0.33 * 0.001 / 60.0) < 1e-20);            // c_1
    ck_assert(fabs(p[6] + p[7] - 0.001 / 60.0) < 1e-20);            // c_1 + c_2: all the rain

    double y[3] = { 2.0, 0.0, 0.0 }, f[2] = { 0.0, 0.0 }, ans[3];
    LinearHillslope_MonthlyEvap(0.0, y, 3, NULL, 0, 3, g, p, f, NULL, 0, NULL, ans);
    ck_assert(fabs(ans[0] - (-p[5] * pow(2.0, 0.2) * 2.0)) < 1e-15);
    ck_assert(ans[1] == 0.0 && ans[2] == 0.0);

    // Rain only fills the hillslope stores, split by RC
    f[0] = 10.0;
    LinearHillslope_MonthlyEvap(0.0, y, 3, NULL, 0, 3, g, p, f, NULL, 0, NULL, ans);
    ck_assert(fabs(ans[1] - 10.0 * p[6]) < 1e-20);
    ck_assert(fabs(ans[2] - 10.0 * p[7]) < 1e-20);

    // Parents add their discharge to the inflow
    double parents[2 * 3] = { 0.5, 0.0, 0.0, 0.25, 0.0, 0.0 };
    f[0] = 0.0;
    LinearHillslope_MonthlyEvap(0.0, y, 3, parents, 2, 3, g, p, f, NULL, 0, NULL, ans);
    ck_assert(fabs(ans[0] - p[5] * pow(2.0, 0.2) * (0.75 - 2.0)) < 1e-15);
}
END_TEST

START_TEST(test_consistency_checks)
{
    double y[4] = { -1.0, -2.0, 3.0, -0.0 };
    CheckConsistency_Nonzero_AllStates_q(y, 4, NULL, 0, NULL, 0, NULL);
    ck_assert(y[0] == 1e-14 && y[1] == 0.0 && y[2] == 3.0 && y[3] == 0.0);
    double z[3] = { 0.0, -1.0, -1.0 };
    CheckConsistency_Nonzero_3States(z, 3, NULL, 0, NULL, 0, NULL);
    ck_assert(z[0] == 1e-14 && z[1] == 0.0 && z[2] == 0.0);
}
END_TEST

// ---------------------------------------------------------------------------------------------------
// asynch_api.h: model specification
// ---------------------------------------------------------------------------------------------------

static void dummy_rhs(double t, const double * const y_i, unsigned int dim, const double * const y_p,
    unsigned short num_parents, unsigned int max_dim, const double * const gp, const double * const p,
    const double * const f, const QVSData * const qvs, int state, void *user, double *ans)
{
    ans[0] = -y_i[0];
}

START_TEST(test_model_spec_checks)
{
    ck_assert_ptr_eq(Asynch_Model_Spec_Create(0, 1, 1, 1, 0), NULL);    // no state
    ck_assert_ptr_eq(Asynch_Model_Spec_Create(1, 1, 1, 2, 0), NULL);    // more disk than total parameters
    ck_assert_ptr_eq(Asynch_Model_Spec_Create(1, 1, 1, 1, 11), NULL);   // too many forcings

    AsynchModelSpec *spec = Asynch_Model_Spec_Create(3, 2, 4, 2, 1);
    ck_assert_ptr_ne(spec, NULL);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Differential(spec, NULL), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Differential(spec, dummy_rhs), 0);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Num_Initial_States(spec, 4), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Num_Initial_States(spec, 2), 0);
    unsigned int bad[] = { 0, 3 }, good[] = { 0, 2 };
    ck_assert_int_eq(Asynch_Model_Spec_Set_Dense_Indices(spec, 2, bad), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Dense_Indices(spec, 0, good), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Dense_Indices(spec, 2, good), 0);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Nonnegative(spec, 3), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Nonnegative(spec, 2), 0);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Areas(spec, 4, 0, false), 1);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Areas(spec, 3, 0, true), 0);
    double factors[] = { 1000.0, 1e6 };
    ck_assert_int_eq(Asynch_Model_Spec_Set_Param_Factors(spec, factors), 0);
    ck_assert_int_eq(Asynch_Model_Spec_Set_Param_Factors(spec, NULL), 0);
    ck_assert_int_eq(Asynch_Install_Model(NULL, spec), 1);
    Asynch_Model_Spec_Free(spec);
    Asynch_Model_Spec_Free(NULL);
}
END_TEST

START_TEST(test_api_without_network)
{
    // The accessors do not crash on a solver that has not read anything yet
    AsynchSolver *asynch = Asynch_Init_World(false);
    ck_assert_ptr_ne(asynch, NULL);
    ck_assert_int_eq(Asynch_Get_Rank(asynch), 0);
    ck_assert_uint_eq(Asynch_Get_Num_Links(asynch), 0);
    ck_assert_int_eq(Asynch_Find_Link(asynch, 1), -1);
    ck_assert_uint_eq(Asynch_Get_Link_ID(asynch, 0), 0);
    ck_assert_int_eq(Asynch_Get_Link_Owner(asynch, 0), -1);
    ck_assert_int_eq(Asynch_Get_Link_Child(asynch, 0), -1);
    ck_assert_uint_eq(Asynch_Get_Max_Dim(asynch), 0);
    ck_assert_uint_eq(Asynch_Get_Size_Global_Parameters(asynch), 0);
    double buf[4];
    ck_assert_int_eq(Asynch_Get_Link_Params(asynch, 0, buf), 1);
    ck_assert_int_eq(Asynch_Get_Link_State(asynch, 0, buf, NULL), 1);
    ck_assert_int_eq(Asynch_Update_Precalculations(asynch), 1);
    Asynch_Free(asynch);                                          // B-17: must not crash before loading
}
END_TEST

// ---------------------------------------------------------------------------------------------------

Suite *asynch_suite(void)
{
    Suite *s = suite_create("Asynch");

    TCase *tc = tcase_create("dates");
    tcase_add_test(tc, test_date_manip_days_in_month);
    suite_add_tcase(s, tc);

    tc = tcase_create("sort");
    tcase_add_test(tc, test_merge_sort_1D);
    tcase_add_test(tc, test_id_to_loc_lookup);
    suite_add_tcase(s, tc);

    tc = tcase_create("rk");
    tcase_add_loop_test(tc, test_rk_order_conditions, 0, 3);
    tcase_add_loop_test(tc, test_rk_error_estimators, 0, 3);
    tcase_add_loop_test(tc, test_rk_dense_output, 0, 3);
    tcase_add_loop_test(tc, test_rk_observed_order, 0, 3);
    suite_add_tcase(s, tc);

    tc = tcase_create("models");
    tcase_add_test(tc, test_model_sizes);
    tcase_add_test(tc, test_model_routines);
    tcase_add_test(tc, test_model_without_equations);
    tcase_add_test(tc, test_model_equations_finite);
    tcase_set_timeout(tc, 120);
    suite_add_tcase(s, tc);

    tc = tcase_create("equations");
    tcase_add_test(tc, test_model190_recession);
    tcase_add_test(tc, test_consistency_checks);
    suite_add_tcase(s, tc);

    tc = tcase_create("api");
    tcase_add_test(tc, test_model_spec_checks);
    tcase_add_test(tc, test_api_without_network);
    suite_add_tcase(s, tc);

    return s;
}

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);

    SRunner *sr = srunner_create(asynch_suite());
    srunner_set_fork_status(sr, CK_NOFORK);          // MPI and fork() do not mix
    srunner_run_all(sr, CK_NORMAL);
    int number_failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    MPI_Finalize();
    return (number_failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
