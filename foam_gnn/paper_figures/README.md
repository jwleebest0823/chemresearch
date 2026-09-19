# Figures for the revised paper

The paper is rebuilt around one finding: **K is not a per-foam constant — it varies
systematically over a foam's lifetime**, and in Foam F it changes sign between a wet early
period and a drier later one. Five main figures carry that argument; four supplementary
figures hold the evidence behind specific measurement choices.

Rebuild with `python dev/paper_figures.py`. Figures 1–5 and S4 read every value from a
table, re-check each value the figure or caption asserts against that table, and stop
(fail loud) if a claim is no longer true. S1 and S2 are drawn by `build_results_package.py`
and copied here; S3 is computed from images and label maps. **`dev/` and `qc/` are
gitignored**, so the drivers and their intermediate tables are local; every table a figure
or caption reads is copied into `results_package/tables/` (committed) by
`build_results_package.py`, which in turn copies these figures into
`results_package/figures/`, so the paper and the package cannot disagree. Build order:
`build_results_package.py` (draws S1/S2 sources), `dev/paper_figures.py`, then
`build_results_package.py` again.

**Renumbering (Sept. 18).** The old `figA` K by period → **Figure 1**; `figD` n₀
zero-crossing → **Figure 2**; `figC` fragility → **Figure 3** (revised); `figB` wetness →
**Figure 4** (revised); the detector calibration, formerly results-package `fig4` →
**Figure 5**. The leverage figure stays **S1**; count curves → **S2**; the junction and
circularity verification figures are new, as **S3** and **S4**. The `figA`–`figD` files are
deleted by the script.

| paper | file | results package copy |
|---|---|---|
| Figure 1 | `fig1_K_by_period.png` | `figures/fig10_K_by_period.png` |
| Figure 2 | `fig2_n0_zero_crossing.png` | `figures/fig12_n0_zero_crossing.png` |
| Figure 3 | `fig3_fragility.png` | `figures/fig11_fragility.png` |
| Figure 4 | `fig4_wetness.png` | `figures/fig8_foam_wetness.png` |
| Figure 5 | `fig5_detector_calibration.png` | `figures/fig4_n_calibration.png` |
| S1 | `figS1_leverage.png` | `figures/fig3_leverage.png` (source) |
| S2 | `figS2_count_curves.png` | `figures/fig2_count_curves.png` (source) |
| S3 | `figS3_junction_measurement.png` | `figures/fig13_junction_measurement.png` |
| S4 | `figS4_circularity_measurement.png` | `figures/fig14_circularity_measurement.png` |

**Second review (same day).** An adversarial review of the rebuilt figures against their
tables found and corrected, among other things: the ground-truth branch asymmetry in
Figure 2 is not resolved from 1 (it was called "genuine"); the size-cut sentence in Figure 3
("not measurement error") overstated the evidence; Figure 4's "only during its first ten
minutes" contradicted its own caption; Figure 5 did not disclose that the hand labels were
corrected from a watershed pre-seed; S1's "wrong sign" was a failed sign test; and S2's
rank correlations did not match the plotted series. Each is described under its figure.

---

## Main figures

### Figure 1 — `fig1_K_by_period.png` · the headline

K for the first, middle and last third of each foam's sequence (30 s horizon), with
cluster-bootstrap intervals and the tracked-bubble count in every cell.

| foam | first third | middle third | last third | |
|---|---|---|---|---|
| A | +0.300 [0.283, 0.333] · 105 bub | +0.425 [0.384, 0.455] · 114 | +0.450 [0.367, 0.550] · 43 | rises 1.50× |
| C | +0.200 [0.183, 0.233] · 466 | +0.197 [0.178, 0.200] · 313 | +0.133 [0.125, 0.156] · 245 | falls 1.50× |
| **F** | **−0.300** [−0.608, −0.033] · 56 | **+1.567** [1.134, 1.916] · 34 | **+1.633** [1.134, 2.433] · 23 | **changes sign** |

*(The Foam A middle-third interval was previously printed as [0.383, 0.467], a value from a
different bootstrap run.)* Two panels: all three foams, and Foams A and C on an expanded
scale. **The axis is elapsed time within the foam's life, not the prediction horizon.** The
caption states that the movement is resolved because the range across periods clears the
noise floor of random bubble subsets in every foam (Figure 3) — *not*, as first written,
because each interval excludes zero — and that Foam F's middle and last thirds are not
distinguishable. A guard fails the build if the period bars stop clearing their floors.

