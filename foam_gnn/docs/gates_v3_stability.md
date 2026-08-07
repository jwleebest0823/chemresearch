# Do the headline results survive the corrected pipeline? — one weakened, one retracted

**Answer, up front:**

| headline result | verdict |
|---|---|
| **von Neumann recovery on Foam A** | **WEAKENED** — holds at t+5 and t+20, **fails the sign test at t+1** (K CI now spans zero), and is far less horizon-stable |
| **t+20 GNN win / "topology is doing the work"** | **DOES NOT REPRODUCE — and the claim is RETRACTED** |

And a structural finding that reframes the second one entirely, found before any number was
re-run:

> **The legacy t+20 GNN result was TRAINED ON FOAM C.** Under leave-one-foam-out with
> foams {A, C}, the row `test_foam == A` means train_foams == (C,). Foam C supplied
> **786 trusted bubbles** against Foam A's 125. Foam C is now guard-rejected as
> unphysical (`docs/foamc_detection_accuracy.md`). So the headline GNN number was
> **trained on data we have since measured as unphysical**, and excluding Foam C — as
> this brief requires — removes its training set entirely. The result is therefore not
> merely "different on the corrected pipeline"; **as originally designed it is not
> evaluable at all without the rejected foam.**

## 1. Trusted set: legacy pipeline vs corrected (Foam A only)
| | bubbles | segments | rows |
|---|---|---|---|
| legacy (2026-08-03) | 125 | 166 | 8039 |
| **corrected** | **120** | **165** | **7271** |
| exp1_run0 | 79 → **74** | 106 → **102** | 4592 → **4409** |
| exp1_run1 | 46 → **46** | 60 → **63** | 3447 → **2862** (−17%) |

Composition (share of trusted bubble-frames, size × distance-to-edge; dist_bin 0 = nearest
the evaporation edge):

| | d0 | d1 | d2 | d3 | | d0 | d1 | d2 | d3 |
|---|---|---|---|---|---|---|---|---|---|
| **legacy** large | 0.127 | 0.103 | 0.067 | 0.037 | **current** large | 0.119 | 0.116 | 0.060 | 0.038 |
| medium | 0.137 | 0.105 | 0.062 | 0.029 | medium | 0.124 | 0.110 | 0.083 | 0.016 |
| small | 0.134 | 0.104 | 0.060 | 0.035 | small | 0.138 | 0.094 | 0.077 | 0.025 |

Composition is broadly preserved — no stratum collapses. The loss is concentrated in
run1's late frames, which is exactly where the mask defect lived.

## 2. Cross-validation design — a forced, and weaker, substitute
`modeling.lofo_folds` fails loud below two foams, correctly. With Foam C excluded there is
only Foam A, so **true leave-one-foam-out is impossible**. `# DECISION`: substitute
**leave-one-session-out** over `exp1_run0` / `exp1_run1`.

This is weaker in two ways that must be kept in view:
* the two runs are the **same physical raft** separated by a ~2.5 min gap — a within-foam
  consistency check, **not replication**;
* the training set shrinks from **786 Foam C bubbles to 46–79 same-foam bubbles**, so
  Gate 3 MAE values are **not numerically comparable** to the legacy table.

Gate 2 is unaffected by this: the von Neumann fit is a per-foam fit with no train/test
split, so **its numbers are directly comparable to the legacy K values.**

## 3. GATE 1 — target + trivial baselines (leave-one-session-out, cluster-bootstrap CIs)
Target: median |ΔA/A| = 0.55% (t+1), 2.3% (t+5), 8.0% (t+20); 165 segments, **70% dynamic**
(|dA/A| ≥ 10%).

| h | test | persistence | global_mean | per_bubble_linear |
|---|---|---|---|---|
| 1 | run0 | 1.8232 [0.968, 3.449] | 1.8167 (d −0.007 [−0.043, +0.033]) | 2.0776 (d +0.254 [−0.093, +0.756]) |
| 1 | run1 | 1.9112 [1.095, 3.281] | 1.9238 (d +0.013 [+0.002, +0.023]) | **1.5757 (d −0.336 [−0.593, −0.032]) BEATS** |
| 5 | run0 | 0.6795 [0.553, 0.846] | 0.6638 (d −0.016 [−0.054, +0.025]) | 0.7871 (d +0.108 [−0.143, +0.375]) |
| 5 | run1 | 1.1289 [0.875, 1.458] | **1.1149 (d −0.014 [−0.026, −0.002]) BEATS** | **0.7333 (d −0.396 [−0.655, −0.123]) BEATS** |
| 20 | run0 | 0.5286 [0.414, 0.674] | 0.5171 (d −0.012 [−0.062, +0.042]) | 0.6150 (d +0.086 [−0.153, +0.365]) |
| 20 | run1 | 0.9545 [0.761, 1.185] | **0.9416 (d −0.013 [−0.023, −0.002]) BEATS** | **0.5787 (d −0.376 [−0.569, −0.210]) BEATS** |

