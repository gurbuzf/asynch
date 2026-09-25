# Roadmap

Issue ids (B-xx, R-xx, S-xx, …) refer to `docs/guide/05_known_issues.md`.

## Phases

| Phase | Goal | Status |
|---|---|---|
| **1. Understand** | build, run all examples, review the code, regression harness, learner guide | **done** (2026-09-25) |
| **2. Fix** | fix confirmed bugs one per commit, each verified with the harness; working CI; remove dead code | next |
| **3. Python API** | new, small, stable C API + Python binding (the old one is unrepairable, A-01) | |
| **4. Performance & structure** | profile on a large network (P-*), one descriptor per model (M-02) | |
| **5. Science** | discuss S-* items, model improvements, new features | |

Suggested order inside Phase 2: B-01 → B-03 → B-04 → B-12 → B-02 → B-05/B-07/B-08 →
regenerate references (R-02/R-03, after decision 1) → CI → dead code (M-01, after decision 4).

## Working rules

1. **One logical change per commit**, with a `CHANGELOG.md` entry that says *what*, *why*, and
   *whether results change*.
2. **Run `tests/regression/run_examples.py` before and after** (np = 1, 2, 4; release and ASan
   builds). If results move beyond the tolerance, the change is scientific: it is explained, and
   benchmarks are regenerated only deliberately, in the same commit.
3. **Never mix a refactoring with a behaviour change.** A refactoring must leave results *bit-identical*.
4. Document as you go in `docs/guide/`, but keep plans and status here, not in official files.
   Keep the user documentation (how to build, run, read outputs) current with every change.
5. **Develop only on branch `modernization` of `gurbuzf/asynch`.** Never merge it into `master`,
   never open pull requests (owner's instruction, 2026-09-25). `master` stays identical to upstream.
6. **After every code change: run all examples and compare with the example results of the original
   repository** (`examples/results/`, `examples/more/*/results_benchmark/`, never modified), with
   `tests/regression/run_examples.py`. Additionally compare with the original code (commit `84da43a`)
   using `--compare-to`: bit-identical with np=1. Report both in the CHANGELOG entry.

## Decisions

The owner asked (2026-09-25) to proceed with the recommended option for each:

1. **R-02 / R-03** → ~~regenerate the references~~. **Superseded by the owner's clarification
   (2026-09-25): "compare with the original" means compare model results with the example results
   of the original, untouched repository.** Reference files are never modified or regenerated.
   R-02 was instead explained by reconstructing the 2015 configurations (`examples/*_2015.gbl`).
   R-03 stays a known mismatch.
2. **B-03** → both debug and release builds must run cleanly. Adopted.
3. **S-02 / S-06** → keep the model unchanged; behaviour is documented. Adopted.
   **Reopened for S-02 (2026-09-25):** the floor `max(0.001, q_b)` is not original. It was added in
   2021 (`93241a3`), and without it the original clearcreek references are reproduced. Asked the owner
   whether to restore the 2015 form. The code stays unchanged until they answer.
   **Owner chose A (restore the 2015 form), 2026-09-25. Done.**
4. **M-01** → move dead source files to `attic/` (history kept, nothing compiled). Adopted.

### Original wording

1. **R-02 / R-03:** may the `clearcreek` and `model_259` reference results be regenerated
   (after B-01 is fixed) from the current code and repository inputs? The alternative is to
   try to recover the original inputs.
2. **B-03:** keep "production build = `-DNDEBUG`" or make both builds clean? (Recommended: both.)
3. **S-02 / S-06 (model 254 water balance):** keep the current behaviour, documenting it, or change
   the model? Any change here alters operational results and needs a scientific justification.
4. **M-01:** delete the dead source files or move them to an `attic/` folder?