Source: `qc/k_robustness/task2_K_by_period.csv` → `results_package/tables/K_by_period.csv`.

### Figure 2 — `fig2_n0_zero_crossing.png`

The hand labels confirm von Neumann's zero-crossing and show that the detector's offset is
a detection artifact.

| | slope | intercept | **n₀** | ratio of K, growing ÷ shrinking side |
|---|---|---|---|---|
| **hand-labelled truth** | +0.394 | −0.003 | **6.01** [5.76, 6.31] | 1.24× [0.95, 1.60]; pair-block [0.95, 1.64] |
| Cellpose | +0.530 | +0.421 | **5.21** [5.05, 5.37] | 2.42× [1.95, 3.13]; pair-block [1.67, 4.60] |

**Corrected wording.** The right panel was titled "the detector roughly DOUBLES a branch
asymmetry that genuinely exists". The hand-labelled ratio's interval includes 1 under both
interval schemes, so the asymmetry is not established; the panel now reads "the detector
widens the gap between the sides", with both ratios and their intervals, and a guard fails
if that stops being true. The suptitle no longer says the offset is invisible to a
detector-only analysis — a detector-only fit shows the offset; the hand labels show it is a
detection artifact. **Only the 30 s horizon is supported** by the seven widely spaced pairs
of consecutive labelled frames.

Source: `qc/gt_k/n0_and_branch.csv` (now with ratio intervals), `n0_binned_medians.csv`;
driver `dev/gt_n0_analysis.py`.

### Figure 3 — `fig3_fragility.png` · revised

How far K moves, as a fraction of its own size, under **exactly three perturbations, for
all three foams**, with 95% bubble-bootstrap intervals and a noise floor per bar (the 95th
percentile of the same statistic on random bubble subsets of the same sizes; bars within
it are hatched). The axis is linear below 1 and logarithmic above, and the caption says so.

| foam | period of the foam's life | minimum bubble-size cut | perimeter bubbles excluded |
|---|---|---|---|
| A (156 bubbles) | 0.41 [0.25, 0.67] | 0.14 [0.05, 0.25] | 0.18 [0.07, 0.27] |
| C (466) | 0.38 [0.24, 0.54] | **0.50** [0.37, 0.60] | 0.13 [0.08, 0.20] |
| F (56) | **3.22** [2.32, 5.04] | 0.57 [0.16, 1.37] | 0.03 [0.00, 0.70] — within noise |

`# DECISION` — **perimeter = centroid within 2 equivalent radii of the raft edge**, the
convex hull of the detected bubbles. The previous rule measured distance to the foam
outline, which leaks off the raft, and missed 26% (A), 59% (C) and 38% (F) of genuine rim
bubbles; every result that used it is withdrawn (`docs/wetness_and_k_fragility.md`,
§3(b)).

**Estimator stability, in the caption only:** a random 20% bubble drop moves K by 0.09 of
its value in Foams A and C, and the 30 → 600 s prediction horizon by 0.02 (A) and 0.09 (C);
for pooled Foam F these are **0.41 and 0.37**.

**Size cut — corrected.** The caption first said the size bar "is not measurement error"
because hand-labelled and detected K agree (+0.366 and +0.333). That was too strong: equal
pooled K does not show the size dependence is detector-free, and the evidence is Foam A
only. It now says: on Foam A's hand-labelled frames the dependence is **present in the hand
labels too** (relative range 0.15 [0.06, 0.31]; K rises from +0.37 to +0.42 by 400 px² and
levels off), so it is not only detection error; the detected sweep on the same frames
moves more (0.25 [0.03, 0.62]) without levelling off, consistent with the detector's wider
branch gap (Figure 2), but the two are not resolved from each other. Raising the cut
removes bubbles with few neighbours (Spearman ρ(area, n) = +0.73 [0.68, 0.77] in the hand
labels; none of the smallest third has more than six neighbours). Foams C and F, whose
size bars are largest, cannot be checked.

