# Correctness audit of the foam_gnn critical path

Inspection only — **nothing was fixed**. Method: prefer known-answer tests over code
reading. Every claim below is backed by a hand-computed value, a synthetic case with a
known answer, or a measurement on real data.

Drivers: `dev/audit_modeling.py` (primitives), `dev/audit_models.py` (learned models),
plus the inline measurements recorded here.

## Verdict up front

| # | finding | severity | changes a conclusion? |
|---|---|---|---|
| **D1** | **The t+1 von Neumann failure and the loss of horizon-stability are a leverage artifact** — 1.2% of rows carry 48% of the fit weight | **HIGH** | **YES — two headline claims** |
| **D2** | `n_sides` is systematically under-counted by ~0.6–1.2 neighbours (13% of the foam interior is unlabelled) | MEDIUM-HIGH | No (K is insensitive), but invalidates claims *about n* |
| **D3** | Gate 2's "beats persistence" is an **in-sample** comparison | MEDIUM | No — out-of-sample still passes |
| **D4** | The run0/run1 K gap is a **dA/dt scale difference**, not a fit bug — but K is confounded with the coarsening rate | MEDIUM (interpretation) | YES — reframes it |
| **D5** | Trusted set is a survivorship cohort; `area_jump_tol=0.5` admits 65% single-frame area jumps | LOW–MEDIUM | Bounds scope |

**The GNN null is genuine. The von Neumann "weakening" is substantially an artifact.**

## 1. What was verified, and how

### modeling.py primitives — ALL PASS (`dev/audit_modeling.py`, 0 failures)
| component | test | result |
|---|---|---|
| `make_horizon_samples` | hand-built segment, frames 0–5 @30 s, area +10 px²/frame | dA/dt = 10/30 exactly at h=1 and 50/150 at h=5 ✓ |
| horizon alignment | frames with a **gap** (0,1,2,4,5) | partner looked up by *frame number*; 2→3 correctly skipped; h=2 across the gap uses the **real** 60 s dt ✓ |
| units | — | areas px², `time_seconds` s, target px²/s — consistent ✓ |
| `past_slope` | causal fit over frames ≤ t | NaN at first frame, 10/30 at second ✓ |
| `fit_von_neumann` | y = 0.5(n−6) exactly | K = 0.5, r²_origin = 1.0 ✓ |
| | y = 0.5(n−6) + 2.0 | `intercept_free` recovers 2.0, `slope_free` 0.5 ✓ |
| | scale equivariance | doubling dA/dt doubles K ✓ (**this matters for D4**) |
| `cluster_bootstrap_ci` | instrumented 200 draws, unequal bubble sizes | **every draw contains whole bubbles only** — resampling is at the bubble level, not the row level ✓ |
| baselines | direct | persistence = 0 rate; `global_mean` = supplied train mean; `per_bubble_linear` = past slope, 0 where undefined; `predict_von_neumann` = K(n−6) ✓ |
| `paired_delta_ci` | perfect vs zero predictor | delta = −1.0, CI < 0 ⇒ "beats" — sign convention correct ✓ |

**Hypothesis 2 (dA/dt / horizon / off-by-one) — REFUTED. No defect.**
**Hypothesis 6 (cluster bootstrap) — REFUTED. Correctly bubble-level.**

### Leakage — Gate 1 and Gate 3 are clean
`global_mean` is fit on `tr` (training sessions) in Gate 1 and on `fit_s` (train minus
validation) in Gate 3; the von Neumann K used as a *predictor* in Gate 3 is fit on
`fit_s`. No test-set information reaches any baseline. **Hypothesis 4 — REFUTED for
Gates 1/3** (but see D3 for Gate 2).

### The GNN and MLP genuinely learn (`dev/audit_models.py`, 0 failures)
Constructed two tasks with known answers on ring-lattice graphs:

