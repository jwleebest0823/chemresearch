# K per bubble, mapped across the raft

Staged, with stop points. Nothing in Stage 3 is run until Stages 1 and 2 are reported.

Drivers: `dev/per_bubble_geometry.py`, `dev/per_bubble_k.py`, `dev/per_bubble_spatial.py`,
`dev/per_bubble_null.py`, `dev/per_bubble_gt_layer.py`. Artifacts: `qc/per_bubble_k/`.
(`dev/` and `qc/` are gitignored; this document and
`docs/per_bubble_preregistration.md` are the committed record.)

---

## Stage 1 — the per-bubble estimate exists, and it is mostly signal

### 1.1 What was built, and what was not invented

The shipped pooled estimator is `median(y/x)` over `|x| >= 1`, with `x = n-6` and
`y = dA/dt` (`foam_gnn.modeling.k_through_origin`, `method="robust"`). Those `y/x` are
per-**measurement** through-origin slopes. A per-**bubble** `K_i` is the median of one
bubble's own slopes — the same quantity, regrouped. Same trusted set, same horizon, same
`|x| >= 1` floor, same `seg_uid` pairing, same `n_sides`.

A guard checks this: the pooled K rebuilt from these slopes reproduces
`results_package/tables/K_fits.csv` to `1e-9` for every foam at every horizon (30 / 150 /
600 s). **Nothing published moves.**

> Two senses of "per-bubble slope" collide in this project's prose —
> `dev/paper_figures.py:245` calls the pooled estimator's `y/x` "per-bubble slopes", but
> that is a per-*measurement* slope. In this document `slope` is one measurement and
> `K_i` is a bubble.

### 1.2 The position variables, and one correction carried forward

`# DECISION (raft edge = the convex hull of the detected bubbles, per frame)` — carried
over unchanged from `dev/raft_edge_distance.py`, the corrected rule that replaced the
leaky foam mask (`docs/verification_wetness_t1.md`). The deprecated
`distance_to_evap_edge` is carried only for contrast. **Guard: the distance computed here
reproduces `qc/k_robustness/trusted_raft_edge.csv` exactly (max |diff| 0.00e+00 px).**

`# DECISION (layer 1 = bubbles touching the raft EXTERIOR, not the hull line)` — the hull
is convex, so across a concave stretch of the raft it runs outside the foam and an
air-facing bubble in a bay would never touch it. Instead the exterior is found
topologically: after the pipeline's own gap-bridging, take the unlabelled pixels, keep the
connected components that reach outside the hull, and call that the exterior. A bay's free
pixels are continuous with the outside (correctly layer 1); an interior Plateau void is a
free component wholly inside the hull (correctly not). A bubble joins layer 1 when it
shares at least `min_shared_border_px = 3` with the exterior — the same border gate the
pipeline uses for `n_sides`, so "touching air" and "having a neighbour" are decided on one
rule. Layer k+1 = a neighbour of layer k not yet assigned. **Guard: the adjacency
recomputed here reproduces the trusted table's `n_sides` on 100.00% of all 46,870 rows.**

`# DECISION (rho_hull = r / (r + d_edge) is the primary radial coordinate)` — a raft is
not a disc. `r/R_eff` is neither 0 at the centre nor 1 at the edge and **exceeds 1 on 1.4%
of Foam A measurements**. `r/(r + d_edge)` is exactly 0 at the raft centroid, exactly 1 on
the raft edge and monotone along every ray for a convex raft. Both are computed.

`# DECISION (normalise, because the raft shrinks)` — over Foam A run 0 the raft falls from
325,189 to 268,481 px² (−17%) while the median bubble radius grows 23.3 → 31.1 px.
Absolute distance to the edge is not comparable across time; `rho_hull`, `r/R_eff` and
distance-in-median-bubble-radii all are.

`# DECISION (a bubble's position is the MEDIAN over its own measurements; its spread is
the IQR)` — a mean is pulled by the frames where a bubble is about to vanish.

