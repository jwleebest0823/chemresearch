# Modeling gates re-run on the corrected dataset — and the GNN

The Gate 1–3 conclusions were derived on the **defective ratchet's** trusted set (a
quiescent-biased population of merged blobs). The corrected pipeline yields a different
and much larger trusted population, so everything below is **re-derived, not assumed**.
Two conclusions change materially.

## Input quality (what feeds the gates)
* **Detection is now GT-validated on Foam A**: F1 **0.899** (P 0.914 / R 0.885),
  split = merge = 0, but **~37% of small near-edge bubbles are never detected**
  (`docs/segmentation_detection_accuracy.md`). Foam C has **no ground truth** — it could
  not be reliably hand-labeled — so its detection quality is unknown.
* **Trusted set**: 284 → **911 bubbles** (Foam A 124→125, Foam C 160→**786**), 7,158 →
  **20,335** bubble-frames.
* **The near-edge exclusion is fixed.** The old set was so interior-biased that the
  radial analysis had 3 near-edge bubbles out of 73. Now near-edge holds **39.8%** of
  Foam A and **56.2%** of Foam C trusted bubble-frames, roughly uniform across size
  (Foam A bin-0 shares: small 0.134, medium 0.137, large 0.127). *Still excluded by
  construction*: actively-coalescing bubbles (no-merge + area-continuity filter), and
  the ~37% of small near-edge bubbles never detected upstream.

## Gate 1 — target and trivial baselines
| scope | n | median \|ΔA/A\| |
|---|---|---|
| t+1 | 18,670 | **2.0%** |
| t+5 | 12,010 | 3.7% |
| t+20 | 5,496 | 8.5% |
| segment | 1,665 | **17.2%** |

Unchanged in character: single-step change sits at the ~2% noise floor, segment-level
change is real (17%), so horizon evaluation remains the meaningful regime. 68% of
segments are dynamic. `global_mean` beats persistence by a small but resolved margin
almost everywhere; **`per_bubble_linear` now beats persistence on Foam A at t+5/t+20**
(−0.281 and −0.238, CIs excluding 0) — it did not before — while remaining much worse on
Foam C.

## Gate 2 — von Neumann: **the conclusion changes on Foam A**
| horizon | foam | K | 95% CI | pearson | r²(origin) | K>0 | beats persistence |
|---|---|---|---|---|---|---|---|
| t+1 | **A** | **+0.313** | [+0.118, +0.465] | 0.036 | 0.001 | **YES** | **YES** |
| t+5 | **A** | **+0.355** | [+0.238, +0.481] | 0.579 | 0.283 | **YES** | **YES** |
| t+20 | **A** | **+0.365** | [+0.276, +0.448] | **0.754** | **0.492** | **YES** | **YES** |
| t+1 | C | −0.196 | [−0.246, −0.152] | −0.175 | 0.011 | no | no |
| t+5 | C | −0.052 | [−0.071, −0.034] | −0.279 | 0.014 | no | no |
| t+20 | C | +0.013 | [−0.012, +0.031] | −0.138 | −0.054 | no | no |

**On Foam A, von Neumann's law now holds.** All three of the old failure modes are gone:
K is **correctly signed** at every horizon, **stable** across them (+0.313 → +0.355 →
+0.365, versus the old −0.35 → +0.27 drift), and it **beats persistence** everywhere.
The relationship strengthens with horizon exactly as noise-averaging predicts —
r² 0.001 → 0.283 → **0.492**, pearson → **0.754**.

**The most likely mechanism is the Plateau-border defect.** Von Neumann's law is a
statement about *n*, the number of neighbours. The old segmentation inserted ~2 spurious
Plateau-border "bubbles" per real bubble, sitting exactly *between* real neighbours — so
every bubble's *n* was corrupted. Fixing detection restored the n–dA/dt relationship.
The earlier "von Neumann fails in this foam" conclusion was therefore substantially a
**measurement artifact, not physics** — on Foam A.

**It still fails on Foam C** (K negative or zero, never beats persistence). The honest
reading: von Neumann emerges where detection is accurate and fails where it is not
validated. Foam C is far denser, has no ground truth, and its *n* is probably still
unreliable. **This is a hypothesis about Foam C's measurement quality, not a physics
claim** — it cannot be settled without Foam C ground truth, which could not be produced.