**How to read Foam F — and where the reading stops.** Not "von Neumann works for A and C
but fails for F". Foam F's **period bar** (3.22, against 0.41 and 0.38) is the signature of
**two regimes averaged into one number**: a first third containing the wet phase, with
negative K (Figures 1, 4), and a drier remainder with K ≈ +1.6. The pooled +0.60 describes
neither. What is consistent with this reading: restricted to the drier window (34
bubbles), Foam F's K barely changes with prediction horizon (+1.57, +1.59, +1.68 at 30, 150
and 600 s), and longer horizons draw more of their samples from the first third (52% at
30 s, 54% at 150 s, 64% at 600 s). What limits it, all stated in the caption: the horizon
range drops 0.37 [0.07, 0.81] → 0.07 [0.02, 0.43], **overlapping, so not resolved**; the
same restriction moves Foam A's range the other way (0.02 → 0.09); restricting the window
brings the size bar within noise in **all three** foams, so that is not specific to Foam F;
and excluding perimeter bubbles gives **no resolved change** in Foam F (0.03 [0.00, 0.70]).
Foam F's size bar (0.57) is about the same as Foam C's (0.50), so only its period bar is
distinctive.

Sources: `qc/k_robustness/fragility_v2.csv`, `fragility_v2_estimator_within_regime.csv`,
`regime_share_by_horizon.csv`, `task4_fragility.csv`, `exclusions_raft_edge.csv`,
`qc/gt_k/gt_min_area_sweep.csv`, `gt_min_area_sweep_range.csv`,
`gt_branch_mixture_facts.csv`. Drivers: `dev/fragility_v2.py`,
`dev/fragility_v2_estimator.py`, `dev/regime_share_by_horizon.py`,
`dev/raft_edge_distance.py`, `dev/gt_min_area_sweep.py`.

### Figure 4 — `fig4_wetness.png` · revised

Is Foam C wet like F or dry like A? **Intermediate-to-dry. Foam F is the wettest foam, most
of all in its first ten minutes.** All measures inside the raft (the convex hull of the
detected bubbles), 20 frames per foam, medians with 95% bootstrap intervals over frames.

| panel | measure | Foam A | Foam C | Foam F |
|---|---|---|---|---|
| (a) primary | junction size: inscribed radius at ≥3-bubble junctions ÷ local bubble radius | 0.134 [0.129, 0.137] | 0.142 [0.139, 0.152] | 0.187 [0.175, 0.202] |
| | same, 95th percentile | 0.19 [0.17, 0.21] | 0.26 [0.25, 0.28] | 0.38 [0.29, 0.66] |
| (b) secondary | liquid fraction from image brightness (pixels classified by brightness alone; the detected bubbles only define the raft interior) | 0.221 [0.212, 0.229] | 0.253 [0.239, 0.273] | 0.327 [0.302, 0.375] |