### 1.3 The population, and who is excluded

30 s horizon, the project's shortest matched horizon.

| foam | rows | usable (`\|n−6\|≥1`) | dropped at n=6 | bubbles | with `m ≥ 10` | median m |
|---|---|---|---|---|---|---|
| A | 10,964 | 8,981 | 1,983 (18.1%) | 156 | **146 (93.6%)** | 58 |
| C | 29,032 | 23,472 | 5,560 (19.2%) | 466 | **413 (88.6%)** | 50 |
| F | 5,972 | 5,021 | 951 (15.9%) | 56 | **53 (94.6%)** | 90 |

`# DECISION (MIN_M = 10)`. A median of m values has asymptotic standard error
≈ `1.253·σ/√m`: m=2 is meaningless, m=3 gives 0.72σ, m=5 gives 0.56σ, **m=10 gives 0.40σ**
— the first point at which a bubble's own noise is smaller than the spread across the
bubbles it will be compared with. Chosen on precision alone: no position variable and no
outcome enters it. The full sweep m ∈ {2,3,5,8,10,15,20,30,50} is in
`qc/per_bubble_k/min_m_sweep.csv`.

**Who is excluded, plainly.**

1. **The trusted set itself** is a frame-0 cohort (94.4% of trusted tracks begin at frame
   0; no later-born bubble can enter). It covers a median **93% (A) / 92% (C) / 65% (F)**
   of the bubbles detected in a frame, and its bubbles are **1.03× (A) / 1.05× (C) /
   1.09× (F)** the median detected radius — so the size bias at this level is mild. Foam
   F's coverage falls to **35% by its last frame**; Foam A's rises to 96% only because the
   raft has shrunk from 118 detected bubbles to 28.
2. **The `|n−6| ≥ 1` floor is not position-neutral.** The share of a bubble's measurements
   that survive it is **93% at layer 1 but 71–77% at layers 2–5** in Foam A (C 90% vs
   75–81%, F 89% vs 76–79%), because interior bubbles sit at n = 6 far more often. The
   estimator therefore listens to rim bubbles more per unit lifetime than to interior ones.
3. **`MIN_M` inherits that.** Raising it from 2 to 50 in Foam A raises the median bubble
   area 1,837 → 3,137 px² **and raises the layer-1 share 40.4% → 51.1%** — i.e. the cut
   selects toward *large and rim*, not toward interior. Median `K_i` moves 0.367 → 0.364
   across the whole sweep, so the headline is not sensitive to it; the composition is.

### 1.4 The per-bubble K distribution

`K_i` in px² s⁻¹, bubbles with m ≥ 10. Intervals resample bubbles.

| foam | n | p10 | p25 | **median** | p75 | p90 | IQR | frac < 0 | median(K_i) | pooled K |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 146 | 0.153 | 0.267 | **0.364** | 0.500 | 0.692 | 0.233 | 3.4% | +0.364 [+0.333, +0.400] | +0.367 [+0.333, +0.400] |
| C | 413 | 0.038 | 0.083 | **0.167** | 0.250 | 0.338 | 0.167 | 6.8% | +0.167 [+0.167, +0.183] | +0.178 [+0.167, +0.189] |
| F | 53 | −0.728 | −0.125 | **0.533** | 1.267 | 1.894 | 1.392 | 26.4% | +0.533 [+0.300, +0.839] | +0.600 [+0.400, +0.867] |

Weighting every **bubble** equally instead of every **measurement** equally moves K by
less than the interval width in all three foams. Foam F's per-bubble distribution is the
one to look at rather than its pooled number: a quarter of its bubbles have a negative
`K_i` and its IQR is 1.39, six times Foam A's.

### 1.5 Within-bubble uncertainty — and how much of the spread is real

