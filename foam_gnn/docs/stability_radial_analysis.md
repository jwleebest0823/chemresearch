# Stable-bubble analysis + radial-gradient test — Foam A (exp1)

Analyzes the **trusted-identity subset** of bubbles and tests whether coarsening
depends on distance to the evaporation edge. Run on the **full first contiguous
99-frame run of exp1** (49 min), per the requirement that no radial conclusion be
drawn from a <99-frame window. Modules: `foam_gnn.stability`, `foam_gnn.radial`.

## Headline (pre-registered outcome)
**The radial hypothesis could not be tested with power on the trusted subset of
Foam A.** Per the pre-specified D1 gate, this is reported as the finding — *not* as
evidence for or against the gradient. The signal, if any, lives in the
small/edge/coalescing population the current segmentation cannot track → a
segmentation-quality investment is what a real test would require.

## 1. The trusted set (identity, not size)
"Trusted" = a frame-0-origin bubble (`id ≤ frame0_max_id`) whose ID persists a
maximal run of ≥ N consecutive frames with **no frame gap, no merge, and continuous
area** (`|Δlog A| ≤ 0.5`). **No instantaneous-size threshold is applied.**

| N | trusted bubbles | segments | frac. count | frac. area |
|---|---|---|---|---|
| 3 | 90 / 142 | 92 | 0.06 | 0.15 |
| **5** | **73 / 142** | **74** | **0.05** | **0.15** |
| 8 | 62 / 142 | 62 | 0.04 | 0.14 |
| 12 | 51 / 142 | 51 | 0.03 | 0.13 |

- **No size bias (fig1):** kept vs dropped frame-0 bubbles overlap across the whole
  500–8000 px² range — the filter selects identity-stability, not size.
- **But the trusted set is a small slice:** ~5 % of all bubble-tracks and only
  **~15 % of foam area** (per-frame mean 14.6 %, fig3). Segmentation churn (1380
  reorganization births + 792 merges over 99 frames, vs 142 real frame-0 bubbles)
  means ~85 % of the foam's area at any frame is in bubbles we cannot track for 5
  frames.
- **Deeper selection (honest):** requiring *no merge* + *area continuity* excludes
  **actively-coalescing** bubbles (a bubble's dA/dt is undefined across a merge).
  So the trusted set is biased toward **quiescent, diffusion-only** bubbles whose
  dA/dt is near zero by construction (fig overlay: trusted bubbles are the sparse,
  stable ones; the big coarsened bubbles are untrusted). Coarsening-by-coalescence
  is unmeasurable per-bubble here.

## 2. Gates (pre-conditions, not post-hoc)
| gate | result | pass? |
|---|---|---|
| **Condition 1 — survival vs distance confound** | Spearman ρ = **+0.04** (95% CI −0.12..+0.20) | **PASS** — survival not correlated with distance; a null would not be a confound artifact |
| **Condition 2 — x-axis reliability** | distance-to-edge jitter (stationary bubbles) = **3.1 %** median | **PASS** — the independent variable is stable |
| **Condition 3 / D1 — power / near-edge occupancy** | near-edge bin has **3** trusted bubbles (< 5); total 73 | **FAIL** — underpowered at the edge |

Radial-bin occupancy (near→far): `3, 23, 9, 10, 9, 11, 7, 2`. The near-edge bin —
where the hypothesis predicts the strongest effect — is nearly empty.

## 3. Radial test (reported, interpretation governed by the gate)
- **Spearman ρ(dA/dt, distance) = +0.03**, 95% CI **[−0.19, +0.26]** → covers 0.
- **near-edge − interior median dA/dt = +0.16 px²/s**, 95% CI [−0.51, +0.54] → covers 0.
- **Power:** with 73 bubbles, a Spearman |ρ| below **~0.23** is indistinguishable
  from 0 at 95%. The observed |ρ|=0.03 is far below this → **underpowered**, not
  "no gradient".
- **von Neumann K per bin (fig5):** noisy and mostly *negative* (anti-physical) —
  30-s ΔA is dominated by pixel-level area noise, so per-interval K is unreliable
  on this data. Not usable as evidence either way.

**Pre-registered decision:** radial = `null`; gate = `underpowered`. Combined
verdict: **underpowered null — no interpretable radial result on the trusted
subset.**

## 4. What this does NOT claim
- Not an estimate of whole-foam coarsening (⟨R⟩, β): the trusted set is
  survivorship-selected and excludes coalescing bubbles.
- Does not resolve small-bubble segmentation.
- Any radial finding would be conditional on the trusted population representing
  the radial physics — which it does **not** here (interior-biased, ~15 % of area,
  quiescent). The honest conclusion is that a powered radial test needs a
  segmentation that can track the small/edge/coalescing bubbles.

## 5. Foam C
Not run this session (Foam A is the development + reporting case). When run, recall
Foam C may have genuinely low evaporation (small slide gap) → a weak/absent radial
gradient there could be physical, not a pipeline failure.

## Figures (qc/stability/, gitignored)
`fig1_size_distribution` (no size bias), `fig2_distance_distribution` (near-edge
sparsity), `fig3_area_fraction` (~15 % of area), `fig4_dadt_vs_distance` (null
scatter), `fig5_K_by_bin` (noisy K), `overlay_trusted_frame49` (trusted = the
stable, not the big).
