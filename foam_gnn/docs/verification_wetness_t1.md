# Verification before revision: circularity, junction width, the foam mask, and T1 rates

> **Status (2026-09-18, later the same day): the corrections below were approved and
> APPLIED.** All three proposals were approved as written — the wetness figure (corrected
> junction primary, brightness liquid fraction secondary, drying trend against the
> negative-K window; film width, unlabelled fraction and circularity dropped), the
> raft-edge perimeter definition, and a supplementary note (not a figure) for T1 with the
> Foam A density caveat. Applied in: `paper_figures/` (Figures 3–5 and S3–S4 rebuilt; see
> its README), `results_package/SUMMARY.md` §3, §5, §7 and the T1 addendum,
> `results_package/METHODS_BRIEF.md`, `docs/wetness_and_k_fragility.md`,
> `docs/cellpose_replication_v2.md`, `docs/tiling_gap_investigation.md`,
> `docs/f_sampling_interval_control.md`, `docs/exp10_replication_attempt.md`,
> `results_package_extra/T1_ADDENDUM.md`, and the foam-mask border warning in
> `src/foam_gnn/segmentation.py`. Withdrawn claims were left visible and marked, not
> replaced. The detector calibration was also re-measured on identical frames with the
> raft edge (paper Figure 5), which withdrew two further statements: "a quarter of the
> foam interior is not bubble" and "the watershed over-counts because it leaves the least
> space between bubbles".
>
> **A second adversarial review** of the rebuilt figures against their tables (4 reviewers,
> each finding checked by an independent skeptic; 61 of 81 findings confirmed) led to
> further corrections, all marked where they occur: the hand-labelled branch asymmetry
> (1.24×) is not resolved from 1; "the size cut is not measurement error" is narrowed to
> "present in the hand labels too"; the hand labels were corrected from a watershed
> pre-seed (87% of bubbles pixel-identical), now disclosed in Figure 5; least squares
> failed the sign test rather than flipping the sign (S1); the count-curve rank
> correlations did not match the plotted series (S2); Foam F's within-window horizon drop
> is not resolved; its perimeter result is "no resolved effect", not "no effect"; and
> Foam C, which also starts wet, keeps a positive first-third K. See
> `paper_figures/README.md` and `results_package/SUMMARY.md`.

Checkpoint document. Tasks 2 and 3 were verification tasks that could invalidate published
claims; **both did**. At the time of writing nothing published had been changed: no figure
regenerated, no caption or summary edited. This records the evidence and the corrections
proposed, for review before the wetness figure and the fragility figure were rebuilt.

Every verdict below was independently re-derived by an adversarial reviewer using a
different method from the original analysis, plus a completeness critic (six reviewers;
notes in `qc/review/`). None refuted a verdict. Several corrected sub-claims, and those
corrections are folded in here.

---

## Task 2 — circularity: the published explanation is wrong

**Published** (wetness figure caption, `docs/wetness_and_k_fragility.md`,
`results_package/SUMMARY.md`): circularity `4πA/P²` "failed as a wetness proxy and pointed
the wrong way" (A 0.905, C 0.921, F 0.890), "because bubble size confounds it — small
bubbles have high Laplace pressure and stay round".

**Verdict: the size confound is real, but it is a pixel-grid artifact of the perimeter
estimator, not Laplace pressure. With a scale-free estimator, Foam F is exactly as circular
as Foam A. The "pointed the wrong way" result is itself mostly this artifact.**

1. **The estimator is not scale-free.** `skimage.measure.regionprops(...).perimeter` scores
   an ideal rasterised circle 0.974 at radius 10 px, 0.953 at 15, 0.928 at 30, 0.920 at 40
   and 0.908 at 80; a regular hexagon (true 0.907) scores 0.86 at 15 px and 0.83 at 60.
   Foam C's bubbles are the smallest (median equivalent radius ~17 px), F's the largest
   (~33 px), so C reads roundest whatever its shape. → `qc/verify_circularity/fig_calibration_and_size.png`
2. **Removing the bias removes most of the gap.** Dividing each bubble's score by that of
   an ideal circle of the same radius shrinks C − F from +0.031 to +0.009 (≈ 70–77%).
   Independently, two scale-free estimators need no correction at all: the Crofton
   perimeter scores ideal circles ~~1.000 ± 0.002~~ within 2% of 1 at every radius from 6
   to 80 px, and on real bubbles gives **A 0.978, C 0.984, F 0.975**
   (`qc/verify_circularity/scalefree_medians.csv`; the reviewer's subsample gave 0.978 /
   0.985 / 0.978 — corrected 2026-09-18); a marching-squares contour gives the same C − F
   gap (+0.007).