| task | GNN skill | MLP skill |
|---|---|---|
| **node** task `y = 3f₀ − 2f₁` (solvable from node features) | **+98.68%** | +99.13% |
| **graph** task `y = 3·mean(neighbour f₀)` (solvable *only* through edges) | **+98.02%** | **+0.52%** |

The GNN recovers a purely topological signal to 98% skill where the MLP — with identical
node features — gets 0.5%. **The architecture, message passing, feature assembly,
normalisation and training loop all work.** Node features are also confirmed identical
between the two models (`area_t` in the sample table *is* the trusted `area` at frame t;
GNN `x` = [area, n_sides, distance_to_evap_edge], MLP = [area_t, n_sides,
distance_to_evap_edge]).

**Hypothesis 5 (model silently fails to train) — REFUTED. The GNN null is genuine:
when topology carries signal, this GNN finds it. On the foam data it does not, because
the Delaunay topology + those edge features do not predict dA/dt.**

### Adjacency mechanics — correct
Synthetic label maps: three stripes give shared borders of exactly 10 px for 1–2 and 2–3
and **no** 1–3 edge ✓; a background gap creates **no** edge ✓; diagonal-only contact
creates no edge (4-connectivity) ✓. `frozenset` keys mean no double-counting ✓.

## 2. D1 — the t+1 von Neumann failure is a LEVERAGE ARTIFACT (HIGH)

K is a through-origin least-squares slope, `K = Σxy / Σx²` with `x = n−6`. **Every row is
weighted by x².** Measured on the current trusted set:

| h=1 | rows | share of rows | **share of Σx²** | K within group |
|---|---|---|---|---|
| \|n−6\| ∈ [0,3) | 5318 | 74.8% | 14.8% | **+0.3412** |
| \|n−6\| ∈ [3,6) | 1586 | 22.3% | 30.7% | +0.2152 |
| \|n−6\| ∈ [6,10) | 116 | 1.6% | 6.3% | +0.0635 |
| **\|n−6\| ∈ [10,30)** | **86** | **1.2%** | **48.2%** | **+0.0479** |

**86 rows out of 7106 carry 48% of the fit weight, and they pull K from ~+0.34 to
+0.1435.** Restricting to the bulk (|n−6| ≤ 4) gives **K = +0.2817**; the robust
estimator `median(y/x)` gives **+0.3166**.

Those 86 rows are giant, many-sided, *flickering* bubbles. The single worst sample:

```
seg exp1_run0:1  frames 12→16   areas 32528 → 20234 → 32917 → 33240 → 32536
                               n_sides   30 →    20 →    28 →    29 →    29
```
A one-frame 38% area dropout and full recovery — segmentation flicker, not physics. It
survives the trusted filter because |Δlog A| = 0.475 is just under `area_jump_tol = 0.5`.
Overall the top 0.1% of rows contribute **−121.8%** of the K numerator at h=1 (they
exceed the total, with opposite sign); max |dA/dt| is **634× the median**.

**Why t+20 was unaffected:** at h=20 there are *no* rows with |n−6| ≥ 6, and bulk K
(+0.3490) equals all-rows K (+0.3483).

### Consequence for two reported conclusions
| claim in `gates_v3_stability.md` | with robust/bulk estimator |
|---|---|
| "K fails the sign test at t+1 (+0.1435, CI spans zero)" | robust K(h=1) = **+0.3166**, bulk = +0.2817 — the sign failure does not survive a non-leverage-dominated estimator |
| "horizon-stability lost: K spans 2.4×" | robust K = **+0.3166 / +0.3400 / +0.3719** → spread **1.17×**, i.e. the *same* stability the legacy analysis claimed |

Partial mitigation is not enough on its own: excluding jump-adjacent rows only lifts
K(h=1) to ~0.22 with the CI still spanning zero. The dominant mechanism is the **x²
weighting on extreme-n bubbles**, not just the jumps.

## 3. D2 — `n_sides` is systematically under-counted (MEDIUM-HIGH)

