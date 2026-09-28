# Design note: new input and output formats

*Status: proposal for discussion, nothing implemented. Written 2026-09-28 at the owner's request.*

The model sizes in this note (number of states, parameters, forcings, initial values) were **extracted from the
library itself** (`SetParamSizes` and `InitRoutines`, run for every model number), not copied from the documentation.
The names and units come from the model code (`src/models/definitions.c`, `equations.c`) and `docs/builtin_models.rst`.
Where the code does not say what a value means or which unit it has, the note says **"to confirm"**.

Contents:

1. [Goals](#1-goals)
2. [The files at a glance](#2-the-files-at-a-glance)
3. [The run file (`run.yaml`)](#3-the-run-file-runyaml)
4. [The link table](#4-the-link-table)
5. [Forcings](#5-forcings)
6. [Dams and reservoirs](#6-dams-and-reservoirs)
7. [Outputs](#7-outputs)
8. [Vocabulary: names and units](#8-vocabulary-names-and-units)
9. [Catalogue of models](#9-catalogue-of-models)
10. [Checks and error messages](#10-checks-and-error-messages)
11. [Compatibility and migration](#11-compatibility-and-migration)
12. [Implementation plan](#12-implementation-plan)
13. [Decisions for the owner](#13-decisions-for-the-owner)
14. [Issues found while compiling this note](#14-issues-found-while-compiling-this-note)

---

## 1. Goals

1. **Names, not positions.** Every value in every file is found by its name (`channel_velocity`), never by its
   place ("the 4th number on line 12").
2. **One place per piece of information.** Everything about a link (connection, parameters, initial state, whether it
   is saved, dam, reservoir) is one row of one table.
3. **Units written in the files** and checked on reading.
4. **Standard formats** that other tools open: YAML (settings), CSV / Parquet / GeoPackage (tables), NetCDF
   (time series and results).
5. **Clear errors** before the run starts: "`solver.method`: unknown value `rodas`; use `dormand-prince` or
   `rodas5p`".
6. **Nothing breaks.** The old files keep working; a converter produces the new files from the old ones; a run gives
   bit-identical results from either.
7. **Any parameter can be global or per link.** A value in `run.yaml` applies to every link; a column of the same
   name in the link table overrides it for each link. Today this needs separate models (654 is 254 with per-link
   parameters, 404 is 400 with per-link parameters, 263 is 256/264 with per-link parameters).

## 2. The files at a glance

| Today | Content | Proposed | Format |
|---|---|---|---|
| `.gbl` | all run settings, by position | **`run.yaml`** | YAML |
| `.rvr` | network: each link and its parents | column `downstream_id` of the **link table** | CSV / Parquet / GeoPackage |
| `.prm` | link parameters, by position | named columns of the **link table** | idem |
| `.ini`, `.uini` | initial states | columns `init_<state>` of the link table, or `initial_state:` in `run.yaml` | idem / YAML |
| `.rec`, `.h5` snapshot | state of every link at one time (restart) | **restart file** | NetCDF |
| `.str`, `.ustr`, binary, `.gz`, grid cells | rain and other time series | **forcing files** | NetCDF (or CSV for one series) |
| `.mon` | 12 monthly values | 12 values in `run.yaml`, or a CSV | YAML / CSV |
| `.sav` | links to write | column `save` of the link table, or a list in `run.yaml` | |
| `.rkd` | solver and tolerances per link | optional columns of the link table | |
| `.dam` | dam parameters per link | columns of the link table (or a dam table) | CSV |
| `.qvs` | storage–discharge table per dam | **dam curve table** | CSV |
| `.rsv` | links whose discharge is read from a forcing | column `reservoir` of the link table | |
| `.dbc` | database connection and queries | unchanged, referenced from `run.yaml` | |
| `.dat`, `.csv`, `.h5` hydrographs | results | **results file** | NetCDF |
| `.pea` | peak flows | **peaks table** | CSV |

A basin then needs three to four files instead of eight to twelve:

```text
my_basin/
  run.yaml         settings of the run
  links.csv        one row per link: network, parameters, initial state, what to save
  rain_2017.nc     rain (and other forcings)
  results/         written by ASYNCH: results.nc, peaks.csv, restart.nc
```

## 3. The run file (`run.yaml`)

### 3.1 Complete example, model 254

```yaml
asynch: 1                       # version of this file format
model: 254                      # or its name: top-layer

time:
  start: 2017-01-01 00:00       # UTC unless a time zone is given (2017-01-01T00:00-06:00)
  end:   2017-02-01 00:00

network: links.csv              # the link table (section 4)

parameters:                     # global parameters of the model, by name (section 9)
  channel_velocity: 0.33        # v_r [m/s]
  exponent_discharge: 0.20      # lambda_1 []
  exponent_area: -0.1           # lambda_2 []
  hillslope_velocity: 0.02      # v_h [m/s]
  k_3: 2.0425e-6                # subsurface to channel [1/min]
  infiltration_factor: 0.02     # k_I factor (beta) []
  hillslope_depth: 0.5          # h_b [m]
  topsoil_depth: 0.1            # S_L [m]
  infiltration_a: 0.0           # A []
  infiltration_b: 99.0          # B []
  infiltration_exponent: 3.0    # alpha []
  baseflow_velocity: 0.75       # v_B [m/s]

initial_state:                  # optional: values for every link; columns init_* of the link table override
  discharge: 0.01               # [m3/s]
  ponded: 0.0                   # [m]
  topsoil: 0.05
  subsurface: 0.1

forcings:
  rain:        {file: rain_2017.nc, variable: precipitation}      # units read from the file
  evaporation: {monthly: [0, 0, 20, 60, 110, 140, 150, 130, 90, 50, 10, 0], units: mm/month}
  reservoir:   {file: releases.nc, variable: discharge}            # only if links have reservoir = yes

output:
  folder: results
  hydrographs:
    file: results.nc
    every: 15 min
    variables: [discharge, baseflow]
    links: save                 # the links with save = yes; or all; or a list [1234, 5678]
  peaks:    {file: peaks.csv, links: all, time: simulation}   # time: simulation | unix  (Classic | Forecast)
  restart:  {file: restart.nc, at: end}                       # or every: 60 min

solver:
  method: rodas5p               # dormand-prince | rodas5p | rk3 | rk4
  tolerance:
    absolute: 1e-6              # one value for every state, or per state name
    relative: 1e-6
    dense_absolute: 1e-6
    dense_relative: 1e-6
```

A model 190 run is the same file with `model: 190`, its six parameters, two forcings and three states.

### 3.2 Every setting, with its `.gbl` equivalent

Required settings are marked **R**; the others have the default shown.

| Setting | Type | Default | `.gbl` today | Notes |
|---|---|---|---|---|
| `asynch` | int | 1 | – | format version, so that later changes can be detected |
| `model` **R** | int or name | – | line 1 | names from section 9 (`top-layer` = 254) |
| `time.start`, `time.end` **R** | date-time | – | begin, end | UTC by default; ISO 8601 with a zone accepted; unix time accepted |
| `network` **R** | path or `{database: file.dbc}` | – | topology `0 f.rvr` / `1 f.dbc` | the link table, section 4 |
| `link_parameters` | path or `{database: …}` | same file as `network` | `0 f.prm` / `1 f.dbc` | only when parameters are in a separate table |
| `parameters.<name>` | number | model default, else **R** | global parameters line | section 9 lists names per model; unknown names are errors |
| `initial_state.<state>` | number | model default | `1 f.uini` | same value for every link |
| `initial_state.file` | path | – | `0 .ini`, `2 .rec`, `4 .h5` | a restart file (NetCDF, or the old `.rec`/`.h5`) |
| `initial_state.database` | `{file: f.dbc, time: …}` | – | `3 f.dbc t` | |
| `forcings.<name>` **R** for each forcing of the model | block | – | forcing blocks, in model order | by name (section 5), order no longer matters |
| `dams` | path, or `columns` | none | `0` / `1 .dam` / `2 .qvs` / `3 .dbc` | section 6 |
| `reservoirs` | `column`, list of ids, or path | none | `0` / `1 .rsv` / `2 .dbc` + forcing index | section 6; the feeding forcing is always `forcings.reservoir` |
| `output.folder` | path | `.` | – | created if missing (asked of the owner) |
| `output.hydrographs.file` | path, or `{database: f.dbc, table: t}` | none | hydrograph flag and file | format from the extension: `.nc` (new), `.csv`, `.dat`, `.h5` (old) |
| `output.hydrographs.every` | duration | – (**R** if file) | interval [min] | `15 min`, `1 h`, `1 day` |
| `output.hydrographs.variables` | list of names | `[discharge]` | "components to print" | state names, and `time`, `unix_time`, `link_id` for the old text formats |
| `output.hydrographs.links` | `save`, `all`, list, path | `save` | `.sav` flag | |
| `output.peaks.file` | path, or `{database: …}` | none | peakflow flag and file | |
| `output.peaks.links` | as above | `all` | second `.sav` flag | |
| `output.peaks.time` | `simulation` or `unix` | `simulation` | `Classic` / `Forecast` | |
| `output.restart.file` | path, or `{database: …}` | none | snapshot flag | |
| `output.restart.at` / `every` | `end` / duration | `end` | snapshot flag 3 / 4 | |
| `output.parameters_in_names` | bool | false | "parameters to filenames" | |
| `solver.method` | name | `dormand-prince` | solver index 2 | `rk3` = 0, `rk4` = 1, `rodas5p` = 4 |
| `solver.tolerance.*` | number, or `{state: number}` | model defaults (to be defined, see 13) | the four tolerance lines | |
| `solver.step_control` | `{min_factor, max_factor, safety}` | `{0.1, 10.0, 0.9}` | `facmin facmax fac` | |
| `advanced.steps_stored` | int | 30 | buffers line | |
| `advanced.steps_transferred` | int | 10 | idem | |
| `advanced.discontinuity_buffer` | int | 30 | idem | |
| `advanced.scratch` | path | `tmp` | scratch file name | |

Per-link solver settings (today's `.rkd`) are optional columns of the link table: `solver`, `tol_abs_<state>`,
`tol_rel_<state>`, ... (section 4.4).

### 3.3 Why YAML

- Named settings, nesting, comments, lists; readable without a manual.
- Common in science and in the neighbouring projects (Tiger-HLM uses YAML).
- JSON has no comments and a missing comma breaks it, so it is poor for people; it stays possible for programs
  (every YAML reader reads JSON).
- TOML is a good alternative; it is clumsier for nested lists (forcings, outputs).
- The weak point of YAML (indentation, `no` read as false) is covered by the checks of section 10: a schema lists
  every key, its type and its unit.

## 4. The link table

### 4.1 Columns common to every model

| Column | Unit | Required | Today |
|---|---|---|---|
| `link_id` | – | yes | id in `.rvr` / `.prm` |
| `downstream_id` | – | yes (empty or 0 at an outlet) | derived from the parent lists of `.rvr` |
| `upstream_area` | km² | yes (all models except 101) | `A_i` (`A_up`) |
| `channel_length` | km | yes (idem) | `L_i` |
| `hillslope_area` | km² | yes (idem) | `A_h` |
| `save` | yes/no | no (default no) | `.sav` |
| `reservoir` | yes/no | no | `.rsv` |
| `init_<state>` | unit of the state | no | `.ini` |

Other columns: the per-link parameters of the model (section 9), any global parameter to override it at this link,
dam columns (section 6), solver columns (4.4). Unknown columns are allowed (for instance a gauge name or a
geometry) and ignored, with a note in the log.

Example, model 254:

```text
link_id,downstream_id,upstream_area,channel_length,hillslope_area,save,init_discharge
1234,1240,0.8,0.35,0.8,no,0.01
1240,0,57.2,0.51,0.3,yes,0.8
```

### 4.2 Network: downstream link instead of parent lists

Today's `.rvr` lists, for every link, its parents. The table gives each link **its downstream link**, as NHDPlus,
HydroSHEDS and most river datasets do (`NextDownID`). It is shorter, it is what GIS tools export, and it cannot be
inconsistent (a link cannot have two downstream links). ASYNCH builds the parent lists from it. Checks: every
`downstream_id` exists, no cycles, at least one outlet.

### 4.3 File format by size

| Network | Format | Why |
|---|---|---|
| up to about 1 million links | **CSV** | opens in Excel, QGIS, pandas, R; readable |
| millions of links | **Parquet** | 5–10 times smaller, read much faster, typed columns |
| with shapes of links and hillslopes | **GeoPackage** (one layer of links) | the network can be drawn on a map directly |

The extension tells the format. The C program reads CSV directly; Parquet and GeoPackage are read through the Python
package (or a later C reader).

### 4.4 Optional columns

| Column | Meaning | Today |
|---|---|---|
| `solver` | method for this link (`rodas5p`, ...) | last value of a `.rkd` line |
| `tol_abs_<state>`, `tol_rel_<state>`, `tol_dense_abs_<state>`, `tol_dense_rel_<state>` | tolerances for this link | `.rkd` |
| any global parameter name | its value at this link | separate models today (654, 404, 263) |
| dam columns | section 6 | `.dam` |

## 5. Forcings

### 5.1 Names

Forcings are given **by name**, so the order of the model does not matter any more. Section 9 lists which names each
model needs.

| Name | Unit expected | Meaning | Models |
|---|---|---|---|
| `rain` | mm/h | precipitation | most models |
| `evaporation` | mm/month | potential evapotranspiration | 190–192, 195, 196, 225, 249, 251–264, 400–405, 601–609, 654 (19, 60 and 250 take a constant e_pot as a global parameter instead) |
| `reservoir` | m³/s | discharge imposed at links with `reservoir = yes` | 191, 192, 196, 249, 251, 253–259, 261–264, 400–405, 608, 609 |
| `snowmelt` | mm/h | water released by snow | 251, 253, 255, 264, 608, 609 |
| `temperature` | °C | air temperature | 400–405 |
| `frozen_ground` | 1 or 0 | ground frozen | 400–405 |
| `surface_runoff` | mm/h | runoff computed by another model (offline) | 193, 194 (`runoff`), 195, 196, 258, 259 |
| `infiltration` | mm/h | infiltration computed by another model | 195, 196, 258, 259 |
| `topsoil_depth` | m | time-varying S_L | 251 |
| `eta` | – | time-varying soil parameter | 261 |
| `hillslope_flux` | to confirm | flux from the hillslope | 219 |

### 5.2 Sources

```yaml
forcings:
  rain: {file: rain.nc, variable: precipitation}           # NetCDF, one value per link and time
  rain: {file: radar.nc, variable: rr, cells: cells.csv}   # NetCDF grid + table link -> cell (today: flag 8)
  rain: {series: gauge.csv}                                # one series for every link (today: .ustr)
  evaporation: {monthly: [12 values], units: mm/month}     # today: .mon
  rain: {database: rain.dbc, every: 5 min}                 # today: flags 3 and 9
  rain: {legacy: {type: binary, path: bin/rain, every: 5 min, first: 1398902400, last: 1401580800}}
                                                           # today: flags 2, 5, 6, kept as they are
  rain: {file: rain.str}                                   # the old per-link file, still read
```

NetCDF layout (CF conventions), per link:

```text
dimensions:  time, link
variables:   time(time)  "minutes since 2017-01-01 00:00:00"   (any CF time unit accepted)
             link(link)  link ids
             precipitation(time, link)  units = "mm/h"
```

A value holds from its time to the next one (step function, as ASYNCH does today). Units are read from the file and
converted from a fixed list (mm/h, mm/s, m/s, kg m-2 s-1, mm/day for rain; mm/month, mm/day for evaporation; m3/s,
ft3/s for discharge; degC, K for temperature). An unknown unit stops the run with a message.

## 6. Dams and reservoirs

**Reservoirs** (discharge imposed from a time series): column `reservoir = yes` in the link table, and the forcing
`reservoir` gives the discharge of those links (NetCDF with a `link` dimension, or CSV with columns `time, link_id,
discharge`). Today the `.gbl` also names which forcing index feeds them; with names this is always
`forcings.reservoir`.

**Dams with parameters** (models 21, 22, 23; today `.dam`): columns of the link table, empty for links without a dam.

| Column | Unit | Symbol |
|---|---|---|
| `dam` | yes/no | – |
| `dam_orifice_area` | m² | orifice_area |
| `dam_spillway_height` | m | H_spill |
| `dam_height` | m | H_max |
| `dam_max_storage` | m³ | S_max |
| `dam_alpha` | – | alpha (exponent for bankfull) |
| `dam_orifice_diameter` | m | d |
| `dam_c1`, `dam_c2` | – | c_1, c_2 (discharge coefficients) |
| `dam_spillway_length` | m | L_spill |

**Dams with a storage–discharge curve** (models 40, 255, 261, 262, and 402, 403, 405; today `.qvs`): a curve table.

```text
link_id,storage_m3,discharge_m3s
7001,0,0
7001,150000,2.5
7001,400000,40
```

## 7. Outputs

### 7.1 Results (hydrographs): NetCDF

```text
dimensions:  time, link
variables:   time(time)       "minutes since <start>"      + attribute with the start date
             link(link)       link ids
             discharge(time, link)   units = "m3/s", long_name = "channel discharge"
             baseflow(time, link)    units = "m3/s"
global attributes: model = 254, asynch_version, run file (copied in full), creation date, solver and tolerances
```

- `xarray.open_dataset("results.nc")` gives ready-to-plot hydrographs; QGIS, Panoply and R read it.
- It is HDF5 underneath (NetCDF-4), which ASYNCH already depends on.
- The whole `run.yaml` is stored in the file, so every result says how it was made.
- The variables are chosen by state name. Today only `State0`–`State7` exist, so states 8 and 9 (model 256
  `q_openloop`, model 401 cumulative groundwater and snow) cannot be written at all (section 14).
- Writing in parallel: each process writes its links to temporary files as today; process 0 assembles the NetCDF
  (no need for parallel NetCDF).

The old formats remain available by file extension (`.csv`, `.dat`, `.h5`).

### 7.2 Peaks: CSV

```text
link_id,peak_discharge_m3s,time_of_peak,upstream_area_km2
```

`time_of_peak` is minutes since the start (`time: simulation`, today *Classic*) or a date-time (`time: unix`, today
*Forecast*, written as ISO date instead of a unix number).

### 7.3 Restart: NetCDF

One variable per state, dimension `link`, attribute `time`. The same file is accepted by `initial_state.file`. It
replaces `.rec` and the `.h5` snapshots (both still read).

## 8. Vocabulary: names and units

One name per quantity, used in `run.yaml`, in link table columns and in the results. The paper symbol is accepted as
an alias (so `v_r` and `channel_velocity` both work); error messages give both, with the unit.

### 8.1 Geometry (link table)

| Name | Symbol | Unit |
|---|---|---|
| `upstream_area` | A_i, A_up | km² |
| `channel_length` | L_i, L | km |
| `hillslope_area` | A_h | km² |
| `hillslope_length` | L_h | km (model 30) |
| `stream_order` | horder | – (model 257, 1–10) |
| `slope` | slope | m/m (to confirm; 225, 601–603) |

### 8.2 Channel

| Name | Symbol | Unit |
|---|---|---|
| `channel_velocity` | v_r, v_0 | m/s |
| `exponent_discharge` | lambda_1 | – |
| `exponent_area` | lambda_2 | – |
| `reference_discharge` | Q_r | m³/s |
| `reference_area` | A_r | km² |
| `baseflow_velocity` | v_B | m/s |

### 8.3 Hillslope, IFC models

| Name | Symbol | Unit |
|---|---|---|
| `runoff_coefficient` | RC | – |
| `hillslope_velocity` | v_h | m/s |
| `subsurface_velocity` | v_g | m/s |
| `k_3` | k_3 | 1/min (subsurface to channel) |
| `infiltration_factor` | k_I factor, beta | – |
| `hillslope_depth` | h_b | m |
| `topsoil_depth` | S_L | m |
| `infiltration_a`, `infiltration_b`, `infiltration_exponent` | A, B, alpha | – |
| `interflow_coefficient` | k_tl (k_tc) | 1/min |
| `evaporation_constant` | e_pot | model 19: to confirm (used as a constant); 250: m/min |
| `gamma` | gamma | – (model 250) |
| `h_r` | h_r | m (model 250, per link) |
| `initial_depth` | S_0 | m (models 21–23, 40) |
| `n_sat`, `phi` | N, phi | – (261, 262) |
| `s_h`, `t_l`, `k_d`, `k_dry`, `k_i` | S_h, T_L, k_D, k_dry, k_i | –, m, 1/s, 1/s, 1/s (261, 262) |

### 8.4 TETIS models (400–405)

| Name | Symbol | Unit |
|---|---|---|
| `static_storage_max` | Hu | mm |
| `infiltration_rate` | infiltration | mm/h |
| `percolation_rate` | percolation | mm/h |
| `surface_velocity` | alfa2, vsurf | m/s |
| `gravitational_residence` | alfa3 | days |
| `aquifer_residence` | alfa4 | days |
| `melt_factor` | melt_factor | mm/day/°C |
| `melt_temperature` | temp_thres | °C |
| `dam_low_threshold`, `dam_high_threshold`, `dam_operating_window` | factor_low_threshold, ... | – (0 to 1; 405) |

### 8.5 States

| Name | Symbol | Unit |
|---|---|---|
| `discharge` | q | m³/s |
| `ponded` | s_p | m |
| `topsoil` | s_t | m |
| `subsurface` | s_s (s_a in 19/190-196, s_l in 225/601-609) | m |
| `aquifer` | s_a | m |
| `precip_total` | s_precip | m |
| `evap_total` | s_evap, s_et | m |
| `runoff_total` | V_r, s_runoff | m (254) or m³ (others, per the code comments; to confirm) |
| `baseflow` | q_b | m³/s |
| `channel_storage` | S | m³ |
| `soil_storage`, `groundwater_storage` | Ss, Sg | m³ (21–23, 40) |
| `static`, `surface`, `gravitational`, `groundwater`, `snow` | h1–h5 | m (400–405) |
| `dam_storage` | dam_storage | m³ |

States of models not covered here keep a neutral name `state_<k>` until named (section 9 marks them).

## 9. Catalogue of models

For each model: its states in order (the number read as initial values, `init`, is what the program reads today;
the others are set by the model), the global parameters (in `run.yaml`, in today's order), the per-link columns
**beyond** `upstream_area`, `channel_length`, `hillslope_area`, and the forcings in today's order.

Symbols are used in the tables for brevity; section 8 gives the names. "⚠" points to section 14.

### 9.1 IFC linear hillslope models

| Model | States (init) | Global parameters | Extra link columns | Forcings |
|---|---|---|---|---|
| 19 | q, s_p, s_a (3) | v_r, λ1, λ2, RC, v_h, v_g, e_pot | – | rain |
| 20 | q, s_p, s_a (3) | v_r, λ1, λ2 + 6 values whose meaning depends on the variant compiled (toy model) ⚠ | – | rain |
| 60 | q, s_p, s_a (3) | v_r, λ1, λ2, v_h, v_g, e_pot | h_b | rain |
| 190 | q, s_p, s_s (3) | v_r, λ1, λ2, RC, v_h, v_g | – | rain, evaporation |
| 191 | q, s_p, s_s, s_precip, V_r, q_b (3) | v_r, λ1, λ2, RC, v_h, v_g, v_B | – | rain, evaporation, reservoir |
| 192 | q, s_p, s_s, s_precip, V_r, q_b (3) | v_r, λ1, λ2, k_I factor, v_h, k_3, v_B | – | rain, evaporation, reservoir |
| 193 | q (1) | – | – | surface_runoff (routed without delay) |
| 194 | q (1) | v_r, λ1, λ2 | – | surface_runoff |
| 195 | q, s_p, s_s, s_precip (3) | v_r, λ1, λ2, v_h, k_3 | – | surface_runoff, infiltration, evaporation |
| 196 | q, s_p, s_s, s_precip, s_runoff (3) | v_r, λ1, λ2, v_h, k_3 | – | surface_runoff, infiltration, evaporation, reservoir |
| 219 | q (1) | v_0, λ1, λ2 | – | hillslope_flux |
| 225 | q, s_p, s_l, s_s (4) | v_r, λ1, λ2, tL, bL, kdry, ki, k2 (units to confirm) | slope, tileQ | rain, evaporation |
| 250 | q, s_p, s_s (3) | v_0, λ1, λ2, v_h, k_3, k_I factor, gamma, h_b, e_pot | h_r | rain |

### 9.2 IFC top layer models

Standard global parameters **TL12** = v_0, λ1, λ2, v_h, k_3, k_I factor, h_b, S_L, A, B, α, v_B.

| Model | States (init) | Global parameters | Extra link columns | Forcings |
|---|---|---|---|---|
| 249 | q, s_p, s_t, s_s, s_precip, V_r (6) | TL12 | – | rain, evaporation, reservoir |
| 251 | q, s_p, s_t, s_s (4) | TL12 without v_B (11) | – | rain, evaporation, reservoir, snowmelt, topsoil_depth |
| 252 | q, s_p, s_t, s_s (4) | TL12 without v_B (11) | – | rain, evaporation |
| 253 | q, s_p, s_t, s_s (4) | TL12 without v_B (11) | – | rain, evaporation, reservoir, snowmelt |
| **254** | q, s_p, s_t, s_s, s_precip, V_r, q_b (7) | TL12 | – | rain, evaporation, reservoir |
| 255 | q (algebraic), S, s_p, s_t, s_s (5) | v_0, λ1, λ2 | v_h, k_3, k_I factor, h_b, S_L, A, B, α | rain, evaporation, reservoir, snowmelt; dam curve |
| 256 | q, s_p, s_t, s_s, q_pl, q_tl, q_sl, q_b, q_openloop (9) | TL12, k_tl | – | rain, evaporation, reservoir |
| 257 | q, s_p, s_t, s_s, s_precip, s_et, V_r, q_b (4) | v_0 for stream orders 1–10, λ1 for orders 1–10, λ2, v_h, k_3, k_I factor, h_b, S_L, A, B, α, v_B, k_tl (31) | stream_order | rain, evaporation, reservoir |
| 258 | q, s_p, s_t, s_s, s_precip, s_evap, V_r, q_b (4) | v_0, λ1, λ2, v_h, k_3, k_I, h_b, S_L, v_B | – | surface_runoff, infiltration, evaporation, reservoir |
| 259 | as 258 (4) | as 258, k_tl | – | as 258 |
| 261 | q (algebraic), S, s_p, s_t, s_s, s_precip, V_r, q_b (5) | v_0, λ1, λ2, N, phi, v_B | S_h, T_L, h_b, k_D, k_dry, k_i | rain, evaporation, eta, reservoir; dam curve |
| 262 | as 261 (5) | as 261 | as 261, eta (constant) | rain, evaporation, reservoir; dam curve |
| 263 | q, s_p, s_t, s_s, 4 more (4) | 13 declared ⚠ | v_0, λ1, λ2, v_h, k_I factor, k_3, h_b, S_L, A, B, α, v_B, k_tl ⚠ | rain, evaporation, reservoir |
| 264 | q, s_p, s_t, s_s, q_pl, q_tl, q_sl, q_b (4) | TL12, k_tl | – | rain, evaporation, reservoir, snowmelt |
| 654 | q, s_p, s_t, s_s (4) | 1 declared, not used | v_h, k_I factor, k_3, h_b, S_L, A, B, α, λ1, λ2, v_0 (TL12 per link, without v_B) | rain, evaporation |

With goal 7 (any parameter global or per link), 654 becomes "254 with per-link columns" and 263 "256/264 with
per-link columns"; they can stay as model numbers for existing setups.

### 9.3 Linear reservoir models with dams

| Model | States (init) | Global parameters | Extra link columns | Forcings |
|---|---|---|---|---|
| 21 | q (algebraic), S, Ss, Sg (2) | v_r, λ1, λ2, RC, S_0, v_h, v_g | dam columns (section 6) | rain |
| 22, 23 | q (algebraic), S, Ss, Sg (2) | λ1, λ2, S_0, v_g | RC, v_h, v_r; dam columns | rain |
| 40 | q (algebraic), S, Ss, Sg (2) | λ1, λ2, S_0, v_g | RC, v_h, v_r; dam curve | rain |

### 9.4 TETIS models

States 400, 404: q, static, surface, gravitational, groundwater, snow. 402, 403, 405: the same and dam_storage.
401: q, 4 cumulative volumes (rain, surface, subsurface, groundwater, m³/h), static, surface, gravitational,
groundwater, snow. Initial values: all states.

| Model | Global parameters | Extra link columns | Forcings |
|---|---|---|---|
| 400, 401, 402, 403 | v_0, λ1, λ2, Hu, infiltration, percolation, surface velocity, alfa3, alfa4, melt_factor, temp_thres | – | rain, evaporation, temperature, frozen_ground, reservoir ⚠ (403) |
| 404 | 1 declared, not used | v_0, λ1, λ2, Hu, infiltration, percolation, vsurf, alfa3, alfa4, melt_factor, temp_thres | as 400 |
| 405 | as 400, then dam_low_threshold, dam_high_threshold, dam_operating_window | – | as 400 ⚠ |

### 9.5 Variable-parameter and tile models (all parameters per link)

These declare 1 global parameter that the equations do not use. Units of the per-link parameters: to confirm with
the model authors.

| Model | States (init) | Link columns after the three areas/lengths | Forcings |
|---|---|---|---|
| 601 | q, s_p, s_l, s_s (4) | slope, v_r, a_r, v_s, a_s, k1, k2, t_l, b_L, λ1, λ2, v_0 | rain, evaporation |
| 602 | q, s_p, s_l, s_s (4) | slope, v_r, a_r, v_l, a_l, v_s, a_s, k1, k2, t_l, b_L, λ1, λ2, v_0 | rain, evaporation |
| 603 | q, s_p, s1, s2, s3 (5) | slope, v1, a1, v2, a2, v3, a3, v4, a4, h1, h2, h3, k1, k2, k3, λ1, λ2, v0 | rain, evaporation |
| 604 | q, s_p, s_l, s_s, 3 accumulators (7) | v_r, a_r, v_s1, v_s2, k1, k2, t_L, S_i, S_n, λ1, λ2, v0 | rain, evaporation |
| 605 | q, s_p, s_l, s_s, 3 accumulators (7) | v_r, a_r, v_s1–v_s4, k1, k2, t_L, S1–S4, λ1, λ2, v0 | rain, evaporation |
| 606 | q, s_p, s_l, s_s, tile storage, 2 accumulators (7) | v_r, a_r, a, b, m, mt, k1, k2, t_L, NoFlow, Td, Beta, λ1, λ2, v0 | rain, evaporation |
| 608 | q, s_p, s_l, s_s (4) | v_r, a_r, a, b, c, d, k3, ki_fac, t_L, NoFlow, Td, Beta, λ1, λ2, v0 | rain, evaporation, reservoir, snowmelt |
| 609 | q, s_p, s_l, s_s, q_b (5) | as 608 | as 608 |

### 9.6 Early research models

Link columns in today's order **L_i, A_h, A_i** first (the only models with length before area; names remove this
trap), then the soil parameters. Units: to confirm from the original papers.

| Model | States (init) | Global parameters | Extra link columns | Forcings |
|---|---|---|---|---|
| 0 | q (1) | v_r, λ1, λ2, Q_r, A_r, RC | h_b, h_H, max_inf_rate, K_sat, S_h, eta, b_H, c_H, d_H | – |
| 1, 2, 3 | q, s (2) | idem | idem | rain (1, 3), none used (2) |
| 4, 5 | q, s, a, v (4) | idem | idem | rain (5), none used (4) |
| 6 | q, s_p, a, v (4) | v_r, λ1, λ2, Q_r, A_r | h_b, K_sat, K_sp, d_0, d_1, d_2, invbeta, alpha_N, alpha_soil, a_res, v_res | rain |
| 15 | q, s_p (2) | v_r, λ1, λ2, v_h, A_r, RC | as 0 | rain |
| 105 | q, s (2) | 0 declared, 6 read ⚠ | as 0 | rain |
| 30 | q, s_p, h_w, theta (4) | v_0, λ1, λ2, Q_r, A_r, K_T, C_r | L_h, A_h, A_up, H_b, H_h, max_inf_rate, K_SAT, S_H, n_vh, b, c, d | rain, second forcing ⚠ |
| 101 | y1, y2, y3 (3) | – | – (Robertson test problem, no network parameters) | – |

### 9.7 Not usable today

200, 260, 300, 301, 315, 607 and 2000 have no equations; ASYNCH refuses them (B-26). They get no entry until
they are completed or removed.

## 10. Checks and error messages

All checks run **before** the computation, and all errors are listed together (not only the first one).

| Check | Example message |
|---|---|
| unknown key | `run.yaml, line 12: unknown setting "solver.metod". Did you mean "solver.method"?` |
| wrong value | `solver.method: "rodas" is not a method; use dormand-prince, rodas5p, rk3 or rk4.` |
| missing parameter | `model 254 needs parameter "baseflow_velocity" (v_B, m/s): give it in run.yaml or as a column of links.csv.` |
| parameter not used by the model | `parameter "runoff_coefficient" is not used by model 254 (ignored).` (warning) |
| missing forcing | `model 254 needs the forcing "evaporation" (mm/month).` |
| unit | `rain_2017.nc: variable "precipitation" has units "inch/h", which ASYNCH cannot convert; use mm/h.` |
| network | `links.csv, row 18: downstream_id 9999 is not a link of the table.` / `the network has a loop: 12 -> 15 -> 12.` |
| value range | `links.csv, row 4: hillslope_area is negative (-0.2 km2).` |
| forcing coverage | `rain_2017.nc ends on 2017-01-20, before time.end (2017-02-01).` (error, or warning with `allow_short_forcings`) |
| output folder | as today (B-15): checked before computing |
| solver | `solver rodas5p cannot be used with model 21 (algebraic equations).` |

## 11. Compatibility and migration

1. **Both formats, forever for the old one.** `asynch run.yaml` and `asynch my_basin.gbl` both work. Old setups
   need no change.
2. **Converter:** `asynch convert my_basin.gbl --to my_basin/` writes `run.yaml` and `links.csv` (and converts
   `.str`/`.ustr` to NetCDF when asked). The reverse (`--to-gbl`) is also provided, so a new setup can run on an old
   ASYNCH.
3. **Proof of equivalence:** for every example, the converted setup must give **bit-identical** results to the
   original (`run_examples.py` gets a mode that converts, runs and compares). This is the acceptance test of the
   whole change.
4. **Python:** `GlobalConfig` gains `read_yaml` / `write_yaml`; `asynch.io` reads and writes the link table and
   NetCDF forcings.

## 12. Implementation plan

| Step | What | Where | Result change |
|---|---|---|---|
| 1 | Model descriptions as data: for every model, names, units and defaults of its states, parameters, forcings (the catalogue of section 9, in one table in the code) | C (`models/`) | none |
| 2 | Python: read `run.yaml` + link table + NetCDF forcings, check them (section 10), hand them to the C library through the API | Python | none |
| 3 | Converter `.gbl` ↔ `run.yaml`; bit-identity test on all examples | Python + tests | none |
| 4 | NetCDF results and restart files | C (NetCDF-C, on HDF5) | none (new output format) |
| 5 | The `asynch` program reads `run.yaml` directly (libyaml, CSV reader) | C | none |
| 6 | Documentation: guide chapter 2 rewritten for the new files; old formats move to a reference page | docs | – |

Step 1 is useful on its own (it is roadmap item M-02, "one descriptor per model"): output names such as `discharge`
instead of `State0`, and checks of the global parameter count, become possible.

New dependencies: libyaml (C, small, in every Linux distribution), NetCDF-C (built on HDF5). Python: PyYAML,
xarray/netCDF4 (optional, only for NetCDF forcings from Python), pyarrow (optional, Parquet).

## 13. Decisions for the owner

1. **Names:** descriptive names (`channel_velocity`) as the main form with symbols (`v_r`) as aliases, as proposed;
   or symbols only.
2. **Default tolerances per model**, so that `solver.tolerance` can be left out (today every `.gbl` must give them).
3. **Model names** (`top-layer` for 254, ...) in addition to numbers.
4. **`output.folder` created automatically** if missing (today: error, B-15).
5. **Models to drop from the catalogue** instead of describing them (for example 20, 30, 101, the 0–6 series), if
   nobody uses them.
6. **Order of the work:** step 1 alone first (it also improves outputs and checks), or steps 1–3 together.

## 14. Issues found while compiling this note

Not fixed (this note changes no code); to be checked and entered in `docs/guide/08_known_issues.md` if confirmed.

| # | Model | Finding |
|---|---|---|
| 1 | 403, 405 | The reservoir routine `Tetis03_Reservoirs` imposes `forcing_values[3]` as the discharge. In these models forcing 3 is `frozen_ground` (0 or 1); the reservoir forcing is 4 (as in `model401reservoir`). A reservoir link would get a discharge of 0 or 1 m³/s. |
| 2 | all | Hydrograph outputs exist only for `State0`–`State7`: states 8 and 9 (model 256 `q_openloop`, model 401 cumulative groundwater and snow) cannot be written. |
| 3 | 105 | Declares 0 global parameters, but its precalculation reads 6 (v_r, λ1, λ2, Q_r, A_r, RC). Works only if the `.gbl` gives them anyway. |
| 4 | 263 | Reads v_0, λ1, λ2, ... from link parameters 3–15, but its equations also read `params[12..15]` as invtau, c_1, c_2, c_3 (the same slots as B, α, v_B, k_tl) and λ1 from the global parameters; states 4–7 have zero derivatives. The model looks unfinished. |
| 5 | 20 | Declares 9 global parameters; the comment lists 10, and their meaning depends on a variant chosen when compiling. |
| 6 | 30 | Declares 2 forcings; the equations use none (legacy CUENCAS model). |
| 7 | 404, 601–609, 654 | Declare 1 global parameter that the equations do not use (all parameters are per link). Harmless; the new format would not ask for it. |
