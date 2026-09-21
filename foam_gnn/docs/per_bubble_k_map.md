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

## Stage 2 — the pipeline is clean; the detector is not

Foam A, 30 s horizon, `K0 = +0.3667` px² s⁻¹. 1,000 realisations per configuration.
β is reported throughout as **px² s⁻¹ per unit ρ** — the weighted least-squares slope of
`K_i` on `rho_hull` with branch fraction as a covariate, the Stage-3 statistic, computed by
the same function on synthetic and real data alike.

### 2.0 What the null inherits

Only `dA/dt` is replaced. `n_sides`, positions, lifetimes, sampling and areas are the real
ones, so the population is built from `x` and position alone and **no synthetic draw can
change who is in it** (guarded). Both asymmetries the mentor asked to be preserved are
therefore present by construction, not by model:

| layer | rows | usable share | mean n | frac n<6 | frac n>6 | median ρ |
|---|---|---|---|---|---|---|
| 1 | 4,606 | **93.1%** | 4.00 | 89.1% | 4.0% | 0.896 |
| 2 | 3,451 | 71.9% | 6.10 | 36.7% | 35.2% | 0.691 |
| 3 | 2,106 | 77.3% | 5.99 | 43.9% | 33.4% | 0.436 |
| 4 | 767 | 73.1% | 5.67 | 58.9% | 14.2% | 0.255 |
| 5 | 34 | 70.6% | 4.41 | 70.6% | 0.0% | 0.162 |

Rim weighting: layer 1 contributes 4,606 rows at 93% usable against 6,358 rows at 74% for
layers 2+. Branch composition is **non-monotone** — the shrinking-branch share falls from
89% at layer 1 to 37% at layer 2 and then climbs back to 59–71% at layers 4–5. Both are
carried into every null replicate.

### 2.1 Noise model

`sigma(A) = s·A^p` with **p = +0.190, s = 3.488**, fitted from the area-decile scale of
Foam A's own residuals; the flat variant is `p = 0, s = 15.63`. Achieved match: robust SD
0.7420 synthetic against 0.7415 real; area-decile scales 0.563/0.683/0.740/0.821/0.997
against 0.641/0.593/0.740/0.791/1.136 — good except in the **largest** decile, where the
synthetic noise is ~12% light, so the null is very slightly optimistic for big bubbles. The
real residual is right-skewed (p5/p95 −1.33/+1.80 against −1.28/+1.28 Gaussian); the
resampled-tail variant covers that and moves nothing.

### 2.2 Null test — **PASS**

| population | noise model | null median | null 95% band |
|---|---|---|---|
| interior (L≥2), 84 bub | size-scaled Gaussian | **−0.0006** | **[−0.0491, +0.0452]** |
| interior | flat Gaussian | −0.0000 | [−0.0502, +0.0491] |
| interior | size-scaled, resampled tails | +0.0007 | [−0.0478, +0.0502] |
| all bubbles, 146 | size-scaled Gaussian | +0.0001 | [−0.0272, +0.0264] |
| all | flat Gaussian | +0.0006 | [−0.0302, +0.0297] |
| all | size-scaled, resampled tails | −0.0003 | [−0.0301, +0.0316] |

**The recovered gradient is consistent with zero under every noise model.** Geometry,
branch composition, rim weighting and sampling do not, by themselves, manufacture a radial
gradient. The Stage-1 pipeline is clean in this specific sense.

### 2.3 Detector-offset null — the intercept alone makes a gradient

Injecting Cellpose's measured intercept `c0 = +0.4211` px² s⁻¹ (GT: −0.003) with **no**
true gradient:

| c0 | branch covariate | median β | 95% band |
|---|---|---|---|
| 0.2995 (c0 CI lo) | yes | +0.0737 | [+0.0180, +0.1241] |
| **0.4211** | **yes** | **+0.1040** | **[+0.0413, +0.1606]** |
| 0.5465 (c0 CI hi) | yes | +0.1371 | [+0.0652, +0.1990] |
| 0.2995 | no | −0.1429 | [−0.2105, −0.0650] |
| **0.4211** | **no** | **−0.2005** | **[−0.2862, −0.1013]** |
| 0.5465 | no | −0.2621 | [−0.3625, −0.1378] |