`# DECISION (the within-bubble interval is an i.i.d. percentile bootstrap over that
bubble's own slopes, with a moving-block bootstrap at block length 5 beside it)`.
Consecutive 30 s samples share an area measurement, so the slopes are serially dependent
and the i.i.d. version is optimistic; both are reported and a claim must hold under both.

| foam | median CI half-width | block-boot | ÷ across-bubble IQR | CI excludes 0 | analytic SE ÷ boot SE |
|---|---|---|---|---|---|
| A | 0.117 | 0.108 | 0.50 | 84.9% | 1.01 |
| C | 0.117 | 0.122 | 0.70 | 64.4% | 1.02 |
| F | 0.709 | 0.934 | 0.51 | 56.6% | 1.06 |

**Variance decomposition — the Stage-1 answer to "can a map exist at all".**
`s_true = sqrt(max(0, s_obs² − s_within²))`; the reliability `(s_true/s_obs)²` is the
ceiling on any spatial signal.

| foam | n | s_obs | s_within | s_within (block) | s_true | **reliability** | reliability (block) |
|---|---|---|---|---|---|---|---|
| A | 146 | 0.173 | 0.060 | 0.055 | 0.162 | **0.88** | 0.90 |
| C | 413 | 0.124 | 0.060 | 0.062 | 0.108 | **0.77** | 0.75 |
| F | 53 | 1.088 | 0.362 | 0.476 | 1.026 | **0.89** | 0.81 |

**Roughly 80–90% of the between-bubble spread in `K_i` is real variation, not measurement
noise.** A per-bubble map is therefore not chasing noise. This says nothing yet about
whether that real variation is *spatial* — that is Stages 2 and 3.

`# DECISION (regression weights use the ANALYTIC standard error of a median,
1.253·1.4826·MAD_i/√m_i)`. Stage 2 re-runs the weighted fit hundreds of times and a
per-bubble bootstrap inside each replicate is not affordable; a weight that differed
between the null and the real test would make the null band meaningless. The two agree to
1–6% (last column above).

### 1.6 The per-bubble regression is degenerate for most bubbles

The mentor asked for a per-bubble slope from regressing `dA/dt` on `(n−6)` over the
bubble's lifetime, and for how often that is degenerate. Among bubbles with m ≥ 10:

| foam | bubbles | only 1 distinct n | ≤ 2 distinct n | samples BOTH branches | median x range |
|---|---|---|---|---|---|
| A | 146 | **18.5%** | **59.6%** | **13.7%** | 2.0 |
| C | 413 | 3.6% | 30.8% | 29.3% | 3.0 |
| F | 53 | 3.8% | 15.1% | 28.3% | 4.0 |

**In Foam A, 6 bubbles in 10 see at most two distinct neighbour counts in their whole life
and fewer than 1 in 7 is ever on both sides of n = 6.** A within-bubble regression is
therefore either undefined or fitted across a 1–2 unit range of x, and a free (with
intercept) fit is not identifiable for most bubbles. **The median-ratio form is used**, as
pre-specified. The consequence is stated once and carried forward: a per-bubble `K_i` is
almost always a median of slopes drawn from a *single* branch, so it inherits the branch
asymmetry rather than averaging over it. That is why branch composition is a covariate in
Stage 3 and not an afterthought.

At the bubble level the branch variable is nearly binary: **68% of Foam A bubbles are
entirely on the n < 6 branch, 18% entirely on n > 6, 14% mixed** (C 54 / 17 / 29,
F 72 / 0 / 28).

### 1.7 Layer occupancy, and the branch confound measured

Bubbles by their median layer, m ≥ 10:

| foam | L1 | L2 | L3 | L4 | L5+ | **interior (L ≥ 2)** |
|---|---|---|---|---|---|---|
| A | 62 | 45 | 25 | 13 | 1 | **84** |
| C | 103 | 79 | 72 | 66 | 93 | **310** |
| F | 30 | 18 | 5 | 0 | 0 | **23** |