Note run1 is uniformly the harder session (persistence MAE ~1.8× run0's at t+20), and it is
the only one where `per_bubble_linear` beats persistence. The two runs are **not**
interchangeable populations.

## 4. GATE 2 — von Neumann: WEAKENED (directly comparable to legacy)
| h | scope | **K** | 95% CI | pearson | r²(origin) | K>0? | beats persistence? | **legacy K** |
|---|---|---|---|---|---|---|---|---|
| 1 | **A pooled** | **+0.1435** | **[−0.0369, +0.2702]** | 0.038 | 0.001 | **NO** | YES | **+0.313** |
| 5 | **A pooled** | **+0.2818** | [+0.2083, +0.3550] | 0.396 | 0.149 | YES | YES | **+0.355** |
| 20 | **A pooled** | **+0.3483** | [+0.2731, +0.4267] | 0.662 | 0.402 | YES | YES | **+0.365** |
| 1 | run0 / run1 | +0.1876 / +0.0382 | [0.110,0.231] / [−0.228,+0.486] | | | YES / no | YES / YES | |
| 5 | run0 / run1 | +0.2627 / +0.3172 | [0.168,0.327] / [0.189,0.528] | | | YES / YES | YES / YES | |
| 20 | run0 / run1 | **+0.2627 / +0.5046** | **[0.174,0.358] / [0.388,0.623]** | | | YES / YES | YES / YES | |

Against the three failure modes:
* **Correct sign — now FAILS at t+1.** K falls +0.313 → +0.1435 and its CI spans zero. It
  still passes at t+5 and t+20.
* **Horizon-stable — materially worse.** K spans 0.14 → 0.35 across horizons (**2.4×**);
  the legacy K spanned 0.313 → 0.365 (**1.17×**). A K that triples with horizon is not a
  single physical constant.
* **Beats persistence — still YES** at all three horizons, in every scope.

**And a new problem the legacy analysis could not see:** at t+20 the two runs of the *same
foam* give **K = 0.263 [0.174, 0.358] and K = 0.505 [0.388, 0.623] — non-overlapping CIs.**
Foam-level K is not even self-consistent within Foam A.

**Verdict: WEAKENED, not retracted.** The t+5/t+20 recovery survives with K about 5–20%
lower; the t+1 recovery does not, and the horizon-stability claim should be dropped.

## 5. GATE 3 — the GNN result DOES NOT REPRODUCE, and the topology claim is retracted
Leave-one-session-out, seed ensembles, cluster-bootstrap CIs, overfit gap = held-out MAE −
train MAE.

| h | test | method | MAE | d vs persistence | **d vs best baseline** | beats best? | gap |
|---|---|---|---|---|---|---|---|
| 20 | run0 | persistence | 0.5286 | — | +0.014 [−0.141, +0.194] | – | |
| 20 | run0 | global_mean | 0.5207 | −0.008 | +0.006 [−0.163, +0.202] | – | |
| 20 | run0 | von_neumann | 0.5147 | −0.014 | 0 (best) | – | |
| 20 | run0 | **mlp** | **0.4084** | −0.120 [−0.278, +0.014] | **−0.1063 [−0.1693, −0.0486]** | **YES** | −0.083 |
| 20 | run0 | **gnn** | 0.5166 | −0.012 | **+0.0019 [−0.1636, +0.1957]** | **no** | −0.007 |
| 20 | run1 | von_neumann | 0.6614 | −0.293 | 0 (best) | – | |
| 20 | run1 | **mlp** | **0.5512** | −0.403 [−0.579, −0.246] | −0.1102 [−0.2315, +0.0000] | no | 0.272 |
| 20 | run1 | **gnn** | 0.9039 | −0.051 | **+0.2425 [+0.1637, +0.3300]** | **WORSE** | 0.781 |

Across **all six** horizon × fold cells:
* the **GNN never beats the best baseline** — and at t+5 run1 and t+20 run1 it is
  *significantly worse* than it;
* the **MLP beats the best baseline in 3 of 6** cells (t+1 both folds, t+20 run0), with CIs
  clear of zero;
* `von_neumann` is the **best baseline in 5 of 6** cells — the simple physical model is now
  the strongest simple predictor.

**The MLP/GNN contrast has inverted.** The legacy claim rested on: GNN beats best baseline
(CI clear of zero) while the MLP with identical node features does not — hence topology
carries the signal. On the corrected pipeline with Foam C excluded, **the MLP wins and the
GNN does not, in the same cell (t+20 run0)**. There is no evidence left that the graph
structure contributes anything; the GNN's high overfit gap on run1 (0.781 vs the MLP's
0.272) suggests it is mostly fitting the small training set.

**"Topology is doing the work" is retracted.**

### Which cause? — the control
Two things changed at once: the pipeline, and the training set (Foam C → the other Foam A
run). Running the identical leave-one-session-out design on the **legacy** trusted set
separates them.

**Control run: the identical leave-one-session-out design on the LEGACY trusted set.**