*Knock-on:* `docs/exp10_10s_vonneumann.md` (10 s vs 30 s-subsampled) used the defective
segmenter on both arms. Its *sampling* contrast remains internally controlled, but its
conclusion that "von Neumann fails and it is not a sampling artifact" must now be
re-examined on corrected tracks — the failure it measured is at least partly the
Plateau-border artifact.

## Gate 3 — MLP and GNN, and the mandatory comparison
Leave-one-foam-out, cluster-bootstrap CIs (resampling whole bubbles), 5-seed MLP
ensemble / 3-seed GNN ensemble. `*` = beats outside the CI.

| horizon | foam | persistence | global_mean | von Neumann | MLP | **GNN** |
|---|---|---|---|---|---|---|
| t+1 | A | 2.008 | **1.980** | 2.249 | 2.727 | 1.985 |
| t+1 | C | 2.680 | **2.679** | 2.827 | 2.841 | 2.715 |
| t+5 | A | 0.790 | **0.767** | 0.849 | 1.103 | 0.971 |
| t+5 | C | **0.720** | 0.733 | 1.244 | 1.031 | 0.893 |
| t+20 | A | 0.693 | 0.668 | 0.674 | 0.636 | **0.627** |
| t+20 | C | **0.195** | 0.196 | 1.074 | 0.674 | 0.641 |

**The pre-committed verdict — outcome (a), in exactly one cell:**

* **Foam A, t+20: the GNN beats every baseline outside the CI.** vs persistence
  −0.0655 [−0.1005, −0.0306]; **vs the best baseline (global_mean) −0.0411
  [−0.0617, −0.0208]** — the whole interval below zero.
* **And topology is what does it.** The MLP at the same cell (0.636) beats persistence
  but **fails** against the best baseline (−0.0322 [−0.0776, **+0.0082**], CI includes
  0). The GNN sees the *same node features* as the MLP and differs only by message
  passing, so the gap is attributable to graph structure.
* **Everywhere else the learned models lose**, often badly — especially on Foam C, where
  nothing beats persistence at any horizon and the GNN is 3× worse at t+20.

### How much weight this single win deserves
Stated plainly: **it is one cell out of six**, and with six comparisons at 95% one
"significant" result is close to what chance alone would produce. I am not going to
present it as an established result on that basis alone. What raises it above a fluke:

1. The CI is comfortably clear of zero (−0.062 to −0.021), not marginal.
2. It is the **longest horizon**, where the target is furthest above the noise floor —
   the regime Gate 1 identifies as the only meaningful one.
3. It is on the **only foam whose detection is ground-truth validated** (F1 0.899).
4. **It agrees with Gate 2.** Von Neumann — a purely topological law in *n* — also
   works on Foam A and only on Foam A, strengthening with horizon in the same way. Two
   independent methods that both use neighbour structure succeed on the same foam at the
   same horizon and fail on the other. That coherence is a physical story, not an
   isolated statistical accident.

**Honest conclusion:** on the corrected data there *is* now measurable per-bubble
coarsening signal on Foam A at long horizons, it *is* topological, and a GNN captures a
little more of it than the classical law or any trivial baseline. The effect is small
(~6% MAE reduction vs global_mean) and demonstrated in one foam × one horizon; it needs
replication on a second GT-validated foam before it can carry a paper.

**Overfitting check:** MLP test−train MAE gaps are reported per cell in
`gate3_v2_comparison.csv`; both learned models were early-stopped on held-out *whole
bubbles* from the training foam, and standardisation used train-fold statistics only.

## Caveats that bound all of the above
1. **Foam C detection is unvalidated.** Every Foam C number inherits unknown detection
   error; its von Neumann failure and its model failures may be measurement, not physics.
2. **~37% of small near-edge bubbles are never detected** on Foam A, so that stratum is
   censored before any model sees it.
3. **Actively-coalescing bubbles remain excluded** by the trusted filter, so this is
   still diffusion-dominated coarsening, not the full physics.
4. **Graph topology is Delaunay-approximated** (`# DECISION` in `dev/run_gates_v2.py`):
   re-deriving true film adjacency per frame costs ~1 h of segmentation. Node features
   are identical between MLP and GNN, so the topology comparison is still fair, but the
   edges are geometric neighbours rather than measured contact lines.

**Artifacts:** `qc/modeling/{gate1_v2_baselines,gate2_v2_vonneumann,gate3_v2_comparison}.csv`,
`gates_v2_summary.json`, `trusted_v2*.csv`. Drivers: `dev/build_trusted_v2.py`,
`dev/run_gates_v2.py`. Model: `foam_gnn.gnn`.