3. **The supervisor's roughness hypothesis is not supported.** At matched size (radius
   24–34 px) Foam F's outlines are no rougher than C's: solidity is equal or higher in F,
   high-frequency boundary energy (Fourier modes ≥ 9) is C 0.0089 vs F 0.0097 (not
   significant), local contour noise is 0.28 px in both, and smoothing or convex hulls do
   not reverse the ordering. What little residual difference remains is in low-order modes
   2–8: F's bubbles are slightly more lobed, not jagged.
4. **What the masks cover** (correcting the analysis's first wording). The masks exclude
   the films and interstitial spaces between bubbles but are not interiors-only: the
   darkest boundary band lies 2–3 px *inside* the mask edge in A and C, and 5–6 px inside in
   F. In F the mask edge sits on a flat, gradient-free plateau within a broad, blurred band,
   so its position is poorly constrained by the image. → `qc/verify_circularity/fig_matched_outlines_C_vs_F.png`

**Proposed caption text:** *Bubble circularity is not shown. The pixel-counting perimeter
estimator scores smaller objects as rounder — an ideal circle reads 0.953 at 15 px radius
and 0.920 at 40 px — which by itself produced the apparent ordering (finest Foam C
roundest, coarsest Foam F least round). With a scale-free perimeter the three foams agree to
within 0.01 and Foams A and F are statistically indistinguishable (0.978 and 0.975,
overlapping intervals), so circularity carries no usable wetness signal here.*

---

## Task 3 — "junction half-width" does not measure junctions

**Published** (wetness figure primary panel): junction half-width ÷ median bubble radius =
A 1.04, C 1.14, **F 5.68**; Foam F "drying 6.10 → 3.75, still 3.6× above Foam A".

**Verdict: inflated and mislabelled. The number is set by the raft margin and by places
where the foam mask has leaked onto empty plate. Measured at actual junctions, Foam F's are
about 1.4× Foam A's, not 5×.**

**What the statistic is.** The 95th percentile, over *every* foam-mask pixel carrying no
bubble label, of the distance to the nearest detected bubble, divided by the frame's median
bubble radius. Nothing in it identifies a junction.

**Where its tail sits.** Across 20 sampled frames per foam, **none** of the pixels above the
95th percentile lies inside the convex hull of the detected bubbles, in any foam, in any
checked frame. They sit in the band between the outermost bubbles and the foam-mask edge,
and — for Foam F — in regions where the mask has leaked off the raft onto the plate. On
Foam F frame 0 the 95th percentile is 154 px, and the single deepest unlabelled in-mask
point is **378 px** from any bubble, at the image's top-right corner pixel, on featureless
plate. → `qc/verify_junction/fig_junction_overlay.png`, `fig_foamF_f000_crops.png`

**The foam mask leaks.** 25% of Foam F's foam mask lies outside the bubble hull (A 11%,
C 8%). Foam F's raft is a complete disc wholly inside the field of view — the bubble hull
touches the image border in 0 of 20 frames — while its mask touches 23.6% of the border in
every frame. **So the published statement that Foam F's "foam extends past the field of
view" is wrong: the raft is fully in view and the mask leaks.**

**The corrected measure.** A junction is a point where three or more bubbles meet — a
Voronoi vertex of the detected bubbles — that lies inside the raft core *and* inside the
triangle of the bubbles forming it; its size is its inscribed radius divided by the mean
radius of those bubbles. Median across 20 frames, bootstrap over frames:

| | Foam A | Foam C | Foam F |
|---|---|---|---|
| **published** "junction half-width" ÷ frame radius | 1.04 | 1.14 | **5.68** |
| **corrected** junction inscribed radius ÷ local radius, median | **0.134** [0.129, 0.137] | **0.142** [0.139, 0.152] | **0.187** [0.175, 0.202] |
| corrected, 95th percentile | 0.188 | 0.262 | 0.382 |
| corrected, median ÷ frame radius | 0.150 | 0.191 | 0.256 |

