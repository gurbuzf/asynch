#if !defined(_MSC_VER)
#include <config.h>
#else 
#include <config_msvc.h>
#endif

#include <assert.h>
#include <math.h>
#include <memory.h>

#include <minmax.h>
#include <system.h>
#include <blas.h>
#include <io.h>
#include <rksteppers.h>


//LU decomposition with partial pivoting of the dim x dim matrix W (row-major), in place. Returns 1 if W is singular.
static int lu_decompose(double *W, int *piv, unsigned int dim)
{
    for (unsigned int k = 0; k < dim; k++)
    {
        unsigned int p = k;
        for (unsigned int i = k + 1; i < dim; i++)
            if (fabs(W[i * dim + k]) > fabs(W[p * dim + k]))
                p = i;
        piv[k] = (int)p;
        if (W[p * dim + k] == 0.0)
            return 1;
        if (p != k)
            for (unsigned int j = 0; j < dim; j++)
            {
                double tmp = W[k * dim + j];
                W[k * dim + j] = W[p * dim + j];
                W[p * dim + j] = tmp;
            }
        for (unsigned int i = k + 1; i < dim; i++)
        {
            double m = (W[i * dim + k] /= W[k * dim + k]);
            if (m != 0.0)
                for (unsigned int j = k + 1; j < dim; j++)
                    W[i * dim + j] -= m * W[k * dim + j];
        }
    }
    return 0;
}

//Solves W x = b with the factors of lu_decompose; b is overwritten by x.
static void lu_solve(const double *LU, const int *piv, unsigned int dim, double *b)
{
    for (unsigned int k = 0; k < dim; k++)
    {
        unsigned int p = (unsigned int)piv[k];
        if (p != k)
        {
            double tmp = b[k];
            b[k] = b[p];
            b[p] = tmp;
        }
        for (unsigned int i = k + 1; i < dim; i++)
            b[i] -= LU[i * dim + k] * b[k];
    }
    for (unsigned int k = dim; k-- > 0;)
    {
        for (unsigned int j = k + 1; j < dim; j++)
            b[k] -= LU[k * dim + j] * b[j];
        b[k] /= LU[k * dim + k];
    }
}

//Jacobian of the equations of link_i at (t, y), row-major (J[i * dim + j] = d f_i / d y_j): the model's own
//(link->jacobian) or forward finite differences (dim more evaluations). f0 = f(t, y), y_p the parents' states.
static void Jacobian(Link* link_i, GlobalVars* globals, double t, const double *y, const double *f0, const double *y_p,
    double *J, double *y_pert, double *f_pert)
{
    unsigned int dim = link_i->dim;
    if (link_i->jacobian)
    {
        memset(J, 0, dim * dim * sizeof(double));
        link_i->jacobian(t, y, dim, y_p, link_i->num_parents, globals->max_dim, globals->global_params,
            link_i->params, link_i->my->forcing_values, J);
        return;
    }
    memcpy(y_pert, y, dim * sizeof(double));
    for (unsigned int j = 0; j < dim; j++)
    {
        double delta = 1.4901161193847656e-08 * max(fabs(y[j]), 1e-6);   //sqrt(machine epsilon) * scale
        y_pert[j] = y[j] + delta;
        link_i->differential(t, y_pert, dim, y_p, link_i->num_parents, globals->max_dim, globals->global_params,
            link_i->params, link_i->my->forcing_values, link_i->qvs, link_i->state, link_i->user, f_pert);
        for (unsigned int i = 0; i < dim; i++)
            J[i * dim + j] = (f_pert[i] - f0[i]) / delta;
        y_pert[j] = y[j];
    }
}

//Interpolates the dense states of the parents of link_i at time tau into y_p ([max_parents][max_dim]), and applies the
//consistency check, as ExplicitRKSolver does for each stage. If nodes is not NULL, the node of each parent that
//contains tau is stored there (to free the older nodes after an accepted step).
static void ParentsAt(Link* link_i, GlobalVars* globals, double tau, double *y_p, RKSolutionNode **nodes)
{
    for (unsigned int i = 0; i < link_i->num_parents; i++)
    {
        Link* curr_parent = link_i->parents[i];
        RKSolutionNode *node = curr_parent->my->list.head;
        double t_needed = min(tau, curr_parent->last_t);
        while (t_needed > node->t)
            node = node->next;
        if (node != curr_parent->my->list.head)
            node = node->prev;
        if (nodes)
            nodes[i] = node;

        double dt = node->next->t - node->t;
        curr_parent->method->dense_b((t_needed - node->t) / dt, curr_parent->method->b_theta);
        double *parent_approx = y_p + i * globals->max_dim;
        for (unsigned int m = 0; m < curr_parent->num_dense; m++)
        {
            unsigned int idx = curr_parent->dense_indices[m];
            double approx = node->y_approx[idx];
            for (int l = 0; l < curr_parent->method->num_stages; l++)
                approx += dt * curr_parent->method->b_theta[l] * node->next->k[l * curr_parent->num_dense + m];
            parent_approx[idx] = approx;
        }
        link_i->check_consistency(parent_approx, curr_parent->dim, globals->global_params, globals->num_global_params, curr_parent->params, link_i->num_params, curr_parent->user);
    }
}

