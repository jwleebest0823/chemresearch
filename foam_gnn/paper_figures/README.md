# Figures for the revised paper

The paper is rebuilt around one finding: **K is not a per-foam constant — it varies
systematically over a foam's lifetime.** These four main figures carry that argument, plus
one supplementary figure retained from the previous version.

Rebuild all of them with `python dev/paper_figures.py`. The script reads only committed
tables under `qc/` and re-checks each headline value against its source table before
drawing, so a figure cannot silently drift from the numbers behind it.

---

## Figure A — `figA_K_by_period.png` · the headline

K for the first, middle and last third of each foam, with cluster-bootstrap intervals and
the tracked-bubble count in every cell.

| foam | first third | middle third | last third | |
|---|---|---|---|---|
| A | +0.300 [0.283, 0.333] · 105 bub | +0.425 [0.383, 0.467] · 114 | +0.450 [0.367, 0.550] · 43 | rises 1.50× |
| C | +0.200 [0.183, 0.233] · 466 | +0.197 [0.178, 0.200] · 313 | +0.133 [0.125, 0.156] · 245 | falls 1.50× |
| **F** | **−0.300** [−0.608, −0.033] · 56 | **+1.567** [1.134, 1.916] · 34 | **+1.633** [1.134, 2.433] · 23 | **changes sign** |

Two panels: all three foams together (Foam F's zero crossing is the point, so the zero line
is drawn), and Foams A and C on an expanded scale, because at Foam F's scale they read as
flat and neither is.

**The axis is elapsed time within the foam's life, not the prediction horizon.** The
caption says so explicitly — these two axes have been conflated once already.

Source: `qc/k_robustness/task2_K_by_period.csv`.

## Figure B — `figB_wetness.png`

Is Foam C wet like F or dry like A? **Dry.** Primary panel is junction half-width ÷ bubble
radius, the sharpest discriminator (A 1.04, C 1.14, **F 5.68**); then film half-width ÷
radius and the intensity-derived liquid fraction, which uses no bubble outlines at all; then
Foam F's own drying trend, 6.10 → 3.75, still ending 3.6× above Foam A.

The caption states why **circularity is absent**: it failed as a wetness proxy and pointed
the wrong way — Foam F, the visibly wet foam, was the least circular — because bubble size
confounds it.

Source: `qc/wetness/wetness_per_frame.csv`.

## Figure C — `figC_fragility.png`

Fractional range of K under each perturbation, for all three foams: **Foam A is robust
everywhere, Foam C is precise but size-sensitive, Foam F is robust to nothing.**

| foam | drop 20% | size cut | exclusions | horizon | period |
|---|---|---|---|---|---|
| A | 0.09 | 0.14 | 0.50 | **0.02** | 0.41 |
| C | 0.09 | **0.50** | 0.56 | 0.09 | 0.38 |
| F | 0.41 | 0.57 | **1.32** | 0.37 | **3.22** |

The caption carries the branch-mixture finding: the size-cut bar is **not** measurement
error. Ground-truth K (+0.366) and detected K (+0.333) are statistically indistinguishable,
and excluding the bubbles the detector misses changes K by 0.004. The cut instead shifts the
population between two genuinely different branches — bubbles with fewer than six neighbours
fit a lower K — and area and neighbour count are strongly correlated (ρ = +0.728), with the
smallest ground-truth tercile containing **no** bubble with more than six neighbours. That is
also why the sweep never plateaus.

Source: `qc/k_robustness/task4_fragility.csv`, `qc/gt_k/n0_and_branch.csv`.

## Figure D — `figD_n0_zero_crossing.png`

The cleanest independent confirmation of von Neumann's zero-crossing in the project, and
direct evidence for why hand labels were necessary.

| | slope | intercept | **n₀** | branch asymmetry |
|---|---|---|---|---|
| **hand-labelled truth** | +0.394 | −0.003 | **6.01** [5.76, 6.31] | **1.24×** |
| Cellpose | +0.530 | +0.421 | **5.21** [5.05, 5.37] | **2.42×** |

Both fits on the same axes with their intercepts marked and dashed droplines at each
zero-crossing; the branch asymmetry beside them. Measured on the same bubbles, with the same
neighbour-counting code. **Only the 30 s horizon is supported** by 14 non-consecutive
frames, and nothing is extrapolated beyond it.

Source: `qc/gt_k/n0_and_branch.csv`, `qc/gt_k/n0_binned_medians.csv`.

## Supplementary — `figS1_leverage.png`

The leverage figure: 1.2% of measurements carrying 48% of the least-squares fit weight,
which is why the robust estimator ships. **Figure C supersedes it as a main figure** — it
makes the same point about estimate stability across five axes rather than one — but the
leverage mechanism is still true and `results_package/SUMMARY.md` §2 cites it as one of the
five measurement artifacts, so it is retained rather than dropped.

Source: `results_package/figures/fig3_leverage.png`.

---

## Standing caveat

Foams C and F have **no hand-labelled ground truth**, so their detection accuracy is
unvalidated and every value involving them inherits that. Foam A's detector is validated
against 14 hand-labelled frames (Cellpose micro-pooled F1 0.966). Every interval in every
figure is a cluster bootstrap resampling whole bubbles, 1000 replicates, 95% percentile.
Horizons are stated in seconds throughout; frame counts are never used as a time unit.