**F ÷ A is 1.4× by the median and 1.7–2.0× by the 95th percentile or frame radius — never
5×.** The ordering A ≤ C < F is robust to every choice. But Foam C sits with A only on the
median (C ÷ A = 1.06); by the 95th percentile it is intermediate (1.3–1.5). Foam A's median
junction is 4.5 px, at pixel resolution, so the A-versus-C comparison is resolution-limited.
The geometric test rejects under 2% of candidate vertices in A and C; in Foam F the
rejected ones are exactly the spurious vertices inside one large bubble the detector missed.

**Foam F's drying trend, corrected:** 0.77 at 0 min → 0.44 at 6 min → 0.21 by ~10 min, then
a plateau at 0.17–0.19 for the remaining 27 minutes. **The wet phase is confined to the
first ~10 minutes — the same window as Foam F's negative-K first third (0–12.3 min).** Foam C
also starts wet (0.43 at frame 0) and settles quickly. Foam F's plateau sits ~1.3× above
Foam A, so "F never reaches A's morphology" survives only in that weak form; "3.6× above A"
does not.

**Two caveats on the corrected measure.** In Foam F's earliest frames a few small bubbles
the detector missed sit inside the liquid, so the early value may be modestly inflated —
but they cover only 1–3% of the unlabelled raft core, and junctions containing none still
have median 0.74, so most of the early signal looks like real liquid.

**The other label-based wetness panels.** Film half-width and unlabelled fraction were
computed over the same leaky mask. Restricted to the raft core: unlabelled fraction A 0.070,
C 0.090, **F 0.269** (published 0.474); film half-width ÷ radius A 0.066, C 0.075, **F 0.30**
(published 0.668). In late Foam F, film half-width *rises* (0.44 → ~0.6), but this is one
large bubble the detector missed in the upper right of the raft — 3.9 to 7.6 bubble-areas in
size and holding over 90% of the thick-film pixels; counting it as a bubble returns
0.08–0.09, comparable to A. These two measures cannot separate liquid from undetected gas
in Foam F and should not be used as wetness measures there.

**The one published wetness number that survives unchanged:** the intensity-derived liquid
fraction (uses no bubble outlines) — A 0.221, C 0.253, F 0.327 on the raft core against
0.226 / 0.253 / 0.323 published, because the leaked region is bright plate.

---

## Consequence found in passing — the perimeter rule is broken for Foams C and F

**Blocking for the fragility figure.** The perimeter rule used in the exclusion tests calls
a bubble perimeter when its centroid is within 2 equivalent radii of the foam-mask edge.
Because the mask extends beyond the bubbles, the rule misses genuine rim bubbles. Against the
raft's own edge (bubble hull), on 20 frames per foam (`dev/verify_perimeter_rule.py`):

| | perimeter by mask edge | by raft edge | true rim bubbles called interior | reverse error |
|---|---|---|---|---|
| A | 26.0% | 35.7% | **27%** | 0% |
| C | 9.2% | 25.7% | **64%** | 0% |
| F | 27.3% | 50.2% | **46%** | 0% |

The error runs one way only. **The published caveat had the direction wrong**: the mask does
not add picture-edge bubbles to the perimeter set; it moves most genuine rim bubbles into the
interior set. The published Foam F result that "perimeter bubbles carry twice the interior's
K" and the Foam C null are therefore uninterpretable and should be withdrawn, not caveated.
The Foam A result is mildly affected. `distance_to_evap_edge` is also an input feature to the
learned models, and it is corrupted for Foams C and F in the same way.

---

## Task 5 — T1 swaps as a second line of evidence

**Step 1.** T1 had never been run on Foams C and F with the current detector: the stored
counts (C 1, F 0) predate the bridged-adjacency fix that took Foam A from 1 swap to 22. The
re-run was inexpensive (~30 min) and uses only the shipped tracker; a guard requires Foam A
to reproduce its hand-verified 17 + 5 = 22 exactly, and it does. **Counts: A 22, C 113,
F 3.**

**Step 2.** Foam F has **3 swaps** in 37.5 minutes (1 / 0 / 2 across the three periods).
That cannot test any relationship with the wet-to-dry transition or the K sign change.

**Step 3 — density normalisation.** Exposure is counted per bubble and per *available
contact*: the detector's own search set of shared films between bubbles that persist
(`dev/t1_crossfoam.py`, which aborts if its adjacency does not reproduce the tracker's
events).

