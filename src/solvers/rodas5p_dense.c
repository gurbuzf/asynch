#if !defined(_MSC_VER)
#include <config.h>
#else 
#include <config_msvc.h>
#endif

#include <stdlib.h>

#include <rkmethods.h>

void Rodas5P_b(double theta, double *b);
void Rodas5P_bderiv(double theta, double *b);

//Builds Rodas5P: a Rosenbrock method of order 5 with 8 stages, L-stable and stiffly accurate, with an embedded error
//estimate of order 4 and a dense output of order 4. G. Steinebach, Construction of Rosenbrock-Wanner method Rodas5P
//and numerical benchmarks within the Julia Differential Equations package, BIT Numerical Mathematics 63, 27 (2023).
//The coefficients are those of OrdinaryDiffEq.jl (lib/OrdinaryDiffEqRosenbrock/src/rosenbrock_tableaus.jl), in the
//form of E. Hairer and G. Wanner's RODAS: with M = I / (h gamma) - J,
//  M k_i = f(t + c_i h, y + sum_j A_ij k_j) + h d_i df/dt + sum_j (C_ij / h) k_j,   y1 = y + sum_i b_i k_i,
//  error = sum_i btilde_i k_i,
//  y(t + theta h) = y + theta (y1 - y) + theta (1 - theta) (K1 + theta K2 + theta^2 K3),   K_j = sum_i H_ji k_i.
//The steps are computed by RosenbrockSolver (steppers/rosenbrock.c). For ASYNCH the four vectors stored for the
//dense output of each step are (y1 - y) / h, K1 / h, K2 / h and K3 / h, with the b(theta) of Rodas5P_b.
void Rodas5P_dense(RKMethod* method)
{
    method->num_stages = 4;             //vectors stored for the dense output (the method itself has 8 stages)
    method->unique_c = 4;
    method->exp_imp = 2;                //linearly implicit: RosenbrockSolver
    method->b = malloc(method->num_stages * sizeof(double));
    method->b_theta = malloc(method->num_stages * sizeof(double));
    method->b_theta_deriv = malloc(method->num_stages * sizeof(double));
    method->dense_b = &Rodas5P_b;
    method->dense_bderiv = &Rodas5P_bderiv;
    method->e_order = 5;                //the error estimate is O(h^5)
    method->e_order_ratio = 5.0 / 4.0;
    method->d_order = 5;                //no separate dense error estimate (the dense output has order 4)
    method->d_order_ratio = 5.0 / 4.0;
    method->localorder = 5;
    method->dense_b(1.0, method->b);
    method->dense_b(1.0, method->b_theta);
    method->e = NULL;
    method->d = NULL;
    method->w = NULL;

    //The tables are static: method keeps pointers to them after this function returns.
    static const double A[8][8] = {
        { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { 2.849394379747939, 0.45842242204463923, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { -6.954028509809101, 2.489845061869568, -10.358996098473584, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { 2.8029986275628964, 0.5072464736228206, -0.3988312541770524, -0.04721187230404641, 0.0, 0.0, 0.0, 0.0 },
        { -7.502846399306121, 2.561846144803919, -11.627539656261098, -0.18268767659942256, 0.030198172008377946, 0.0, 0.0, 0.0 },
        { -7.502846399306121, 2.561846144803919, -11.627539656261098, -0.18268767659942256, 0.030198172008377946, 1.0, 0.0, 0.0 },
        { -7.502846399306121, 2.561846144803919, -11.627539656261098, -0.18268767659942256, 0.030198172008377946, 1.0, 1.0, 0.0 },
    };
    static const double C[8][8] = {
        { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { -14.155112264123755, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { -17.97296035885952, -2.859693295451294, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { 147.12150275711716, -1.41221402718213, 71.68940251302358, 0.0, 0.0, 0.0, 0.0, 0.0 },
        { 165.43517024871676, -0.4592823456491126, 42.90938336958603, -5.961986721573306, 0.0, 0.0, 0.0, 0.0 },
        { 24.854864614690072, -3.0009227002832186, 47.4931110020768, 5.5814197821558125, -0.6610691825249471, 0.0, 0.0, 0.0 },
        { 30.91273214028599, -3.1208243349937974, 77.79954646070892, 34.28646028294783, -19.097331116725623, -28.087943162872662, 0.0, 0.0 },
        { 37.80277123390563, -3.2571969029072276, 112.26918849496327, 66.9347231244047, -40.06618937091002, -54.66780262877968, -9.48861652309627, 0.0 },
    };
    static const double c[8] = { 0.0, 0.6358126895828704, 0.4095798393397535, 0.9769306725060716, 0.4288403609558664, 1.0, 1.0, 1.0 };
    static const double d[8] = { 0.21193756319429014, -0.42387512638858027, -0.3384627126235924, 1.8046452872882734, 2.325825639765069, 0.0, 0.0, 0.0 };
    static const double H[3][8] = {
        { 25.948786856663858, -2.5579724845846235, 10.433815404888879, -2.3679251022685204, 0.524948541321073, 1.1241088310450404, 0.4272876194431874, -0.17202221070155493 },
        { -9.91568850695171, -0.9689944594115154, 3.0438037242978453, -24.495224566215796, 20.176138334709044, 15.98066361424651, -6.789040303419874, -6.710236069923372 },
        { 11.419903575922262, 2.8879645146136994, 72.92137995996029, 80.12511834622643, -52.072871366152654, -59.78993625266729, -0.15582684282751913, 4.883087185713722 },
    };
    static const double b[8] = { -7.502846399306121, 2.561846144803919, -11.627539656261098, -0.18268767659942256, 0.030198172008377946, 1.0, 1.0, 1.0 };
    static const double btilde[8] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0 };

    method->ros_stages = 8;
    method->ros_gamma = 0.21193756319429014;
    method->A = A[0];
    method->ros_C = C[0];
    method->c = c;
    method->ros_d = d;
    method->ros_H = H[0];
    method->ros_b = b;
    method->ros_btilde = btilde;
}

//The b(theta) coefficients of the dense output, for the stored vectors (y1 - y)/h, K1/h, K2/h, K3/h
void Rodas5P_b(double theta, double *b)
{
    double t1 = theta * (1.0 - theta);
    b[0] = theta;
    b[1] = t1;
    b[2] = t1 * theta;
    b[3] = t1 * theta * theta;
}

//Derivatives of the b(theta) coefficients
void Rodas5P_bderiv(double theta, double *b)
{
    b[0] = 1.0;
    b[1] = 1.0 - 2.0 * theta;
    b[2] = theta * (2.0 - 3.0 * theta);
    b[3] = theta * theta * (3.0 - 4.0 * theta);
}
