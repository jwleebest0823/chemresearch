# Stage 1 — target + trivial baselines (GATE 1)

Establishes the per-bubble coarsening-rate target and the trivial baselines every
learned model must clear, on the **trusted-stability** bubble set, under
**leave-one-foam-out** with **cluster-bootstrap** CIs (resampling whole bubbles).

Data: `qc/modeling/trusted.csv` — 284 trusted bubbles / 431 segments / 7,158
frame-rows. Foam A = 124 bubbles (`exp1_run0`+`exp1_run1`); Foam C = 160 bubbles
(`exp3`–`exp7`). Target `dA/dt` = `(A[t+h]−A[t])/(t[t+h]−t[t])` in px²/s, over
horizons t+1/t+5/t+20, only where both frames lie in the same trusted segment.

## 1. Target distribution — confirms single-step ≈ noise, horizon = signal
| scope | n | median \|ΔA/A\| | p90 \|ΔA/A\| | median \|dA/dt\| (px²/s) |
|---|---|---|---|---|
| **t+1** | 6727 | **2.7 %** | 21 % | 1.47 |
| t+5 | 5003 | 7.4 % | 29 % | 1.14 |
| t+20 | 2313 | 13 % | 38 % | 0.54 |
| **segment (whole life)** | 431 | **19 %** | 53 % | — |

Single-step fractional change (**2.7 %**) sits right on the ~2 % pixel-noise floor;
segment-level change is **19 %** — real. So the earlier finding is reproduced:
**horizon evaluation is the meaningful regime; t+1 is noise-dominated.** 69 % of
segments are "dynamic" (\|ΔA/A\| ≥ 10 %: Foam A 154/217, Foam C 145/214), so the
split below is well-populated on both sides.

Note the *rate* \|dA/dt\| **falls** with horizon (1.47→0.54): the longer the window,
the more per-step area noise averages out — which is exactly why persistence gets
stronger, not weaker, at long horizons.

## 2. Baselines (MAE of dA/dt, px²/s; LOFO; cluster-boot 95 % CI)
"beats" = paired-bootstrap ΔMAE vs persistence with the whole 95 % CI **< 0**.

### Held-out Foam A
| horizon | subset | persistence | global_mean | per_bubble_linear |
|---|---|---|---|---|
| t+1 | all | **5.44** | 5.70 | 5.95 |
| t+1 | dynamic | **5.40** | 5.59 | 5.84 |
| t+5 | all | 1.80 | **1.70** ✓beats (Δ−0.10 [−0.14,−0.06]) | 2.34 |
| t+5 | dynamic | 1.81 | **1.67** ✓beats (Δ−0.14 [−0.19,−0.10]) | 2.29 |
| t+20 | all | 0.70 | **0.67** ✓beats (Δ−0.025 [−0.031,−0.018]) | 1.19 |
| t+20 | dynamic | 0.72 | **0.69** ✓beats (Δ−0.028 [−0.034,−0.021]) | 1.15 |

### Held-out Foam C
| horizon | subset | persistence | global_mean | per_bubble_linear |
|---|---|---|---|---|
| t+1 | all | **7.46** | 7.60 | 8.67 |
| t+1 | dynamic | **8.58** | 8.65 | 9.96 |
| t+5 | all | **1.91** | 1.98 | 3.05 |
| t+5 | dynamic | **2.44** | 2.39 (Δ CI covers 0) | 3.80 |
| t+20 | all | **0.31** | 0.53 | 0.84 |
| t+20 | dynamic | **0.96** | 1.02 | 3.22 |

## 3. Gate-1 verdict
1. **Persistence (predict dA/dt = 0) is essentially unbeatable at t+1 and on Foam C
   at every horizon.** The per-step coarsening rate on trusted bubbles is at/below
   the noise floor — consistent with the trusted set being the *quiescent,
   interior, diffusion-only* slice (see `docs/stability_radial_analysis.md`,
   `docs/survivor_investigation.md`).
2. **The only resolved improvement over persistence is a constant mean-rate offset
   (`global_mean`), and only on Foam A at t+5/t+20** — a small effect (4–8 % MAE
   reduction) whose paired CI excludes 0. Physically: the trusted bubbles carry a
   weak but non-zero *net* coarsening drift that persistence's zero misses; it only
   resolves once per-step noise averages out (long horizons) and only on the
   larger Foam-A sample. It does **not** transfer to Foam C.
3. **`per_bubble_linear` is worse than persistence everywhere** — the recent-past
   slope has no predictive value; the single-step rate is noise, not a trend a line
   can extrapolate.
4. **This changes what a learned model may claim.** The honest bar for Stage 3 is
   **the better of {persistence, global_mean} at each horizon/foam**, not raw
   persistence. A GNN/MLP that merely matches persistence has added nothing; to
   count as signal it must beat `global_mean` at t+5/t+20 on Foam A (paired CI < 0)
   and beat persistence where `global_mean` does not win. Given how flat the
   baseline field is, that is a stringent, falsifiable target — exactly the point
   of gating.

**Figure:** `qc/modeling/stage1_baselines.png`. **Artifacts:**
`qc/modeling/stage1_{target_distribution,baselines}.csv`, `stage1_summary.json`.

**STOP — Gate 1.** Reporting before proceeding to Stage 2 (von Neumann).