Two things matter here. First, **the offset alone produces a gradient two to four times the
width of the pure null band.** Second, **the branch covariate does not remove it — it flips
its sign**, from −0.20 to +0.10. That is expected and worth stating plainly: the offset
enters as `c/x`, which is continuous in n, while the covariate is a branch *fraction* that
is nearly binary at the bubble level. Adjusting for branch removes the part that acts
through branch membership and leaves the part that acts through the magnitude of `n−6`.
Across c0's own interval the operative band is **[+0.018, +0.199]**.

### 2.4 Recovery — the minimum detectable gradient

Attenuation is 1.01 — the pipeline returns injected gradients essentially unbiased.

| population | null \|β\| p95 | **MDE (80% power)** | centre-to-rim ΔK over its own ρ span | as % of K0 |
|---|---|---|---|---|
| **interior (L≥2), 84 bubbles** | 0.0478 | **β = 0.071** | **+0.054 px² s⁻¹** over ρ 0.114–0.874 | **15%** |
| all bubbles, 146 | 0.0270 | β = 0.043 | +0.037 px² s⁻¹ over ρ 0.114–0.963 | 10% |
| interior, against the **operative** null (c0 present) | band [+0.041, +0.161] | **β = 0.081** | **+0.061 px² s⁻¹** | **17%** |

**For Foam A's 84 interior bubbles the minimum detectable gradient is β = 0.071 px² s⁻¹ per
unit ρ against the pure null, and β = 0.081 against the operative null that includes the
detector's intercept — a centre-to-rim change in K of +0.054 to +0.061 px² s⁻¹, i.e. 15–17%
of K0.** Anything smaller than that is "not detected", not "absent". Power reaches 54.6% at
β = 0.05 and 91.2% at β = 0.08.

### 2.5 Ground-truth check — **the detector's per-bubble error is position-dependent**

Seven hand-labelled consecutive Foam A pairs, 409 genuinely paired bubbles (merged on the
GT↔Cellpose correspondence, not on the `matched_both_detectors` flag, which yields 409 GT
against 411 CP rows — not the same bubbles). Layers computed on each detector's own map;
strata taken from the **GT** layer so the detector cannot choose its own strata.

`n_sides` disagrees on **13.2%** of paired bubbles, median |Δn| = 1 — and at n = 4 a Δn of
1 doubles `y/x`.

Median (Cellpose − hand) per-bubble slope, by GT layer:

| GT layer | n | median GT slope | median CP slope | median diff | [bubble boot] | [pair block] |
|---|---|---|---|---|---|---|
| 1 (rim) | 139 | 0.333 | 0.283 | −0.044 | [−0.117, +0.022] | [−0.192, +0.033] |
| 2 | 99 | 0.466 | 0.433 | −0.033 | [−0.117, +0.133] | [−0.133, +0.133] |
| **3** | 63 | 0.332 | 0.500 | **+0.167** | **[+0.028, +0.267]** | **[+0.044, +0.267]** |
| 4 | 19 | 0.433 | 0.533 | +0.100 | [−0.033, +0.233] | [−0.017, +0.292] |

Layer 3 is resolved under both interval schemes. Interior (L≥2) minus rim bias is
**+0.111 [+0.006, +0.222]**.

**Where the error comes from.** Decomposed on the same 409 pairs:

* the **area** error has *no* radial gradient — slope of (dA/dt_CP − dA/dt_GT) on ρ is
  **+0.007 [−0.622, +0.642]**;
* the **neighbour-count** error does — slope of (n_CP − n_GT) on ρ is
  **−0.416 [−0.588, −0.255]** neighbours per unit ρ.

So this is a *topology* error, not a segmentation-area error, which is consistent with
everything else this project has measured about `n_sides` at the raft edge.

**The size of the artifact, in the Stage-3 statistic's own units** (slope of the per-bubble
CP−GT slope difference on ρ):

| population | branch cov | estimator | slope | [bubble boot] | [pair block] |
|---|---|---|---|---|---|
| all paired (320) | no | OLS | −0.593 | [−0.976, −0.270] | [−1.139, −0.181] |
| all paired | no | Theil-Sen | −0.391 | [−0.589, −0.196] | [−0.732, −0.190] |
| all paired | yes | OLS | −0.310 | [−0.616, +0.010] | [−0.703, −0.027] |
| all paired | yes | Theil-Sen | −0.143 | [−0.335, +0.041] | [−0.384, +0.017] |
| **interior L≥2 (181)** | **yes** | **OLS** | **−0.542** | **[−1.091, −0.068]** | **[−1.005, −0.187]** |
| **interior L≥2** | **yes** | **Theil-Sen** | **−0.362** | **[−0.770, +0.025]** | **[−0.714, −0.130]** |

