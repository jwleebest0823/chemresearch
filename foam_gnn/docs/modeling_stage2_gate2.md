# Stage 2 — von Neumann law as the physics anchor (GATE 2)

Fits and evaluates the classical dry-foam law **dA/dt = K(n−6)** on the trusted set
(LOFO, cluster-bootstrap CIs). The through-origin slope K is the physical coarsening
constant; von Neumann requires **K > 0** and, for a material constant, K stable and
consistent across foams.

## 1. Is K stably / physically fittable? — **No.**
K = slope(dA/dt vs n−6) through the origin, per foam × horizon:

| horizon | foam | K | 95% CI | pearson r | r²(origin) | clean? |
|---|---|---|---|---|---|---|
| t+1 | A | **−0.352** | [−0.616, −0.113] | −0.08 | −0.01 | no (negative) |
| t+1 | C | −0.190 | [−0.468, +0.051] | −0.20 | −0.01 | no |
| t+5 | A | +0.115 | [−0.019, +0.234] | −0.03 | −0.07 | no (CI covers 0) |
| t+5 | C | −0.016 | [−0.148, +0.088] | −0.25 | −0.04 | no |
| t+20 | A | +0.270 | [+0.174, +0.356] | +0.21 | **−0.19** | CI>0 but r²<0 |
| t+20 | C | −0.008 | [−0.057, +0.053] | −0.16 | −0.01 | no |

Three independent ways K fails to be a physical constant:
- **Wrong sign at short horizons:** K is *negative* at t+1 on both foams (the 30-s rate
  is anti-correlated with n−6 — reproduces the earlier "K noisy/negative" note).
- **Horizon-dependent:** K drifts −0.35 → +0.27 on Foam A as the horizon grows; a
  material constant should not depend on the (arbitrary) prediction horizon. It only
  turns positive once per-step noise averages out — and even then it explains
  **negative** variance (r²(origin) = −0.19: the K(n−6) line fits *worse* than the mean).
- **Not consistent across foams:** at t+20, Foam A K=+0.27 but Foam C K≈0 (CI covers 0).
  The one "CI>0" cell (Foam A, t+20) is contradicted by Foam C.

The scatter of dA/dt vs (n−6) (figure, left) is a formless blob centred on 0 — **(n−6)
has essentially no grip on the per-bubble rate** in this trusted, quiescent population.

## 2. Does K(n−6) beat persistence? — **No, it is worse everywhere.**
LOFO (K fit on the *train* foam, applied to the held-out foam), paired ΔMAE vs persistence:

| horizon | held-out | MAE von Neumann | MAE persistence | ΔMAE [95% CI] |
|---|---|---|---|---|
| t+1 | A | 5.52 | 5.44 | +0.07 [+0.05, +0.09] worse |
| t+1 | C | 7.84 | 7.46 | +0.38 [+0.27, +0.50] worse |
| t+5 | A | 1.81 | 1.80 | +0.004 [+0.002, +0.006] worse |
| t+20 | C | 0.66 | 0.31 | +0.36 [+0.19, +0.60] worse |

Every cell is worse than persistence (ΔMAE > 0), and mostly significantly so. Because
K does not transfer across foams (it is often the wrong sign for the held-out foam),
K(n−6) is a *worse* predictor than "no change."

## 3. Residual structure — moot, because K removes ~no variance
The von Neumann residual `dA/dt − K(n−6)` has **resid_var / target_var ≈ 0.99–1.01** at
every horizon/foam: subtracting K(n−6) removes essentially none of the target variance
(expected, since K≈0 / r²<0). So the residual *is* the target; a "learn the residual
over von Neumann" framing gains nothing. There is weak, **Foam-A-only** structure in
dA/dt itself (residual ρ with distance +0.07…+0.23, with area −0.10…−0.27, CIs exclude
0; nothing resolves on Foam C) — too weak and non-transferable to anchor a physics
residual, but it is where any learnable signal would live.

## GATE 2 verdict — **Case 2: K is NOT cleanly fittable**
Of the plan's two cases, **Case 2 holds decisively**: K is not a stable, positive,
foam-consistent constant, and K(n−6) predicts *worse* than persistence.

**Recommended framing for the paper and for Stage 3:**
- The GNN (if Stage 3 is justified at all) should predict **dA/dt directly**, NOT a
  von Neumann residual. von Neumann enters only as a **reported baseline** (and it is a
  poor one) — optionally as a soft-loss prior, though given it underperforms
  persistence there is little reason to weight it.
- **The K-instability is itself a result.** Classical dry-foam von Neumann does not
  describe per-bubble coarsening of the trackable (quiescent, interior) population of
  this *wet, evaporating, quasi-2D* foam: K is horizon-dependent, sign-unstable, and
  foam-inconsistent, and n−6 explains negative variance. This is a clean physics
  statement the paper can make regardless of what the GNN does.
- **Bar for Stage 3 is unchanged and stringent:** beat the better of {persistence,
  global_mean} per horizon/foam (Gate 1). von Neumann does not raise the bar.

Combined Gate-1+2 picture: the coarsening signal on trusted bubbles is weak — neither a
constant offset (beyond a tiny Foam-A global-mean effect) nor the classical n−6 law
predicts it. Stage 3's MLP precondition (must beat persistence outside CI) is a genuine
test that may legitimately fail; if it does, "classical/no-change baselines suffice on
trackable bubbles" is the honest result.

**Figure:** `qc/modeling/stage2_vonneumann.png`. **Artifacts:**
`qc/modeling/stage2_{K_fits,vn_predictive,residual}.csv`, `stage2_summary.json`.

**STOP — Gate 2.** Awaiting the framing decision before Stage 3.
