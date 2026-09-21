# Pre-registration — is K spatially graded across the raft?

**Written and committed before the Stage-3 analysis was run.** Stages 1 and 2 are complete
and reported (`docs/per_bubble_k_map.md`, commits `2080e6d` and `7c74c07`). This document
fixes the hypothesis, the statistic, the population, the inference and the decision rule.
Anything not written here is exploratory and is labelled as such in the write-up.

---

## 1. Hypothesis

**H1 (two-sided).** Among interior bubbles of Foam A, the per-bubble coarsening coefficient
`K_i` varies systematically with normalised radial position in the raft.

**H0.** It does not: `K_i` is statistically independent of radial position once branch
composition is accounted for.

**The test is two-sided.** I do not know which direction evaporation predicts. Rim bubbles
are drier and may carry a higher surfactant concentration, which could raise or lower the
effective diffusive permeability, and nothing in this project's data settles it.

> **Labelled conjecture, not the hypothesis, and not part of the decision rule.** If
> evaporation drives a gradient at all, an evaporation front advancing inward from the rim
> would make the rim the older, drier, more-coarsened region first, so a *lower* K at the
> rim (β < 0 on the coordinate below) is the more natural expectation. This is recorded so
> it cannot be constructed afterwards. **It carries no weight in the analysis.**

---

## 2. Test statistic