OLS on a `y/x` ratio is leverage-sensitive — the failure mode this project audited in S1 —
so Theil-Sen and a median-in-ρ-bins fit are reported beside it; all three agree in sign and
order of magnitude. A second, independent route agrees: pooled robust K on these frames is
rim +0.333 / interior +0.427 by hand (a real +0.094 contrast) against rim +0.283 / interior
+0.467 by Cellpose (+0.184) — **the detector roughly doubles the interior-over-rim
contrast**, which over the relevant Δρ ≈ 0.35 is a slope near −0.26.

Note the sign. The offset-null predicts **+0.10** with the covariate; the directly measured
detector artifact is **−0.36 to −0.54**. They are consistent without the covariate (−0.20
predicted against −0.39 measured, overlapping intervals), so the intercept model accounts
for roughly half of the detector's position-dependent error and the ρ-dependent `n_sides`
error accounts for the rest. **The branch covariate barely helps in the interior**
(−0.615 → −0.542): inside the raft the offset does not act mainly through branch membership.

### 2.6 Stage 2 verdict

1. **The null test passes.** Nothing in the geometry, the branch composition, the rim
   weighting or the sampling manufactures a radial gradient: −0.0006 [−0.0491, +0.0452].
   Stage 3 is not disqualified.
2. **The minimum detectable gradient for Foam A's 84 interior bubbles is β = 0.071**
   (pure null) **to 0.081** (operative null) **px² s⁻¹ per unit ρ = 15–17% of K0 from
   centre to rim.**
3. **But the detector's own error carries a radial gradient of β ≈ −0.36 to −0.54 in the
   interior, with intervals reaching −0.77 to −1.09.** That is **5 to 8 times** the
   minimum detectable effect and **3 to 5 times** the detector-offset band. It is a
   neighbour-count error, not an area error, and the branch covariate does not remove it.
4. **Therefore the binding constraint on Stage 3 is not power — it is the detector.** Any
   interior gradient smaller in magnitude than roughly 0.5 px² s⁻¹ per unit ρ cannot be
   separated from Cellpose's own position-dependent `n_sides` error, in either direction.
   The pre-registration must state this before the primary test is run, and the
   pre-committed reporting rule "gradient present but no larger than the detector band →
   cannot be distinguished from a measurement artifact" is the one most likely to apply.

**Caveats carried forward.** The hand labels are themselves 86.6% pixel-identical to a
watershed pre-seed (`dev/gt_preseed_overlap.py`), so GT–Cellpose agreement is partly built
in and the ~13% that differs carries the whole signal; the GT's mean n (5.081) is well
below the watershed's (5.681), so the hand corrections did remove the watershed's rim
over-count rather than inheriting it. The detector band is measured on 320–409 single
measurements from 7 frame pairs, while a `K_i` is a median of ~55 measurements: the
Theil-Sen and binned-median estimates target the systematic part that survives that
averaging, which is why they are quoted ahead of OLS. The top area decile's synthetic noise
is ~12% light.

## Stage 3 — the pre-registered primary test

Run exactly as `docs/per_bubble_preregistration.md` specifies. That document was committed
at **`9281645`, before this analysis was run**; the decision rule below is evaluated
mechanically against thresholds copied from it, not chosen here.

Population: **Foam A, interior (median layer ≥ 2), m ≥ 10, 30 s horizon — 84 bubbles**,
ρ spanning 0.114–0.874, 59 shrinking-branch / 25 growing-branch.

### 3.1 The primary statistic

    beta = -0.2781  px^2 s^-1 per unit rho

| | |
|---|---|
| 95% CI, angular-sector block bootstrap (8 sectors, pre-registered) | **[−0.4367, −0.0679]** |
| 95% CI, ordinary bubble bootstrap | [−0.5202, −0.0850] |
| permutation p (sector × branch strata, 5,000) | **0.0070** |
| Moran's I on residuals (k-NN, k = 6) | **+0.1254** (E = −0.0120, **p = 0.021**) |

β < 0 means **K falls toward the rim** — higher in the middle of the raft.

### 3.2 Every other way it could have been computed