Two independent mechanisms, both measured:

1. **Background gaps inside the foam.** `_reject_plateau_borders` and the min-area filter
   zero out regions, so **13.2–13.7% of the flood-mask interior carries label 0**.
   Adjacency requires two *positive* labels to touch, so two bubbles separated by a
   zeroed region are not counted as neighbours even though they share a film.
2. **`min_shared_border_px = 3`** drops 9.4% of detected contacts (287 → 260 on exp1 f000).

Bridging the gaps by dilation recovers the missing neighbours:

| dilation | 0 (shipped) | 1 px | 2 px | 3 px |
|---|---|---|---|---|
| ⟨n⟩ all regions | **4.48** | 5.09 | 5.26 | 5.59 |
| ⟨n⟩ deep interior | **4.36** | 5.09 | 5.27 | 5.68 |

A space-filling 2D cellular structure must have ⟨n⟩ → 6 in the bulk. **Independent
corroboration from a diagnostic the gates compute but never print:** the free
(with-intercept) OLS implies dA/dt = 0 at **n₀ = 5.42–5.67**, not 6 — consistent with an
under-count of ~0.4–0.6 even before dilation.

**But this does NOT explain the negative results.** K is remarkably insensitive to a
uniform shift in n:

| h=20 | δ=0 | δ=0.5 | δ=1.0 | δ=1.5 |
|---|---|---|---|---|
| K (pooled) | 0.3483 | 0.3970 | 0.3822 | 0.3094 |

So D2 is a genuine measurement defect that **invalidates any quantitative claim about n
itself** (mean sides, n-distributions, Euler checks) and mildly biases K, but it is not
the cause of the nulls.

## 4. D3 — Gate 2's "beats persistence" is in-sample (MEDIUM)

In `run_gates_v3.gate2`, K is fit on `g` and then `predict_von_neumann(g, fit["K"])` is
scored on the same `g`. That is an in-sample comparison, and it is the number reported as
"beats persistence: YES".

Checked honestly at h=20 with a train/test split:

| | K | MAE(vN) | MAE(persistence) | beats? |
|---|---|---|---|---|
| in-sample (reported) | 0.3483 | 0.4814 | 0.6941 | yes |
| out-of-sample, test = run0 | 0.5046 (fit on run1) | 0.5012 | 0.5286 | **yes** |
| out-of-sample, test = run1 | 0.2627 (fit on run0) | 0.6609 | 0.9545 | **yes** |

**The conclusion survives**, but the reported margin is optimistic. Gate 3 does this
correctly.

## 5. D4 — the run0/run1 K gap is a scale effect, not a bug (MEDIUM, interpretation)

This was flagged as "the single most suspicious number in the project". It is not a bug.

| h=20 | run0 | run1 | ratio |
|---|---|---|---|
| **K** | 0.2627 | 0.5046 | **1.921** |
| mean \|dA/dt\| | 0.5286 | 0.9545 | **1.806** |
| rms dA/dt | 0.7265 | 1.2891 | 1.775 |
| mean n | 5.176 | 5.297 | 1.023 |
| sd(n−6) | 1.662 | 1.572 | 0.946 |

**K tracks the dA/dt scale almost exactly while the n distributions are nearly
identical**, and K is provably scale-equivariant in dA/dt (verified in stage 1). The
robust estimator reproduces the same gap (median(y/x) = +0.2666 vs +0.5241), so it is not
an outlier or fit artifact either.

**Interpretation:** run1 is a later, faster-evaporating epoch of the same raft. K carries
the units and magnitude of dA/dt, so it is **confounded with the epoch's overall
coarsening rate**. "Non-overlapping K CIs between two runs of one foam" is therefore
*not* evidence that the physics is self-inconsistent — it is evidence that **K as fitted
is not a normalised quantity**. Any cross-epoch or cross-foam K comparison inherits this.

## 6. D5 — trusted-set composition (LOW–MEDIUM, mostly by design)

