# 5. Model 254 ("Top Layer" hillslope-link model), equation by equation

<div class="meta-row"><span class="audience">Modellers</span><span>Equations with units</span><span>25 minutes</span></div>

Model 254 is the model used operationally by the Iowa Flood Center and in
`examples/clearcreek.gbl`. This page maps **every equation to the line of C that
implements it**, with units, so that you can check the code against the science
yourself. The official description is in `docs/builtin_models.rst` (section *Top Layer
Hydrological Model*). Where that description and the code disagree, it is noted here
(and listed in [08_known_issues.md](08_known_issues.md), items D-xx).

## 5.1 The conceptual picture

Each link = one channel reach + the hillslope (two sides) that drains into it.

![Model 254: three storages on the hillslope (ponded water, top soil, subsurface) draining into a channel reservoir](diagrams/model254.svg)

The infiltration rate `k_t` depends on how wet the top layer is. When the top soil is
dry, more water infiltrates; when it is full (`s_t → S_L`), infiltration drops to `A·k2`.
That is how the model produces a runoff coefficient that varies in time.

## 5.2 States (`dim = 7`)

| index | symbol | meaning | unit |
|---|---|---|---|
| 0 | q | channel discharge | m³/s |
| 1 | s_p | water ponded on the hillslope surface | m |
| 2 | s_t | water in the top soil layer | m |
| 3 | s_s | water in the subsurface | m |
| 4 | s_precip | accumulated precipitation since t0 (diagnostic) | m |
| 5 | V_r | accumulated overland runoff q_pc since t0 (diagnostic) | m (*the rst says m³/s: D-03*) |
| 6 | q_b | baseflow part of the discharge | m³/s |

Time `t` is in **minutes** everywhere inside ASYNCH.

## 5.3 Parameters

**Global** (same for all links, line `%Global parameters` in the `.gbl`), read in
`model254()` from `global_params[]`:

| idx | name | clearcreek value | meaning |
|---|---|---|---|
| 0 | v_0 (v_r) | 0.33 | channel reference velocity [m/s] |
| 1 | λ₁ | 0.20 | exponent of discharge in channel velocity |
| 2 | λ₂ | −0.1 | exponent of upstream area in channel velocity |
| 3 | v_h | 0.02 | hillslope overland velocity [m/s] |
| 4 | k_3 | 2.0425e-6 | subsurface → channel rate [1/min] |
| 5 | k_I_factor (β) | 0.02 | k_i = β·k_2 |
| 6 | h_b | 0.5 | total hillslope soil depth [m] |
| 7 | S_L | 0.10 | top layer depth [m] |
| 8 | A | 0.0 | infiltration coefficient, saturated part |
| 9 | B | 99.0 | infiltration coefficient, dry part |
| 10 | α (exponent) | 3.0 | infiltration nonlinearity |
| 11 | v_B | 0.75 | baseflow velocity [m/s] |

**Local** (per link, `params[]`). The first 3 come from the `.prm` file, the rest are
computed in `Precalculations` (`src/models/definitions.c` ~line 3036):

| idx | name | source | unit in the code |
|---|---|---|---|
| 0 | A_i | `.prm`, upstream area | km² (kept in km²) |
| 1 | L_i | `.prm`, channel length | km → **m** in `ConvertParams` (×1000) |
| 2 | A_h | `.prm`, hillslope area | km² → **m²** in `ConvertParams` (×10⁶) |
| 3 | invtau | $\dfrac{60\, v_0\, A_i^{\lambda_2}}{(1-\lambda_1)\, L_i}$ | 1/min |
| 4 | k_2 | $60\, v_h\, L_i / A_h$ | 1/min |
| 5 | k_i | $k_2\, \beta$ | 1/min |
| 6 | c_1 | $0.001/60$ | converts rain mm/h → m/min |
| 7 | c_2 | $A_h/60$ | converts m/min over A_h → m³/s |

## 5.4 The equations, line by line (`src/models/equations.c`, `model254`, lines 1609-1687)

**Evaporation** (lines 1621, 1641-1654). Potential evaporation is shared between the three storages in
proportion to their relative fullness:

$$
e_\text{pot} = \text{forcing}[1]\cdot\frac{10^{-3}}{30\cdot 24\cdot 60}
\qquad \text{mm/month} \rightarrow \text{m/min}\ \ \text{(30-day month: S-03)}
$$

$$
\text{Corr} = \frac{s_p}{s_r} + \frac{s_t}{S_L} + \frac{s_s}{h_b - S_L} \qquad (s_r = 1\ \text{m})
$$