| variant | β |
|---|---|
| **Theil-Sen, branch-adjusted (PRIMARY)** | **−0.2781** |
| Theil-Sen, unadjusted | −0.3134 |
| WLS + branch covariate (secondary) | −0.1794, CI **[−0.3154, +0.0443]** |
| WLS, no branch covariate | −0.2380 |
| WLS, unweighted | −0.3675 |
| Spearman ρ (branch-centred K) | −0.2703 |
| within the n < 6 branch (n = 59) | −0.3288 |
| within the n > 6 branch (n = 25) | −0.2201 |
| slope through the five ρ-quintile medians | −0.144 |

**The sign is stable across all nine.** The magnitude is not: it ranges from −0.14 to −0.37
depending on the summary. Over the observed ρ span this is a centre-to-rim fall of
**0.086 px² s⁻¹** (quintile medians, innermost minus outermost) to **0.211** (Theil-Sen ×
span) — i.e. **23% to 58% of K0**. The 1/σ² weights concentrate hard (Kish ESS 37.6 of 84),
which is why the unweighted and weighted WLS variants differ by a factor of two.

**The secondary does not resolve it.** The WLS + covariate interval [−0.3154, +0.0443]
includes zero. The pre-registered rule required only sign stability from the secondary, and
that holds; but it is reported here plainly rather than buried.

### 3.3 Sector-count sensitivity — the interval is not stable, the p-value is

| N_SECTORS | β | 95% block CI | perm p |
|---|---|---|---|
| 4 | −0.2781 | [−0.4047, **+0.0703**] | 0.0205 |
| 6 | −0.2781 | [−0.4910, **+0.0025**] | 0.0085 |
| **8 (pre-registered)** | −0.2781 | **[−0.4367, −0.0679]** | 0.0045 |
| 12 | −0.2781 | [−0.5177, −0.0606] | 0.0205 |

**At 4 and 6 sectors the interval includes zero.** With only 4 or 6 blocks a block bootstrap
is very coarse, and 8–12 is the usual range, but the honest statement is that *the exclusion
of zero depends on the blocking choice while the permutation p does not* (0.0045–0.0205
throughout).

### 3.4 Decision rule A — is the measured gradient resolved?

| criterion | |
|---|---|
| 95% block CI excludes 0 | **PASS** |
| permutation p < 0.05 | **PASS** |
| \|β\| > pure null band (0.0587) | **PASS** |
| branch-stratified slope agrees in sign | **PASS** |
| sign stable across sectors and WLS | **PASS** |

**→ RESOLVED.** A radial gradient in `K_i` is present in the measured data.

### 3.5 Decision rule B — is it distinguishable from the detector?

**|β| = 0.278, against a detector band whose point estimate is 0.362 and whose interval
reaches 0.769.**

> **→ INDISTINGUISHABLE from the detector's position-dependent neighbour-count error.**

The whole measured gradient is smaller than the artifact Stage 2 measured directly against
hand labels, and points in the **same direction** as it (both negative). Figure 7 shows the
fitted line lying essentially on top of the detector band's central line and wholly inside
that band.

### 3.6 Decision rule C — the detector-corrected estimate (mandatory)

`beta_det` is a **signed bias**, not noise. The detector biases β downward by ≈ 0.36, so:

    beta_corr = beta_obs - beta_det = -0.2781 - (-0.3620) = +0.0839
                95% (convolved)      [-0.3410, +0.5231]

**Once the measured detector bias is removed, the best estimate of the true gradient is
+0.08 — near zero, with an interval that spans from a strong inward fall to a stronger
outward rise.** The sign of the *physical* gradient is not determined by this experiment.

Caveats: `beta_det` comes from 7 frame pairs of single measurements on a GT-layer-defined
population, while `beta_obs` uses 99 frames of per-bubble medians; the correction assumes
the detector bias measured on those 14 frames applies across the sequence.

### 3.7 Decision rule D — the null, quantified

The minimum detectable gradient is **β = 0.081** (80% power vs the pure null), i.e.
**+0.062 px² s⁻¹ centre-to-rim = 17% of K0**; **0.091** against the operative null. The
measured β = −0.278 is well above this, so **this is not a power failure** — the pipeline
saw a gradient it was easily able to see. It is a *calibration* failure: the instrument's
own error in the same coordinate is larger than the signal.

### 3.8 Moran's I — residual spatial dependence survives