**(c)** Foam F's junction size over time: 0.77 of a bubble radius at the first frame, about
0.2 within ten minutes, then about 0.18 (≈1.3× Foam A's). The shaded band is Foam F's first
third, where its K is negative (Figure 1).

**Corrected in the second review.** The suptitle said Foam F is wetter "only during its
first ten minutes" and panel (c) that it "then stays near Foams A and C"; after ten minutes
it stays about 1.3× Foam A on junction size and on brightness, so both now say "most of
all" / "about 1.3 times Foam A's". The caption now also states: Foam F's earliest junction
values are **upper bounds** (some junction discs enclose small bubbles the detector missed,
S3), and the brightness fraction falls over the same ten minutes (0.53 → 0.38); **Foam C
also starts wet** (0.43 at its first frame) while its first-third K is positive (+0.20), so
an early wet phase does not by itself produce a negative K; and the circularity ordering is
described by size ("finest Foam C", "coarsest Foam F"), not as "dry"/"wet".

**Removed:** film half-width and unassigned fraction (in Foam F they cannot separate
liquid from missed bubbles) and circularity (the pixel-counting perimeter scores smaller
objects as rounder; with a scale-free perimeter Foams A and F agree, S4).

**Withdrawn from the previous version (`figB`):** junction half-width A 1.04 / C 1.14 /
F 5.68 and "five times"; the drying trend 6.10 → 3.75; "Foam C is dry on every measure";
the Laplace-pressure explanation of circularity.

Sources: `qc/verify_junction/raft_core_measures_per_frame.csv`, `raft_core_summary.csv`,
`qc/k_robustness/task2_K_by_period.csv`. Driver: `dev/verify_wetness_raft.py`.

### Figure 5 — `fig5_detector_calibration.png`

All three detectors scored on the **same 14 hand-labelled Foam A frames** with the same
neighbour-counting code, with the raft edge taken from the hand-labelled bubbles. Means over
frames with 95% bootstrap intervals over frames; parentheses are paired differences from
the hand labels.

| | ⟨n⟩ all | ⟨n⟩ interior | ⟨n⟩ rim | raft interior unassigned |
|---|---|---|---|---|
| **hand labels** | 5.08 [4.99, 5.18] | 5.79 [5.73, 5.84] | 4.05 [3.99, 4.11] | 11.4% [10.2, 12.5] |
| Cellpose | 5.11 (+0.03 [0.02, 0.05]) | 5.84 (+0.05 [0.02, 0.10]) | 4.04 (−0.01 [−0.04, 0.02]) | 7.2% (−4.2 [−5.3, −3.2]) |
| watershed | 5.68 (+0.60 [0.52, 0.69]) | 5.71 (−0.08 [−0.14, −0.02]) | 5.68 (**+1.62** [1.54, 1.70]) | 11.0% (−0.4 [−0.7, −0.1]) |

Cellpose is within 0.05 of the hand labels on every group. **The watershed's +0.60 excess is
all at the rim.** Over the whole foam outline the watershed leaves 10.9% unassigned against
the hand labels' 25.3%: it assigns the band between the outermost bubbles and the outline.

**Shared origin — disclosed after the second review.** The hand labels were made by
correcting an automatic pre-seed from this same propagating watershed
(`groundtruth/manifest.csv`), and **87% of hand-labelled bubbles [84%, 89%] are
pixel-identical to a watershed region**. Agreement between the watershed and the hand labels
is therefore partly built in — including the matching unassigned share in panel (b) — and
Cellpose's lower value there may reflect a boundary convention the hand labels inherited.
The rim excess is not built in: rim bubbles whose outlines are pixel-identical in both maps
still have **0.76 [0.69, 0.83] more neighbours** in the watershed, so the excess comes from
their surroundings (the watershed keeps 1.4 [1.1, 1.9] regions per frame that match no
hand-labelled bubble and lie mostly outside the hand-labelled raft). Cellpose shares no
origin with the hand labels, which makes its agreement the stronger check.

`# DECISION` — (i) **the watershed row is the shipped propagating pipeline**, run over both
of Foam A's runs and evaluated at the 14 labelled frames. A per-frame watershed is not a
faithful stand-in: it assigns essentially every pixel (0.0% unassigned); it is kept in the
tables for reference (+0.44 over all bubbles, +1.26 at the rim). (ii) **Interior = the whole
bubble more than one median hand-labelled radius inside the hand-labelled hull**, the same
pixels for every detector — a different rule from Figure 3's perimeter rule, chosen so all
three detectors are scored on identical pixels. With it, 38% of hand-labelled bubbles are
rim bubbles.

**What this replaces:** the previous calibration (5.08 / 5.66 / 25.3%; watershed 5.67 /
5.71 / 12.4%) measured "interior" and "unlabelled" from the foam outline, and its watershed
row came from a different set of frames. The hand-label and Cellpose all-bubble values
reproduce exactly; the watershed's moves from 5.67 to 5.68 on the common frames. "A quarter
of the foam interior is not bubble" and "the watershed over-counts because it leaves the
least space between bubbles" are withdrawn.

Sources: `qc/detector_calibration/summary.csv`, `paired_vs_gt.csv`, `per_frame.csv`,
`gt_vs_preseed_summary.csv`, `rim_identical_degrees_summary.csv`. Drivers:
`dev/watershed_propagated_gt_frames.py`, `dev/detector_calibration_v2.py`,
`dev/gt_preseed_overlap.py`, `dev/rim_identical_degrees.py`.

---

## Supplementary figures

### S1 — `figS1_leverage.png`

Foam A, 7106 measurements from the watershed pipeline's trusted set (a detector since
replaced by Cellpose), 30 s horizon: 1.2% of measurements carry 48% of the least-squares fit
weight and pull K from about +0.34 to +0.14, with an interval spanning zero. **Corrected:**
the title said least squares "gave the wrong sign"; it failed the sign test, and every
stratum's own K is positive (+0.34, +0.22, +0.06, +0.05). This is why the robust estimator
ships. Figure 3 supersedes it as a main figure; it is kept because
`results_package/SUMMARY.md` §2 cites it as one of the five measurement artifacts. Source:
`results_package/figures/fig3_leverage.png`, `tables/leverage_strata.csv`.