`# DECISION (primary estimator = branch-adjusted Theil-Sen slope).`

    beta  =  TheilSen( rho_i ,  K_i - median(K over i's branch group) )

* `K_i` — the bubble's median of `dA/dt / (n-6)` over `|n-6| >= 1`, at the 30 s horizon
  (Stage 1; identical to the shipped pooled estimator, regrouped).
* `rho_i` — `rho_hull`, median over that bubble's own measurements.
* branch group — `shrink` if the bubble's shrinking-branch fraction `f_i >= 0.5`, else
  `grow`. Stage 1 measured `f_i` to be nearly binary (68% of Foam A bubbles wholly n<6,
  18% wholly n>6, 14% mixed), so group-median centring is the rank-based analogue of a
  linear covariate and assumes no linearity.
* units — px² s⁻¹ per unit `rho`.

**Why Theil-Sen and not least squares.** `K_i` is a median of `y/x` ratios. A least-squares
slope fitted to ratios is leverage-sensitive, which is the exact failure this project
audited in S1 and in `dev/estimator_bench.py` (LS biased by −0.093 with inter-replicate IQR
1.04 under 1.2% contamination). Theil-Sen has a 29% breakdown point. Stage 2 also shows the
choice matters here and not only in principle: under the detector-offset null the WLS
statistic returns **+0.104 [+0.041, +0.161]** while Theil-Sen returns **+0.017 [−0.050,
+0.079]** — i.e. **Theil-Sen is nearly immune to the detector's intercept in the interior,
and LS is not.**

**Why branch-adjusted rather than branch-stratified.** One test, so no multiplicity inside
the primary; and it keeps the 14% of bubbles that sample both branches instead of forcing
them into a group. **The branch-stratified version is computed every time as a mandatory
robustness check** (§6), because Stage 1 showed branch composition is *not monotone* in
position — 89% shrinking at layer 1, 37% at layer 2, back to 59–71% at layers 4–5.

**Secondary statistics, reported always, never substituted for the primary:** the weighted
least-squares slope with `1/sigma_i^2` weights from the within-bubble bootstrap (it uses the
per-bubble uncertainties, which Theil-Sen discards); the unadjusted Theil-Sen slope; and the
Spearman rank correlation of branch-centred `K_i` against `rho`.

---

## 3. Population — fixed before the test

* **Foam A only** (`exp1`, sessions `exp1_run0` + `exp1_run1`) — the only foam with hand
  labels and the only one not guard-rejected.
* **30 s horizon** (h = 1 frame), the project's shortest matched horizon.
* **Interior only: median layer ≥ 2**, which removes the free-boundary confound. Layer is
  the topological index of Stage 1 (layer 1 = touching the raft exterior).
* **`m_usable >= 10`** (Stage 1 `# DECISION`, chosen on precision alone).
* **n = 84 bubbles.** `rho` spans 0.114–0.874. Angular sectors hold 8/8/13/9/11/12/9/14.

This population was fixed in Stage 1 and is not revisited.

---

## 4. Inference — must respect spatial autocorrelation

1. **Angular-sector block bootstrap**, 2,000 replicates, `N_SECTORS = 8` (45°) primary,
   with 4/6/12 reported as sensitivity. `# DECISION`: a radial statistic must not be
   blocked radially — that would remove the contrast being tested — so blocks are angular
   sectors, which keep the full radial range inside each block while breaking the
   correlation between neighbouring bubbles, which is angular at fixed radius. The
   ordinary bubble bootstrap is reported beside it so the cost of respecting space is
   visible.
2. **Permutation test**, 5,000 replicates, shuffling `K_i` **within (angular sector ×
   branch group)** strata. `# DECISION`: this destroys the radius–K relation while
   preserving both the sector-scale spatial structure of the K field and the branch
   composition, so the reference distribution already contains whatever large-scale
   spatial dependence the foam has. Two-sided.
3. **Moran's I** on the residuals of the weighted fit, over a k-nearest-neighbour graph of
   the bubbles' raft-relative mean positions, `K_NN = 6` (roughly a 2D foam's coordination
   number), tested by permuting residuals. Reported as a diagnostic on whether residual
   spatial dependence survives the fit.

---

## 5. Thresholds fixed by Stage 2

All in px² s⁻¹ per unit `rho`, interior population, primary statistic.

| quantity | value |
|---|---|
| pure null band (95%) | **[−0.0553, +0.0587]**, median +0.0010 |
| detector-**intercept** null band (c0 = +0.4211) | [−0.0500, +0.0786], median +0.0171 |
| **MDE at 80% power vs the pure null** | **β = 0.081** (= +0.062 px² s⁻¹ centre-to-rim, **17% of K0**) |
| **MDE at 80% power vs the operative null** | **β = 0.091** (= +0.070 px² s⁻¹, **19% of K0**) |
| **detector band — measured, GT vs Cellpose, primary form, interior** | **β_det = −0.362**, [−0.769, +0.048] bubble, [−0.725, −0.137] pair-block |

**The detector band is the binding constraint, and it is stated here in advance.** Stage 2
found that Cellpose's per-bubble error is position-dependent, that it is a **neighbour-count
error and not an area error** (slope of `n_CP − n_GT` on `rho` = −0.416 [−0.588, −0.255];
slope of the `dA/dt` difference = +0.007 [−0.622, +0.642]), and that the branch adjustment
does not remove it in the interior. Its magnitude, β ≈ −0.36 with an interval reaching
−0.77, is **4 to 9 times the minimum detectable gradient**.

Note that Theil-Sen has already disarmed the *intercept* part of the detector problem
(+0.017, straddling zero). What remains, and what sets the threshold, is the ρ-dependent
`n_sides` error, which no estimator choice can remove.

---

## 6. Decision rule — fixed in advance

Let `beta_obs` be the primary statistic on the real data, `CI` its 95% angular-block
bootstrap interval, `p` its sector×branch permutation p-value.

**A. Is the measured gradient resolved?**
Resolved iff **all** of:
* `CI` excludes 0, **and**
* `p < 0.05` (two-sided), **and**
* `|beta_obs| > 0.0587` (outside the pure null band), **and**
* the branch-**stratified** slopes agree in sign with `beta_obs` in the branch that clears
  the 20-bubble floor, **and**
* the sign is unchanged across `N_SECTORS ∈ {4, 6, 8, 12}` and across the WLS secondary.

Failing any of these → **not resolved**.

**B. Is it distinguishable from the detector artifact?** *(applies only if A is met)*
* `|beta_obs| > 0.769` (the 97.5th percentile magnitude of the detector band) →
  **distinguishable**; report as a finding.
* `0.362 < |beta_obs| <= 0.769` → **borderline**; report as "larger than the detector
  band's point estimate but inside its interval", not as a finding.
* `|beta_obs| <= 0.362` → **indistinguishable from the detector's position-dependent
  neighbour-count error**, and reported as such — *this is the expected outcome and saying
  so in advance is the point of this document.*

**C. Mandatory detector-corrected estimate.** Whatever A and B give, also report
`beta_corr = beta_obs − beta_det` with an interval convolving the two bootstrap
distributions, because `beta_det` is a **bias with a sign**, not merely noise: the detector
biases `beta_obs` downward by ≈ 0.36, so a measured β near zero is consistent with a true
β near +0.36. Carry the caveats that β_det comes from 7 frame pairs of single measurements,
on a GT-layer-defined population, while β_obs uses 99 frames of per-bubble medians.

**D. If not resolved**, report the MDE (β = 0.081, i.e. 17% of K0 centre-to-rim) so the
null is quantified rather than vague.

---

## 7. Secondary analyses — exploratory, pre-specified, corrected for multiplicity

Reported separately, and **never used to revise the primary conclusion**. Benjamini–Hochberg
across the **six** tests below; corrected and uncorrected values both reported.

1. **Rim (layer 1) versus interior in Foam A.** Cannot separate evaporation from
   free-boundary geometry. If the interior gradient is null but the rim differs, the
   parsimonious reading is the free boundary — the law is derived for bubbles fully
   surrounded by others — and that will be stated.
2. **Foam C** — primary test repeated. No ground truth, and the foam is guard-rejected.
3. **Foam F** — primary test repeated. 23 interior bubbles: above the 20-bubble floor, only
   just. Refuse any fit below the floor.
4. **Time × space in Foam F** — whether a spatial pattern differs between its wet early
   period and its drier later periods. Refuse if power does not allow, and say so.
5. **Short- versus long-lived bubbles** (mentor's question 1) — compared within foam,
   controlled for position and branch, since short-lived bubbles are small,
   shrinking-branch and possibly rim-heavy.
6. **The ground-truth rim-versus-interior contrast** (hand labels only). This is its own
   result and is labelled as one: it is **free of the Cellpose error** measured in Stage 2,
   but it **cannot separate evaporation from the free boundary**, it rests on **7 frame
   pairs**, and it is **not branch-controlled** unless explicitly stated (the GT rim is 91%
   shrinking-branch). Both interval schemes; the 20-bubble floor applies to each branch.

---

## 8. Outputs fixed in advance

A spatial map per foam (bubbles at mean positions, coloured by `K_i`, raft edge drawn,
colour scale symmetric about the pooled K); a radial profile of `K_i` in `rho` bins with
block-bootstrap intervals, rim and interior distinguished, and the Stage-2 null band and
detector band overlaid; the write-up in `docs/per_bubble_k_map.md`.

`# DECISION (bins)`: equal-count quintiles of `rho` within the plotted population, so no
bin is empty and no bin edge is chosen after seeing K. Bin membership is fixed by `rho`
alone. Bins are for display and for the profile figure; **the primary test is not binned.**

---

## 9. What had already been seen when this was written

Full disclosure, because a pre-registration is worth only what it discloses.

1. **An uncontrolled median `K_i` by layer for Foam A** (layers 1→4: 0.317, 0.375, 0.500,
   0.400), printed while assembling Stage 1 §1.7 and disclosed there. It controls for
   nothing — not branch, not size, not the free boundary, not the detector — and it is not
   a result. It suggests β < 0 on the `rho` coordinate. **The statistic, the covariate, the
   blocking scheme, the permutation scheme and the population were already fixed in
   `dev/per_bubble_spatial.py` before that number existed**; the only element decided
   afterwards is the Theil-Sen primary, which was **directed by the mentor** on the general
   grounds that `y/x` ratios make least squares leverage-prone, not on any result.
2. **All of Stage 2**, which is synthetic or ground-truth-based and contains no
   relationship between real Cellpose `K_i` and position.
3. **The ground-truth rim/interior point estimates** (+0.322 rim, +0.400 interior; earlier
   quoted as +0.333/+0.427 on the 320 genuinely-paired subset rather than the full GT
   measurement set). Their intervals are computed as secondary 7 above.
4. **No test of real Cellpose `K_i` against position has been run in any form.** Stage 3 is
   the first.

---

*Pre-registration complete. Stage 3 may now be run.*