First, this validates the harness: on the legacy trusted set my Gate 2 code reproduces the
published headline K **exactly** - **0.3131 / 0.3545 / 0.3648** against the reported
+0.313 / +0.355 / +0.365. The re-implementation is faithful, so the Gate 2 differences in
section 4 are real pipeline effects, not code differences.

Now the t+20 model comparison, same design, both datasets (d vs **best baseline**):

| t+20 | | **corrected** trusted set | **legacy** trusted set |
|---|---|---|---|
| MLP | run0 | **-0.1063 [-0.1693, -0.0486] BEATS** | -0.0362 [-0.0840, +0.0173] no |
| MLP | run1 | -0.1102 [-0.2315, +0.0000] no | -0.0768 [-0.1849, +0.0188] no |
| **GNN** | run0 | +0.0019 [-0.1636, +0.1957] **no** | +0.0384 [-0.1158, +0.2040] **no** |
| **GNN** | run1 | +0.2425 [+0.1637, +0.3300] **WORSE** | +0.2379 [+0.1504, +0.3432] **WORSE** |

**This separates the two causes, and the answer is unambiguous: the GNN result was never a
property of the pipeline - it was a property of the Foam C training set.** On the *legacy*
data, the very data the headline was computed from, the GNN fails to beat the best baseline
in both folds and is significantly *worse* in run1 - as soon as it is no longer trained on
Foam C. Changing the pipeline is not what killed it; removing 786 Foam C bubbles from the
training set is.

Two corollaries:
* **The t+20 GNN win rests entirely on training data that has since been measured as
  unphysical.** That is a stronger and worse statement than "it did not survive the mask
  fix", and it is the single most important finding of this session.
* The corrected pipeline is, if anything, *better* for the learned models: the MLP goes
  from not beating the best baseline (legacy, -0.0362 CI spanning zero) to beating it
  (corrected, -0.1063 CI clear of zero) at t+20 run0.


## 6. Extra check — run0 vs run1 (quasi-replication, framed honestly)
The leave-one-session-out folds *are* this check. The two runs are the same raft separated
by ~2.5 min, so this is **within-foam consistency, not independent replication** — it cannot
substitute for a second foam.

* **GNN t+20: fails in both folds** (run0 +0.002, run1 +0.243 vs best baseline). No
  consistency, and no effect to be consistent about.
* **MLP t+20: wins in run0, not in run1** (run1 CI upper bound exactly 0.0000). Suggestive
  but not consistent.
* **von Neumann K t+20: inconsistent between runs** — non-overlapping CIs (§4).

So even the weakest available replication check does not support the t+20 model result.

## 7. What this means
1. **The paper cannot currently claim a GNN result.** The original was trained on a foam
   since rejected; the re-run on validated data shows no graph benefit.
2. **The von Neumann recovery survives at t+5/t+20 only**, with lower K, no horizon
   stability, and within-foam inconsistency at t+20. It should be stated as
   "K is positive and beats persistence at t+5 and t+20 on Foam A", nothing stronger.
3. **The binding constraint is unchanged and is now sharper**: one usable foam, 120 trusted
   bubbles, no replication partner. Foam C needs the learned detector
   (`docs/segmentation_hybrid_seeding.md` §5) before it can rejoin, and until then no
   model claim on this dataset can be independently replicated.

Nothing here was tuned. The numbers are the first and only run of the corrected gates.

**Artifacts:** `qc/modeling/{trusted_current_foamA.csv, gate1_v3_baselines.csv,
gate2_v3_vonneumann.csv, gate3_v3_comparison.csv, gates_v3_summary.json}`. Drivers:
`dev/rebuild_trusted_foamA.py`, `dev/run_gates_v3.py`.

---

## ADDENDUM (2026-08-07) — the von Neumann verdict in this document is SUPERSEDED
The audit (`docs/correctness_audit.md`) showed the weakening reported above was largely a
least-squares leverage artifact, and the repairs are now applied
(`docs/gates_v4_repairs.md`). With a leverage-resistant estimator, a dropout-recovery
filter, and corrected neighbour counting:

| failure mode | this document | after repairs |
|---|---|---|
| correct sign | **FAILS at t+1** (K CI spans zero) | **PASSES at all three horizons** |
| horizon-stable | **2.4× spread** | **1.04× spread** (K = +0.483 / +0.497 / +0.501) |
| beats persistence | yes (in-sample) | **yes, out-of-sample, 6/6 folds** |

**The "run0 and run1 disagree" framing in §4 is withdrawn as a misinterpretation.** K
carries the magnitude of dA/dt and so is confounded with each epoch's coarsening rate;
normalised, the two runs differ by 1.09×, not 1.64×.

**The Gate 3 conclusion is unchanged and strengthened.** With K estimated properly the von
Neumann baseline becomes the best model in all six cells; the GNN is significantly *worse*
than it everywhere, and the MLP no longer beats it either. The "topology is doing the work"
retraction stands.