//Computes one step of a Rosenbrock method in the form of RODAS (Rodas5P_dense, numerical solver index 4) at a link,
//for stiff equations: the step size is limited by accuracy, not by stability. Same interface and bookkeeping as
//ExplicitRKSolver (explicit.c); the parents' solutions are interpolated at each stage time.
//Returns 1 if the step was successfully taken, 0 if the step was rejected.
int RosenbrockSolver(Link* link_i, GlobalVars* globals, int* assignments, bool print_flag, FILE* outputfile, ConnData* conninfo, Forcing* forcings, Workspace* workspace)
{
    unsigned int idx;
    RKSolutionNode *curr_node[ASYNCH_LINK_MAX_PARENTS], *node, *new_node;
    double current_theta;

    double *y_0 = link_i->my->list.tail->y_approx;
    double h = link_i->h;
    double t = link_i->my->list.tail->t;
    RKMethod* meth = link_i->method;
    const unsigned int s = meth->ros_stages;
    const double * const A = meth->A;
    const double * const C = meth->ros_C;
    const double * const c = meth->c;
    const double * const d = meth->ros_d;
    const double * const H = meth->ros_H;
    const double * const b = meth->ros_b;
    const double * const btilde = meth->ros_btilde;
    unsigned int num_stages = meth->num_stages;
    ErrorData* error = link_i->my->error_data;
    unsigned int dim = link_i->dim;
    unsigned int num_dense = link_i->num_dense;
    unsigned int* dense_indices = link_i->dense_indices;
    double *temp = workspace->temp;
    double *sum = workspace->sum;
    double **temp_k = workspace->temp_k_slices;
    const unsigned int max_dim = globals->max_dim;
    double *y_p = workspace->parents_approx;
    double *F = workspace->ros_vec;                 //f at a stage
    double *T = F + max_dim;                        //df/dt
    double *u = T + max_dim;                        //stage value
    double *f_pert = u + max_dim;
    double *k = f_pert + max_dim;                   //stages [s][max_dim]
    assert(s <= 12);                                //room in workspace->ros_vec (Create_Workspace)
    double *J = workspace->ros_J;
    double *M = workspace->ros_W;
    int *piv = workspace->ros_piv;

    //f, df/dt (forward difference: the equations depend on t through the parents' solutions) and the Jacobian at t
    ParentsAt(link_i, globals, t, y_p, NULL);
    link_i->differential(t, y_0, dim, y_p, link_i->num_parents, max_dim, globals->global_params, link_i->params,
        link_i->my->forcing_values, link_i->qvs, link_i->state, link_i->user, F);
    Jacobian(link_i, globals, t, y_0, F, y_p, J, u, f_pert);
    double delta = 1e-6 * h;
    ParentsAt(link_i, globals, t + delta, y_p, NULL);
    link_i->differential(t + delta, y_0, dim, y_p, link_i->num_parents, max_dim, globals->global_params,
        link_i->params, link_i->my->forcing_values, link_i->qvs, link_i->state, link_i->user, T);
    for (unsigned int i = 0; i < dim; i++)
        T[i] = (T[i] - F[i]) / delta;

    //M = I / (h gamma) - J
    for (unsigned int i = 0; i < dim; i++)
        for (unsigned int j = 0; j < dim; j++)
            M[i * dim + j] = (i == j ? 1.0 / (h * meth->ros_gamma) : 0.0) - J[i * dim + j];
    new_node = New_Step(&link_i->my->list);
    new_node->t = t + h;
    double *new_y = new_node->y_approx;
    if (lu_decompose(M, piv, dim))
    {
        Undo_Step(&link_i->my->list);
        link_i->h = h * error->facmin;
        return 0;
    }

    //Stages
    for (unsigned int i = 0; i < s; i++)
    {
        double *k_i = k + i * max_dim;
        if (i > 0)
        {
            for (unsigned int m = 0; m < dim; m++)
            {
                u[m] = y_0[m];
                for (unsigned int j = 0; j < i; j++)
                    u[m] += A[i * s + j] * k[j * max_dim + m];
            }
            link_i->check_consistency(u, dim, globals->global_params, globals->num_global_params, link_i->params, link_i->num_params, link_i->user);
            ParentsAt(link_i, globals, t + c[i] * h, y_p, (i == s - 1) ? curr_node : NULL);
            link_i->differential(t + c[i] * h, u, dim, y_p, link_i->num_parents, max_dim, globals->global_params,
                link_i->params, link_i->my->forcing_values, link_i->qvs, link_i->state, link_i->user, F);
        }
        for (unsigned int m = 0; m < dim; m++)
        {
            double r = F[m] + h * d[i] * T[m];
            for (unsigned int j = 0; j < i; j++)
                r += C[i * s + j] / h * k[j * max_dim + m];
            k_i[m] = r;
        }
        lu_solve(M, piv, dim, k_i);
    }
    if (s == 1)
        ParentsAt(link_i, globals, t + h, y_p, curr_node);

    //Solution, stored dense output vectors, error
    for (unsigned int m = 0; m < dim; m++)
    {
        double y1 = y_0[m], err = 0.0, K1 = 0.0, K2 = 0.0, K3 = 0.0;
        for (unsigned int i = 0; i < s; i++)
        {
            double km = k[i * max_dim + m];
            y1 += b[i] * km;
            err += btilde[i] * km;
            K1 += H[0 * s + i] * km;
            K2 += H[1 * s + i] * km;
            K3 += H[2 * s + i] * km;
        }
        new_y[m] = y1;
        sum[m] = err;
        temp_k[1][m] = K1 / h;
        temp_k[2][m] = K2 / h;
        temp_k[3][m] = K3 / h;
    }
    link_i->check_consistency(new_y, dim, globals->global_params, globals->num_global_params, link_i->params, link_i->num_params, link_i->user);
    for (unsigned int m = 0; m < dim; m++)
        temp_k[0][m] = (new_y[m] - y_0[m]) / h;
    new_node->state = link_i->state;

    for (unsigned int i = 0; i < dim; i++)
        temp[i] = max(fabs(new_y[i]), fabs(y_0[i])) * error->reltol[i] + error->abstol[i];
    double err_1 = nrminf2(sum, temp, 0, dim);
    double value_1 = pow(1.0 / err_1, 1.0 / meth->e_order);
    double err_d = err_1;       //the dense output has its own order (4) but no separate estimate
    double value_d = pow(1.0 / err_d, 1.0 / meth->d_order);

    //Determine a new step size for the next step
    double step_1 = h * min(error->facmax, max(error->facmin, error->fac * value_1));
    double step_d = h * min(error->facmax, max(error->facmin, error->fac * value_d));
    link_i->h = min(step_1, step_d);

    if (err_1 < 1.0 && err_d < 1.0)
    {
        //Check if a discontinuity has been stepped on
        if (link_i->discont_count > 0 && (t + h) >= link_i->discont[link_i->discont_start])
        {
            (link_i->discont_count)--;
            link_i->discont_start = (link_i->discont_start + 1) % globals->discont_size;
            link_i->h = InitialStepSize(link_i->last_t, link_i, globals, workspace);
        }

        //Save the new data
		// adlz
		// printf("+Saving the data as (%f < 1.0) and (%f < 1.0)...\n", err_1, err_d);
        link_i->last_t = t + h;
        link_i->current_iterations++;
        store_k(workspace->temp_k, globals->max_dim, new_node->k, num_stages, dense_indices, num_dense);

        //Check if new data should be written to disk
        if (print_flag)
        {
            //while(t <= link_i->next_save && link_i->next_save <= link_i->last_t)
            while (t <= link_i->next_save && (link_i->next_save < link_i->last_t || fabs(link_i->next_save - link_i->last_t) / link_i->next_save < 1e-12))
            {
                if (link_i->disk_iterations == link_i->expected_file_vals)
                {
                    printf("[%i]: Warning: Too many steps computed for link id %u. Expected no more than %u. No more values will be stored for this link.\n", my_rank, link_i->ID, link_i->expected_file_vals);
                    break;
                }
                (link_i->disk_iterations)++;
                node = link_i->my->list.tail->prev;
                current_theta = (link_i->next_save - t) / h;
                link_i->method->dense_b(current_theta, link_i->method->b_theta);
                for (unsigned int m = 0; m < num_dense; m++)
                {
                    idx = dense_indices[m];
                    double approx = node->y_approx[idx];
                    for (unsigned int l = 0; l < link_i->method->num_stages; l++)
                        approx += h * link_i->method->b_theta[l] * node->next->k[l * num_dense + m];

                    sum[idx] = approx;
                }

                link_i->check_consistency(sum, link_i->dim, globals->global_params, globals->num_global_params, link_i->params, link_i->num_params, link_i->user);

                //Write to a file
                WriteStep(globals->outputs, globals->num_outputs, outputfile, link_i->ID, link_i->next_save, sum, link_i->dim, &(link_i->pos_offset));

                link_i->next_save += link_i->print_time;
            }
        }

        //Check if this is a peak value. The steps are long, so the crest is searched inside the step with the dense
        //output (16 points), not only at its end.
        if (link_i->peak_flag)
        {
            double best_theta = 1.0, best_q = new_y[0];
            for (unsigned int j = 1; j < 16; j++)
            {
                double th = j / 16.0, t1 = th * (1.0 - th);
                double q = y_0[0] + h * (th * temp_k[0][0] + t1 * (temp_k[1][0] + th * (temp_k[2][0] + th * temp_k[3][0])));
                if (q > best_q)
                {
                    best_q = q;
                    best_theta = th;
                }
            }
            if (best_q > link_i->peak_value[0])
            {
                if (best_theta == 1.0)
                    dcopy(new_y, link_i->peak_value, 0, link_i->dim);
                else
                {
                    double th = best_theta, t1 = th * (1.0 - th);
                    for (unsigned int m = 0; m < dim; m++)
                        link_i->peak_value[m] = y_0[m] + h * (th * temp_k[0][m] + t1 * (temp_k[1][m] + th * (temp_k[2][m] + th * temp_k[3][m])));
                }
                link_i->peak_time = t + best_theta * h;
            }
        }

        //Check if the newest step is on a change in rainfall
        short int propagated = 0;	//Set to 1 when last_t has been propagated
        for (unsigned int j = 0; j < globals->num_forcings; j++)
        {
            if (forcings[j].active && (link_i->my->forcing_data[j].num_points > 0) && (fabs(link_i->last_t - link_i->my->forcing_change_times[j]) < 1e-8))
            {
                //Propagate the discontinuity to downstream links
                if (!propagated)
                {
                    propagated = 1;
                    Link* next = link_i->child;
                    Link* prev = link_i;
                    for (unsigned int i = 0; i < globals->max_localorder && next != NULL; i++)
                    {
                        if (assignments[next->location] == my_rank && i < next->method->localorder)
                        {
                            //Insert the time into the discontinuity list
                            next->discont_end = Insert_Discontinuity(link_i->my->forcing_change_times[j], next->discont_start, next->discont_end, &(next->discont_count), globals->discont_size, next->discont, next->ID);
                        }
                        else if (next != NULL && assignments[next->location] != my_rank)
                        {
                            //Store the time to send to another process
                            Insert_SendDiscontinuity(link_i->my->forcing_change_times[j], i, &(prev->discont_send_count), globals->discont_size, prev->discont_send, prev->discont_order_send, prev->ID);
                            break;
                        }

                        prev = next;
                        next = next->child;
                    }
                }

                //Find the right index in rainfall
                //for(l=1;l<link_i->my->forcing_data[j].n_times;l++)
                unsigned int l;
                for (l = link_i->my->forcing_indices[j] + 1; l < link_i->my->forcing_data[j].num_points; l++)
                    if (fabs(link_i->my->forcing_change_times[j] - link_i->my->forcing_data[j].data[l].time) < 1e-8)
                        break;
                link_i->my->forcing_indices[j] = l;

                double forcing_buffer = link_i->my->forcing_data[j].data[l].value;
                link_i->my->forcing_values[j] = forcing_buffer;

                //Find and set the new change in rainfall
                unsigned int i;
                for (i = l + 1; i < link_i->my->forcing_data[j].num_points; i++)
                {
                    //if(link_i->my->forcing_data[j].rainfall[i].value != forcing_buffer)
                    if (fabs(link_i->my->forcing_data[j].data[i].value - forcing_buffer) > 1e-8)
                    {
                        link_i->my->forcing_change_times[j] = link_i->my->forcing_data[j].data[i].time;
                        break;
                    }
                }
                if (i == link_i->my->forcing_data[j].num_points)
                    link_i->my->forcing_change_times[j] = link_i->my->forcing_data[j].data[i - 1].time;
            }
        }

        //Select new step size, if forcings changed
        if (propagated)
            link_i->h = InitialStepSize(link_i->last_t, link_i, globals, workspace);

        //Free up parents' old data
        for (unsigned int i = 0; i < link_i->num_parents; i++)
        {
            Link *curr_parent = link_i->parents[i];
            while (curr_parent->my->list.head != curr_node[i])
            {
                Remove_Head_Node(&curr_parent->my->list);
                curr_parent->current_iterations--;
                curr_parent->iters_removed++;
            }
        }

        return 1;
    }
    else
    {
		// adlz
		// printf("+Trashing the data as (%f > 1.0) or (%f > 1.0)...\n", err_1, err_d);

        //Trash the data from the failed step
        Undo_Step(&link_i->my->list);

        return 0;
    }
}