| | swaps, first → last third | raw rate ratio | per bubble | per available contact |
|---|---|---|---|---|
| **A** (22, hand-verified) | 17 → 3 | **5.84**, p = 0.0013 | 2.38, p = 0.22 | **2.15, p = 0.32**, 95% CI [0.62, 11.4] |
| **C** (113, not verified) | 67 → 18 | 3.95, p < 10⁻⁷ | 2.21, p = 0.002 | **2.29, p = 0.001** |
| F (3, not verified) | 1 → 2 | 0.53 | 0.24 | 0.25, p = 0.26 |

**Foam A's early concentration does not survive density normalisation — as a resolved
effect.** This is *no evidence of a rate decline*, not evidence of no decline: the
per-contact point estimate (2.15×) is almost identical to Foam C's resolved 2.29×, but with
20 events in the compared thirds the test needed an observed ratio of at least 7.2 to reach
significance and had 80% power only at a true ratio of ~8.8. The per-contact pattern is
also not monotone (middle third lowest).

Foam C's decline does survive normalisation. Its main confound, identity churn, is five
times higher early and lowers early detection efficiency (all four bubbles must keep their
identities: 0.83 early vs 0.95 late), so it biases *against* the observed early excess. But
5 of the 67 early Foam C swaps involve a bubble born within the previous five frames, and
none of the 113 has been checked by eye.

**Step 4 — verdict: no sixth main-text figure.** Foam F's 3 swaps cannot test the
transition, Foam A's effect is unresolved after normalisation, and Foam C is an
intermediate-to-dry foam whose events are unvalidated. Supplementary note only. The Foam A sentence in the T1
addendum ("swaps concentrate in the dense early foam and become sparse afterward") is true
of raw counts; it needs the per-contact caveat above and must not be read as a rate claim.
Validating the cross-foam events by hand would mean scoring **116 events (113 C + 3 F)** —
five times the Foam A exercise.

---

## Proposed revised wetness figure (for approval)

* **Primary:** corrected junction size (actual junctions, raft core, ÷ local radius) —
  A 0.134, C 0.142, F 0.187, with frame-bootstrap intervals.
* **Secondary:** intensity-derived liquid fraction (no bubble outlines) — the only published
  measure that survives unchanged.
* **Drying panel:** Foam F's corrected junction size over time (0.77 → 0.21 in ~10 min, then
  flat), with Foams A and C for reference, marking the first third where F's K is negative.
* **Removed from the figure:** film half-width and unlabelled fraction, which cannot
  separate liquid from undetected bubbles in Foam F (reported in the text on the raft core,
  with that caveat); circularity, with the corrected caption above.
* **Wording:** "A ≤ C < F, with C intermediate-to-dry", not "C is Foam A's twin on every
  measure"; "F's junctions ≈ 1.4× A's", not "five times".

Supplementary verification figures, per Task 4: the junction overlay, the Foam F frame-0
crops, and the circularity calibration and matched-outline comparison.

## Published statements this would change

The junction numbers and "five times" (wetness doc, `SUMMARY.md` §7, `paper_figures/README.md`);
the drying trajectory 6.10 → 3.75 and "3.6× above A"; film half-width and unlabelled fraction
for Foam F (wetness doc, `SUMMARY.md`, `cellpose_replication_v2.md` including its
"unlabelled 48.2% → missed bubbles" argument, `f_sampling_interval_control.md`); "foam extends
past the field of view" (`SUMMARY.md` §5, wetness doc, `cellpose_replication_v2.md`,
`exp10_replication_attempt.md`); the circularity mechanism (wetness doc, `SUMMARY.md`,
`paper_figures/README.md`); "Foam C is Foam A's twin on every one of these" (`SUMMARY.md`);
the Foam C and Foam F perimeter results (wetness doc, `SUMMARY.md`, and the fragility tables);
and the T1 addendum sentence.

## Artifacts

Drivers: `dev/verify_circularity.py`, `dev/verify_junction.py`, `dev/verify_wetness_raft.py`,
`dev/verify_perimeter_rule.py`, `dev/t1_crossfoam.py`, `dev/t1_rates.py`. Outputs:
`qc/verify_circularity/`, `qc/verify_junction/`, `qc/t1_crossfoam/`, reviewer notes in
`qc/review/`.