`I = +0.1254` against `E = −0.0120`, p = 0.021. Neighbouring interior bubbles still have
correlated residuals after the radial and branch terms are removed. The angular-sector
block bootstrap absorbs dependence at the sector scale but not at the few-bubble scale, so
**the intervals above are, if anything, still optimistic** — which reinforces §3.3's
finding that the exclusion of zero is fragile.

---

## Stage 4 — secondary analyses (exploratory)

Benjamini–Hochberg across the six pre-registered secondaries. **None of these revises
Stage 3.**

| # | test | statistic | 95% interval | p | BH p |
|---|---|---|---|---|---|
| S1 | Foam A rim vs interior, branch-centred | +0.0397 | [−0.0166, +0.1471] | 0.0942 | 0.2355 |
| S2 | **Foam C interior gradient** (310 bubbles) | **−0.0000** | **[−0.0428, +0.0485]** | 0.9272 | 0.9272 |
| S3 | Foam F interior gradient (23 bubbles) | +1.6898 | [−0.3687, +5.9224] | 0.3248 | 0.4562 |
| S4 | Foam F time × space | **REFUSED** | — | — | — |
| S5 | lifetime, position+branch controlled | −0.0267 | [−0.0872, +0.0138] | 0.3650 | 0.4562 |
| S6 | **GT rim vs interior (hand labels)** | **+0.0779** | [−0.0111, +0.1583] | 0.0925 | 0.2355 |

**S1 — rim versus interior in Foam A.** Once branch composition is removed, interior minus
rim is **+0.0397 [−0.0166, +0.1471], p = 0.094 — not resolved.** This matters for published
work: see §5 below. And it cannot separate evaporation from the free boundary in any case —
a rim bubble's outward face is air, not a film, and von Neumann's law is derived for
bubbles fully surrounded by others.

**S2 — Foam C is flat.** β = −0.0000 [−0.0428, +0.0485] on **310 interior bubbles**, the
best-powered population in the project. Its interval is *narrower than Foam A's MDE*. Foam C
has no ground truth and is guard-rejected, so this is not proof that Foam A's gradient is
artefactual — the detector's neighbour-count error need not be the same in a foam whose
bubbles are 0.57× the radius — but it is a real and uncomfortable contrast: **the same
detector, on a much larger sample, finds nothing.**

**S3 — Foam F.** 23 interior bubbles, β = +1.69 with an interval four units wide. Above the
20-bubble floor by three bubbles, and uninformative. Note it is the only foam whose point
estimate is *positive*.

**S4 — Foam F time × space: REFUSED.** Splitting at the first-third boundary (420 s) leaves
23 interior bubbles early and **18 late**, below the 20-bubble floor. **Power does not allow
the test.** This is the place a wetness-driven spatial effect should have been strongest,
and it cannot be run.

**S5 — short- versus long-lived bubbles.** After removing the radial trend and branch,
long minus short is **−0.0267 [−0.0872, +0.0138], p = 0.365 — no resolved difference.**
Uncontrolled the same comparison gives +0.0527, which is not interpretable: short-lived
bubbles are small, shrinking-branch and rim-heavy. The mentor's question 1 therefore has a
null answer at this power.

**S6 — the ground-truth rim-versus-interior contrast (its own result, hand labels only).**

| population | interior − rim | [bubble bootstrap] | [7-pair block] |
|---|---|---|---|
| **hand labels, all bubbles** | **+0.0779** | [−0.0111, +0.1583] | [−0.0164, +0.1805] |
| hand labels, n < 6 branch only | +0.0502 | [−0.0224, +0.1557] | [−0.0056, +0.1831] |
| hand labels, n > 6 branch only | REFUSED (13 rim bubbles) | | |
| Cellpose, same frames, all bubbles | +0.1995 | **[+0.0951, +0.3113]** | **[+0.0892, +0.4331]** |
| Cellpose, n < 6 branch only | +0.1333 | **[+0.0222, +0.2393]** | **[+0.0444, +0.2889]** |

Component K values (hand labels): **rim +0.322 [+0.294, +0.383], interior +0.400
[+0.342, +0.467]**.

> **The hand labels do NOT resolve a rim-versus-interior difference; Cellpose, on the same
> bubbles in the same frames, does — and roughly doubles it.** That holds with and without
> branch control.