$$
e_p = \frac{s_p/s_r}{\text{Corr}}\,e_\text{pot}, \qquad
e_t = \frac{s_t/S_L}{\text{Corr}}\,e_\text{pot}, \qquad
e_s = \frac{s_s/(h_b - S_L)}{\text{Corr}}\,e_\text{pot}
$$

All three are 0 if $e_\text{pot} = 0$ or $\text{Corr} \le 10^{-12}$.

Note that $e_p + e_t + e_s = e_\text{pot}$ whenever there is *any* water. Evaporation always runs
at the full potential rate, however little water is stored (see S-06).

**Infiltration rate** (lines 1656-1657):

$$
k_t = k_2 \left(A + B\left(1 - \frac{s_t}{S_L}\right)^{\alpha}\right) \qquad \text{(the bracket is set to 0 if } s_t > S_L\text{)}
$$

**Fluxes** [m/min] (lines 1660-1663):

| Flux | Formula | From → to | Name in the code |
|---|---|---|---|
| $q_{pc}$ | $k_2\, s_p$ | ponded → channel | `q_pl` |
| $q_{pt}$ | $k_t\, s_p$ | ponded → top soil | `q_pt` |
| $q_{ts}$ | $k_i\, s_t$ | top soil → subsurface | `q_ts` |
| $q_{sc}$ | $k_3\, s_s$ | subsurface → channel | `q_sl` |

**Channel** (lines 1666-1669), a nonlinear reservoir:

$$
\frac{dq}{dt} = \text{invtau}\cdot q^{\lambda_1}\left(-q + c_2\,(q_{pc} + q_{sc}) + \sum_\text{parents} q_\text{parent}\right)
$$

$c_2\,(q_{pc}+q_{sc})$ converts the hillslope flux [m/min] over the hillslope area [m²] into
m³/s. The parents' discharges are read from `y_p[i*dim]` (the parent's state 0), see S-01.

**Hillslope storages** (lines 1672-1674):

$$
\begin{aligned}
\frac{ds_p}{dt} &= c_1\,p(t) - q_{pc} - q_{pt} - e_p \\
\frac{ds_t}{dt} &= q_{pt} - q_{ts} - e_t \\
\frac{ds_s}{dt} &= q_{ts} - q_{sc} - e_s
\end{aligned}
$$

**Diagnostics** (lines 1678-1679): $\dfrac{ds_\text{precip}}{dt} = c_1\,p(t)$ and $\dfrac{dV_r}{dt} = q_{pc}$.

**Baseflow** (lines 1638, 1682-1686), a linear reservoir in the channel fed only by the subsurface:

$$
\begin{aligned}
\frac{dq_b}{dt} &= \frac{v_B}{L}\left(A_h\,q_{sc} - 60\,q_b + 60\sum_\text{parents} q_{b,\text{parent}}\right) \\
&= \frac{60\,v_B}{L}\left(\frac{A_h\,q_{sc}}{60} + \sum_\text{parents} q_{b,\text{parent}} - q_b\right)
\end{aligned}
$$

The second form shows it is a linear reservoir with rate $60\,v_B/L$ [1/min] (v_B in m/s,
L in m).

:::{admonition} Restored in 2026
:class: important
From 2021 to 2026 the code used `max(0.001, q_b)` instead of `q_b` in the outflow term. That was not part of the
original model, and it has been removed (issues S-02, R-02), so the equation above is again the one that produced the
reference results shipped with ASYNCH.
:::
 The `.rst` documentation omits the factor 60 in front of the parents' baseflow (D-02).

## 5.5 Initial state (`ReadInitData`, `definitions.c` ~line 3573)

The `.uini`/`.ini` file provides q, s_p, s_t, s_s. The code then sets
`s_precip = 0`, `V_r = 0`, `q_b = q` (initially all flow is assumed to be baseflow).

## 5.6 Constraints

`check_consistency = CheckConsistency_Nonzero_AllStates_q` (`src/models/check_consistency.c`)
is applied after each stage and step. It clamps q to a small positive value and the storages
to ≥ 0. Every time it clamps, it silently adds water: this is how the model stays
physical when evaporation over-draws a nearly empty storage (see S-06).

## 5.7 Documentation discrepancies found while writing this page

These concern the original reference page; the code is right in all three cases.

* **D-01** `docs/builtin_models.rst`: 1/τ has `L · 10⁻³` in the denominator with L in km. It should
  be `L · 10³` (km → m). The code is correct (L is converted to metres in `ConvertParams`).
* **D-02** `docs/builtin_models.rst`: the baseflow equation writes `+ q_b,in(t)`. The code uses
  `+ 60·q_b,in`, which is the dimensionally consistent form.
* **D-03** `docs/builtin_models.rst`: V_r is described as a flux in m³/s. It is an accumulated
  depth in m (the integral of q_pc [m/min]).