Hypothesis 7 asked whether the population is structurally quiescent or interior-only.
**Partly refuted:**

* **Near-edge bubbles are NOT excluded.** `distance_to_evap_edge` is recorded in the
  segment table (`dist_mid`, `dist_spread`) but is **never used as a filter**. Trusted
  distances span 27.5–314 px (p5 = 38). ✓
* **Not quiescent:** 115 of 165 segments (**70%**) are "dynamic" (|ΔA/A| ≥ 10%).
* **But it IS a survivorship cohort by construction:** `origin_rule="frame0"` admits only
  bubbles present in the initial segmentation, and `min_persist_frames=5` requires a
  5-frame run. This is a documented `# DECISION` and the module docstring says so
  explicitly; it bounds generality rather than invalidating results.
* **`area_jump_tol = 0.5`** admits single-frame |Δlog A| up to 0.5 (a 65% jump). 0.24% of
  rows sit in 0.4–0.5 — small in count, but these are exactly the D1 leverage points.

## 7. What could NOT be verified

* **Absolute correctness of `n`.** There is no adjacency ground truth. The 14 GT masks
  give bubble *identity*, not which pairs share a film, so the ⟨n⟩→6 Euler argument is
  indirect. The dilation experiment shows the *direction* and rough size of the bias, not
  the true value.
* **Whether the physical K is genuinely constant.** No independent measurement exists;
  the horizon/epoch spread can only be characterised, not adjudicated.
* **`seg_eval.py` / `seg_temporal.py` metric internals** were exercised only through their
  existing tests (148 pass) plus prior sessions' GT work — not re-derived here.
* **Foam C's rejection** was out of scope; nothing in this audit bears on it.

## 8. Bottom line — are the recent negatives genuine?

| result | verdict |
|---|---|
| **GNN never beats baselines** | **GENUINE.** The model provably learns topology (98% skill on a graph-only task); features are correct and identical to the MLP's; no leakage. The null reflects the data, not the code. |
| **von Neumann K CI spans zero at t+1** | **LIKELY ARTIFACT.** Driven by 86 of 7106 rows (1.2%) carrying 48% of the fit weight. Robust/bulk estimators give +0.28 to +0.32. |
| **Horizon-stability lost (K spans 2.4×)** | **LIKELY ARTIFACT.** Robust K = 0.317/0.340/0.372, spread 1.17×. |
| **run0 vs run1 K non-overlapping (0.263 vs 0.505)** | **REAL but MISINTERPRETED.** It is a 1.8× dA/dt scale difference between epochs; K is not normalised. Not evidence of inconsistent physics. |
| **t+5 / t+20 K positive and beats persistence** | **GENUINE**, and survives an out-of-sample check. |
| **Foam C guard-rejected** | Not examined this session. |

**So a sixth defect does exist (D1/D2), and it cuts in the direction of the project's
established failure mode: it produced a plausible-looking wrong number rather than an
error.** The correction runs *against* one of the recent negatives — the von Neumann
weakening is substantially an artifact of a least-squares fit dominated by a handful of
flickering giant bubbles — while leaving the GNN null intact.

### Recommended repairs (NOT performed — separate session)
1. Report a **robust or leverage-capped K** alongside the least-squares K, or exclude
   |n−6| ≥ 10 (1.2% of rows) with the exclusion stated. Re-run Gate 2.
2. Fix `n_sides`: bridge label-0 gaps before computing adjacency (or compute adjacency on
   the pre-rejection watershed partition), and re-examine `min_shared_border_px = 3`.
   Validate against ⟨n⟩ → 6 for deep-interior bubbles.
3. Make Gate 2's "beats persistence" out-of-sample.
4. Normalise K (or report it per epoch with the coarsening rate alongside) before any
   cross-run or cross-foam comparison.
5. Consider tightening `area_jump_tol` below 0.475 and re-checking trusted-set size.