Foam F's interior population is 23 bubbles — above the project's 20-bubble floor, but only
just. Foam A is 84; Foam C is 310 but is guard-rejected as a foam.

The confound the mentor named first, measured on the trusted measurements (Foam A):

| layer | rows | mean n | frac n<6 | frac n>6 | frac n=6 | median area px² | median rho_hull |
|---|---|---|---|---|---|---|---|
| 1 | 4,606 | **4.00** | **89.1%** | 4.0% | 6.9% | 3,249 | 0.896 |
| 2 | 3,451 | 6.10 | 36.7% | 35.2% | 28.1% | 3,549 | 0.691 |
| 3 | 2,106 | 5.99 | 43.9% | 33.4% | 22.7% | 2,776 | 0.436 |
| 4 | 767 | 5.67 | 58.9% | 14.2% | 26.9% | 1,738 | 0.255 |
| 5 | 34 | 4.41 | 70.6% | 0.0% | 29.4% | 492 | 0.162 |

**Layer 1 is 89% shrinking-branch with ⟨n⟩ = 4.00; layers 2–4 are 5.7–6.1 and roughly
balanced.** This is exactly the confound, and it is large. Note also that the *innermost*
layers drift back toward the shrinking branch and toward small area — so branch
composition is **not monotone** in position, which is one reason a linear branch covariate
is checked against a branch-stratified fit rather than trusted on its own.

Among the 84 interior Foam A bubbles the residual confounding is weak: Spearman
ρ(rho_hull, frac_shrink) = **+0.159**, ρ(rho_hull, mean area) = −0.169, ρ(rho_hull, mean
n) = −0.133, ρ(rho_hull, lifetime) = −0.136. Their `rho_hull` spans 0.114–0.874.

The 1/σ² weights concentrate: Kish effective sample size is **0.45 n** in Foam A interior
(≈ 38 of 84), 0.43 n in C, 0.71 n in F. Every β is therefore reported weighted **and**
unweighted.

### 1.8 Do bubbles move?

| foam | median rho_hull | median rho IQR | frac with rho IQR > 0.10 | frac with layer IQR ≥ 1 |
|---|---|---|---|---|
| A | 0.736 | 0.019 | 4.1% | 15.1% |
| C | 0.747 | 0.019 | 0.5% | 40.7% |
| F | 0.757 | 0.027 | 17.0% | 35.8% |

Radial position is essentially fixed for a bubble (median IQR 0.019). The *layer* index
moves for 15% (A) to 41% (C) of bubbles — not because bubbles migrate but because the raft
loses its outer bubbles and the layers renumber. This is why the radial coordinate is
primary and the layer index is used for the interior/rim cut, where it is stable.

### 1.9 Disclosure

While assembling §1.7 I also printed an **uncontrolled median `K_i` by layer for Foam A**
(layer 1 → 4: 0.317, 0.375, 0.500, 0.400) before Stage 2 had run and before the
pre-registration was written. That is a peek at the Stage-4 rim-versus-interior comparison.
It is disclosed here and in `docs/per_bubble_preregistration.md`, and it changed nothing:
the statistic, the covariate, the blocking scheme, the permutation scheme and the decision
rule were already fixed in `dev/per_bubble_spatial.py` before that number existed. Those
four numbers are uncontrolled for branch, size, the free boundary and the detector offset —
i.e. for everything Stage 2 exists to measure — and are not a result.

### Stage 1 verdict

A per-bubble K is well defined, reproduces the published pooled K exactly, and carries real
between-bubble variation (reliability 0.77–0.90). The per-bubble *regression* form is
degenerate for most bubbles and is not used. Foam A has **84 interior bubbles** for the
primary test; Foam F has 23; Foam C has 310 but is guard-rejected. The branch confound is
real and large (⟨n⟩ = 4.00 at the rim against 5.7–6.1 inside) and is not monotone in
position.

---

## Stage 2 — pending

## Stage 3 — pending

## Stage 4 — pending
