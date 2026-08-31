# Stage 3 — MLP precondition (GATE 3): the GNN is NOT justified

Per the gated plan, the GNN is built **only if** a no-graph MLP on per-bubble
features first beats the better of {persistence, global_mean} **outside the paired
bootstrap CI** at some horizon. It does not. **The precondition fails, so the GNN
was not built** — the honest, pre-committed outcome (c): trivial baselines suffice
on the trackable population.

## The precondition test
No-graph MLP (2×64, dropout 0.3, weight-decay 1e-4, 5-seed ensemble, bubble-level
early stopping) predicting **dA/dt directly** (Gate-2 decision: no von Neumann
prior). Leave-one-foam-out; features = {area, n_sides, distance-to-edge}, no
absolute position. "beats" = paired-bootstrap ΔMAE vs the *better* trivial baseline
with the whole 95% CI < 0.

| horizon | held-out | MAE MLP | MAE persist | MAE gmean | better | ΔMAE vs better [95% CI] | beats? |
|---|---|---|---|---|---|---|---|
| t+1 | A | 6.34 | **5.44** | 5.78 | persistence | +0.90 [+0.67, +1.13] | no (worse) |
| t+1 | C | 7.49 | **7.46** | 7.61 | persistence | +0.03 [−0.02, +0.08] | no (tie) |
| t+5 | A | 1.70 | 1.80 | **1.70** | global_mean | +0.003 [−0.008, +0.015] | no (tie) |
| t+5 | C | 1.99 | **1.91** | 1.99 | persistence | +0.08 [−0.02, +0.16] | no (tie) |
| t+20 | A | 0.669 | 0.699 | **0.672** | global_mean | −0.003 [−0.006, +0.0002] | no (CI touches 0) |
| t+20 | C | 0.647 | **0.308** | 0.495 | persistence | +0.34 [+0.16, +0.46] | no (worse) |

**Nowhere does the MLP beat the better baseline outside the CI.** The pattern is
diagnostic:
- Where the MLP *tries* to use the features (t+1 Foam A: +0.90; t+20 Foam C: +0.34)
  it is **significantly worse** — it fits train-foam structure that does not transfer.
- At the horizons with the most averaged signal (t+5/t+20 Foam A) the MLP **collapses
  to `global_mean`** (ΔMAE ≈ 0, CI straddles/touches 0): it recovers only the weak
  constant mean-rate offset that `global_mean` already encodes, extracting **no
  additional per-bubble signal**. The single closest cell (Foam A t+20 vs global_mean,
  Δ −0.003) has a CI that still includes 0 — a tie, not a win.

The null is not a broken model: the same training harness cleanly learns an implanted
linear signal and collapses to the mean on pure noise (`tests/test_nn_models.py`). The
signal simply is not there at the per-bubble level.

**Why building the GNN cannot change this.** A GNN adds *graph structure* over the
*same* per-bubble features. It cannot manufacture per-bubble coarsening signal that the
MLP — given those features directly — could not find. With the MLP unable to clear the
trivial-baseline bar, the pre-commitment (and basic scientific hygiene) says stop rather
than tune a larger model toward a manufactured win.

## Headline scientific findings for the paper
This modeling stage produced **two positive, publishable results** — neither is a
failed intermediate step:

1. **Classical von Neumann coarsening does not describe this wet, evaporating,
   quasi-2D foam's trackable population** (Stage 2 / `docs/modeling_stage2_gate2.md`).
   The coarsening constant K in `dA/dt = K(n−6)` is **not a stable physical constant
   here**: it is the *wrong sign* at short horizons, *horizon-dependent* (Foam A −0.35→
   +0.27), *foam-inconsistent* (t+20: Foam A +0.27 vs Foam C ≈0), explains **negative**
   variance (r²(origin)<0), and predicts **worse than persistence** at every horizon.
   (n−6) has no grip on the per-bubble rate. This is a clean, quantified departure from
   textbook dry-foam physics, with the mechanism understood: the only reliably trackable
   bubbles are the quiescent, interior, diffusion-limited slice (~15% of area), where the
   n-dependence of coarsening is swamped and coalescence — the real coarsening channel —
   is unmeasurable per-bubble.

2. **No learned model is justified on the trackable population** (this gate). Under
   leakage-safe LOFO with cluster-bootstrap CIs, neither a constant offset, the classical
   law, nor a regularized MLP beats "predict no change" outside the CI at any horizon. The
   per-bubble coarsening-rate signal on trusted bubbles is at/below the measurement-noise
   floor (single-step |ΔA/A| = 2.7% ≈ pixel noise; Stage 1). The binding constraint is
   **data, not model capacity**: the segmentation can only track the quiescent interior
   bubbles, and the coarsening physics lives in the small/near-edge/coalescing population
   it cannot yet follow (see `docs/stability_radial_analysis.md`,
   `docs/survivor_investigation.md`). A GNN cannot add value until segmentation can track
   that population — that is the concrete next investment, not a bigger model.

## Status
- GNN, ablations: **not built** (precondition not met — pre-committed stop).
- New code: `foam_gnn.nn_models` (optional-torch MLP + seed-ensemble trainer),
  `tests/test_nn_models.py` (torch-gated). Driver `dev/stage3_mlp.py` (gitignored).
- **Figure:** `qc/modeling/stage3_mlp.png`. **Artifacts:** `qc/modeling/stage3_mlp.csv`,
  `stage3_mlp_summary.json`.

**GATE 3 — reported. Outcome (c): classical/trivial baselines suffice on the trackable
population; a learned model (and therefore the GNN) is not justified on this data.**