### S2 — `figS2_count_curves.png`

Bubble count against time. Left: the propagating watershed's region count on Foam C rises
(Spearman ρ = +0.87), which a coarsening foam cannot do. Right: Cellpose counts on the three
foams fall monotonically (ρ = −0.987 to −0.9993 for the series drawn). **Corrected:** the
titles previously gave +0.98 and "−0.995 … −0.9993", which did not match the plotted
series; ρ is now computed from the drawn data (`results_package/tables/count_curve_spearman.csv`).
*(An earlier version of this README said the right panel "restates what Figure 5
establishes"; it does not — Figure 5 is a neighbour-count calibration.)*

### S3 — `figS3_junction_measurement.png`

Why the published junction statistic was wrong. On a Foam F frame and a Foam A frame, the
pixels that set the published 95th percentile all lie outside the raft — on the margin
between the outermost bubbles and the foam outline and, in Foam F, on empty plate where the
outline has leaked. Beside each image, the corrected measurement at actual junctions: the
old statistic reads 6.10 bubble radii in Foam F frame 0, where the median junction is 0.77,
and 0.94 in Foam A frame 36, where it is 0.14. In Foam F's first frames the margin also
holds small bubbles the detector missed, and some junction discs enclose them, so its
earliest junction sizes are upper bounds. Source: `dev/verify_wetness_raft.py`; caption
values are computed in code.

### S4 — `figS4_circularity_measurement.png`

Circularity of ideal circles and hexagons against radius under the pixel-counting
perimeter (which scores smaller objects as rounder: an ideal circle reads 0.953 at 15 px
and 0.920 at 40 px) and under a scale-free (Crofton) perimeter (within 2% of 1 at every
radius from 6 to 80 px), with the per-foam medians under both. Crofton medians: A 0.978
[0.977, 0.979], C 0.984 [0.982, 0.986], F 0.975 [0.969, 0.980]. Sources:
`qc/verify_circularity/scalefree_calibration.csv`, `scalefree_medians.csv`; driver
`dev/circularity_scalefree.py`.

---

## Supplementary note (no figure) — neighbour swaps (T1)

Swaps were tested as a second line of evidence for the wet-to-dry transition and do **not**
support a figure:

* The shipped detector, re-run with the adjacency fix, finds **A 22 (hand-verified, 0 false
  positives), C 113, F 3**; a guard requires Foam A's 22 to reproduce exactly.
* **Foam A density caveat.** Foam A's early concentration (17 → 3 swaps, first to last
  third; raw rate ratio 5.84×, p = 0.001) **does not survive normalisation by exposure** —
  per available contact the ratio is **2.15×, p = 0.32, 95% CI [0.62, 11.4]**. That is no
  evidence of a decline, not evidence of no decline: with 20 events the test could only
  resolve a ratio of about 7 or more. "Swaps concentrate in the dense early foam" is true
  of counts, not of a rate.
* Foam C's per-contact decline is resolved (2.29×, p = 0.001) but **none of its 113 events
  has been checked by eye**, and it rests on a tracker that creates many spurious new
  identities on Foam C.
* Foam F's 3 swaps (1 / 0 / 2 across its thirds) cannot test the transition.
* Hand-checking the cross-foam events would mean scoring **116 events (113 C + 3 F)**; not
  done.

Sources: `results_package/tables/t1_first_vs_last_third.csv`, `t1_rates_by_period.csv`;
drivers `dev/t1_crossfoam.py`, `dev/t1_rates.py`; full account in
`docs/verification_wetness_t1.md`, Task 5.

---

## Standing caveat

Foam C's only hand labels are two frames made by deleting regions from a detector's output
(they can measure precision but not missed bubbles), and Foam F has none, so their
detection accuracy is unvalidated and every value involving them inherits that. Foam A's
detector is validated against 14 hand-labelled frames (Cellpose micro-pooled F1 0.966),
which were themselves corrected from a watershed pre-seed (Figure 5). K intervals are
cluster bootstraps resampling whole bubbles (1000 replicates, 95% percentile); per-frame
measures (wetness, circularity, detector calibration) bootstrap over frames, because bubbles
within a frame are not independent; swap rates use exact Poisson intervals. Horizons are
stated in seconds throughout; frame counts are never used as a time unit.