This is the cleanest statement the data support, and its limits are equally clear: it is
**free of the Cellpose error**, but it **cannot separate evaporation from the free
boundary**, it rests on **7 frame pairs**, the "all" row is **not branch-controlled** (the
GT rim is 91% shrinking-branch), and the n > 6 branch is refused for want of rim bubbles.

---

## 5. Downstream changes to published statements

**`docs/wetness_and_k_fragility.md` correction #4, `results_package/tables/K_exclusion_configs.csv`,
`qc/k_robustness/exclusions_raft_edge.csv`** currently report, for Foam A, "interior K
exceeds perimeter K (+0.433 [0.383, 0.478] vs +0.316 [0.283, 0.355])" with non-overlapping
intervals, i.e. as a resolved spatial effect. That number is not withdrawn — it is a
correct pooled fit — but **its reading as a spatial effect is now known to be confounded on
two counts**, and both are measurable:

1. **Branch composition.** The rim is 89% shrinking-branch with ⟨n⟩ = 4.00 against 5.7–6.1
   inside. The same comparison done per bubble and branch-centred gives **+0.0397
   [−0.0166, +0.1471], p = 0.094 — not resolved** (S1).
2. **The detector.** On hand labels the interior-over-rim contrast is **+0.078, not
   resolved**; Cellpose gives **+0.200, resolved** (S6). The detector approximately doubles
   it.

Recommended wording, if the perimeter result is quoted: *"Pooled over measurements, Foam A's
interior K exceeds its rim K. The contrast is not resolved once branch composition is
controlled per bubble, and hand labels on the same frames do not resolve it either, so it
should not be read as a spatial effect."* The **Foam C and Foam F perimeter results were
already withdrawn** and nothing here revives them.

No other published number changes. The pooled K table, the K-by-period result, the sign
change in Foam F and the wetness results are untouched — verified by the Stage-1 guard that
reproduces `K_fits.csv` to 1e-9.

---

## 6. Verdict

Against the four outcomes pre-committed before any of this was run:

> **"Gradient present but no larger than the detector-offset band → report that it cannot
> be distinguished from a measurement artifact."**

That is the outcome.

**In full.** Foam A's interior bubbles show a radial gradient in K that is statistically
resolved (β = −0.278 [−0.437, −0.068], permutation p = 0.007) and comfortably above the
minimum detectable effect (0.081). It is **not** distinguishable from Cellpose's own
position-dependent neighbour-count error, which Stage 2 measured directly against hand
labels at β_det = −0.362 [−0.769, +0.048] — larger than the signal and in the same
direction. Removing that bias leaves **β_corr = +0.084 [−0.341, +0.523]**: consistent with
no gradient, and consistent with a gradient of either sign.

Three independent facts point the same way. Foam C, with 310 interior bubbles and the same
detector, is **flat to within ±0.05**. The hand labels **do not resolve** a rim-versus-
interior contrast that the detector does. And Moran's I says residual spatial structure
survives the fit, so even the measured interval is optimistic.

**What would settle it.** Not more bubbles from this detector — the MDE is already five
times smaller than the artifact. It needs either (a) hand labels on enough consecutive
frame pairs to estimate K per bubble from ground truth directly, which at ~55 measurements
per bubble is far beyond the 7 pairs that exist, or (b) a detector whose `n_sides` error is
demonstrably position-independent, which would have to be shown against hand labels first.
The physically interesting question — whether an evaporation front leaves a radial signature
in K — remains open, and this analysis says how large such a signature would have to be
before this measurement chain could see it: **larger than 0.36 px² s⁻¹ per unit ρ, i.e. a
centre-to-rim change of about 75% of K itself.**

---

## 7. Figures

* `paper_figures/fig6_per_bubble_map.png` — the spatial map, all three foams: bubbles at
  their mean raft-relative positions, coloured by `K_i` on a scale symmetric about each
  foam's pooled K, rim bubbles as squares, the raft edge of a mid-sequence frame dashed.
* `paper_figures/fig7_per_bubble_radial_profile.png` — Foam A's radial profile: interior
  bubbles branch-adjusted, ρ-quintile medians with block-bootstrap intervals, the fitted
  Theil-Sen slope, and **the Stage-2 null band and the measured detector band overlaid**,
  so a reader can see directly that the data do not leave the detector band.

Both are built by `dev/per_bubble_figures.py`, which re-checks the values its title and
caption assert and stops if they have changed.
