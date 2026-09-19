# Foam coarsening: von Neumann's law across three foams

Prepared for Dr. Oh. Every number here traces to a table in `tables/` or a figure in
`figures/`. Plain language throughout; the methods are in `METHODS_BRIEF.md`.

**Corrected Sept. 18.** Several statements in §3, §5 and §7 were wrong and are marked as
withdrawn where they stood, with the corrected value beside them; nothing was removed
silently. The figures below that also appear in the revised paper are copies of the
paper figures: `fig10` = paper Figure 1, `fig12` = Figure 2, `fig11` = Figure 3, `fig8` =
Figure 4, `fig4` = Figure 5; `fig3` = Supplementary S1, `fig2` = S2, `fig13` = S3, `fig14`
= S4 (`paper_figures/README.md`).

---

## 1. Headline result

**Von Neumann's law holds on all three foams, measured with one detector.** The law says
a bubble with more than six neighbours grows and one with fewer shrinks:
`dA/dt = K·(n − 6)`, with K positive.

Horizons are given in **seconds of elapsed time**, matched across foams. Foams A and C
are imaged at 30 s/frame, Foam F at 10 s/frame, so a horizon quoted in *frames* would
mean a different physical timespan in each foam.

| foam | 30 s | 150 s | 600 s | variation across horizons | beats "no change" out-of-sample |
|---|---|---|---|---|---|
| **A** (exp1) | **+0.367** [0.333, 0.400] | **+0.364** [0.333, 0.393] | **+0.358** [0.327, 0.398] | **1.02×** | **6 of 6 folds** |
| **C** (exp3) | **+0.178** [0.167, 0.189] | **+0.180** [0.170, 0.193] | **+0.193** [0.180, 0.206] | 1.09× | 3 of 6 |
| **F** (exp10) † | **+0.600** [0.400, 0.867] | **+0.490** [0.237, 0.805] | **+0.376** [0.105, 0.803] | 1.59× | 3 of 6 |

**† Foam F's row should not be read as a single number.** Split by period of the sequence, its K is **negative** in the first third and **+1.63** in the last (§7). The values above average across that sign change. Foams A and C do not change sign, but their K also moves with the period of the sequence (1.5×, §7).

Brackets are 95% confidence intervals from a bootstrap that resamples whole bubbles
(not individual measurements), so within-bubble correlation cannot inflate significance.
**K is positive with the interval clear of zero in all nine cells.** → `figures/fig1_K_vs_horizon.png`, `tables/K_fits.csv`

Foam A's K changes by only **2% across a twentyfold change in prediction horizon**
(30 s to 600 s). ~~A quantity that stable across timescales is behaving like a physical
constant.~~ *Corrected Sept. 18:* it is stable across the prediction horizon, but not
across the foam's lifetime — Foam A's K rises 1.5× from the first to the last third of its
sequence and Foam C's falls 1.5× (§7, `figures/fig10_K_by_period.png`). No foam's K is a
constant.

**The foams disagree on K's size, and most of that disagreement is explained.** Raw, Foam
A looked 2.7× Foam C. Two corrections account for nearly all of it:

| horizon | raw gap | after matching the detector | after also normalising by coarsening rate |
|---|---|---|---|
| 30 s | 2.72× | 2.06× | **1.31×** |
| 150 s | 2.76× | 2.02× | **1.18×** |
| 600 s | 2.59× | 1.85× | **0.98×** |

The detector accounts for 38–46%, the coarsening-rate normalisation a further 44–55% —
**82–101% together, and at 600 s Foams A and C agree to within 2%.** The remaining
difference is Foam F, which is also our least reliable foam (§5).

---

## 2. Why this was hard — five measurement artifacts, and what each one faked

This is the part I think is most worth publishing. **Von Neumann's law appeared to fail,
including once with a large negative K, and every one of those failures was an artifact
of the measurement rather than the physics.** Each was caught by a check that did not
depend on the answer coming out right.

| # | The defect | The wrong answer it produced | How it was caught |
|---|---|---|---|
| 1 | **Propagation ratchet.** Bubble identities were carried forward geometrically, so one label could swallow its neighbours and never split back. | Foam A collapsed 385 → 106 bubbles while an independent count of the same frames found 219. | A guard comparing the tracked count against an independent per-frame count. |
| 2 | **Plateau borders counted as bubbles.** The liquid channels where three films meet are bright enough to pass as gas. | Detection precision 0.347; F1 0.515. **And they sit *between* real neighbours, so they corrupted exactly the neighbour count `n` that the law is about.** | 14 hand-labelled frames. F1 0.515 → 0.899 after a per-region intensity gate. |
| 3 | **Foam-mask threshold cliff.** The mask separating foam from background sat on a step in its own threshold curve, so it flickered frame to frame. | Late Foam A frames flooded; bubble identities churned; the mask cut foam off entirely on two other foams. | Sweeping the threshold and finding mask area was a step function of it. |
| 4 | **Leverage.** K was fitted by least squares, which weights each bubble by `(n−6)²`. | **86 of 7106 measurements — 1.2% — carried 48% of the fit weight and pulled K from about +0.34 to +0.14 at t+1, with an interval spanning zero** (~~flipped K's sign~~ — corrected Sept. 18: the sign test failed; the sign did not flip). Those 86 were giant flickering bubbles, not physics. On another foam this produced K = −1.74. | Stratifying the fit weight by `|n−6|`. → `figures/fig3_leverage.png` — retained, but superseded as a headline by the fragility figure (§7) |
| 5 | **A model trained on rejected data.** The neural-network result rested on training data from a foam later rejected for a segmentation defect. | An apparent "graph network beats physics" result at long horizon. | Re-running the split and finding the training set no longer existed. |

**The honest summary of that history: for a period we had a large negative K and believed
von Neumann's law failed in this system. It did not — we were measuring the wrong thing
five different ways.** Fixing the estimator alone moved one foam's K from −1.74 to ≈0;
fixing the neighbour count raised Foam A's K by ~40%.

---

## 3. Validation against hand-labelled truth

14 Foam A frames were hand-labelled (~1,000 bubbles) and used only for testing.

| detector | precision | recall | F1 (loose match) |
|---|---|---|---|
| tuned watershed pipeline | 0.925 | 0.882 | 0.903 |
| **Cellpose (no foam-specific training)** | **0.989** | **0.945** | **0.966** |

→ `tables/gt_detection_per_frame.csv`, `figures/fig4_n_calibration.png`

**A result that surprised us and corrected our own earlier claim.** We had assumed the
watershed's higher neighbour count was the accurate one. Measured against the hand
labels, it is not:

**Re-measured Sept. 18 — please use this table, not the one we sent earlier.** The
earlier version defined "interior" and "unlabelled" from the foam outline, which extends
past the outermost bubbles onto empty plate, and its watershed row came from a different
set of frames. Below, all three are scored on the **same 14 frames**, with the raft edge
taken from the hand-labelled bubbles themselves. Brackets are 95% intervals over frames;
values in parentheses are the paired difference from the hand labels.

| | ⟨n⟩, all bubbles | ⟨n⟩, interior bubbles | ⟨n⟩, rim bubbles | raft interior left unassigned |
|---|---|---|---|---|
| **hand-labelled truth** | **5.08** [4.99, 5.18] | **5.79** [5.73, 5.84] | **4.05** [3.99, 4.11] | **11.4%** [10.2, 12.5] |
| Cellpose | 5.11 (**+0.03** [0.02, 0.05]) | 5.84 (+0.05 [0.02, 0.10]) | 4.04 (−0.01 [−0.04, 0.02]) | 7.2% (−4.2 [−5.3, −3.2]) |
| watershed | 5.68 (**+0.60** [0.52, 0.69]) | 5.71 (−0.08 [−0.14, −0.02]) | **5.68 (+1.62** [1.54, 1.70]) | 11.0% (−0.4 [−0.7, −0.1]) |

**Cellpose reproduces the hand-labelled neighbour count to within 0.05 everywhere. The
watershed over-counts by 0.60, and all of it is at the rim**: its rim bubbles have 1.6
too many neighbours while its interior bubbles are, if anything, slightly low. Inside the
raft the watershed leaves as much space between bubbles as the hand labels do; the
difference is in the band between the outermost bubbles and the foam outline, which the
watershed fills (over the whole outline it leaves 10.9% unassigned against the hand
labels' 25.3%). → `figures/fig4_n_calibration.png`, `tables/n_calibration.csv`

**One qualification (added Sept. 18).** The hand labels were made by correcting an
automatic pre-seed produced by this same watershed, and **87% of hand-labelled bubbles
[84%, 89%] are pixel-identical to a watershed region**. So agreement between the watershed
and the hand labels is partly built in — including the matching space between bubbles in
the last column. The rim excess is not: rim bubbles whose outlines are identical in both
still have **0.76 [0.69, 0.83] more neighbours** in the watershed, so the excess comes from
their surroundings — the watershed keeps 1.4 [1.1, 1.9] regions per frame that match no
hand-labelled bubble and lie mostly outside the hand-labelled raft. Cellpose shares no
origin with the hand labels, which makes its agreement the stronger check.
→ `tables/gt_inheritance_from_watershed_preseed.csv`, `tables/n_calibration_rim_identical.csv`

> **What changed from the earlier table** (interior ⟨n⟩ / unlabelled share):
> * hand labels ~~5.66 / 25.3%~~ → 5.79 / 11.4%;
> * Cellpose ~~5.76 (+0.10) / 20.9%~~ → 5.84 (+0.05) / 7.2%;
> * watershed ~~5.71 (+0.09) / 12.4%~~ → 5.71 (−0.08) / 11.0%.
>
> The hand-label and Cellpose all-bubble values are unchanged; the watershed's moves from
> 5.67 to 5.68 because it is now scored on the same 14 frames. "A quarter of the foam interior is not bubble"
> (25.3%) came from the foam-outline definition and is withdrawn; inside the raft the
> hand labels leave 11.4%. The earlier explanation that the watershed over-counts because
> it leaves the least space between bubbles is also **withdrawn**: inside the raft it
> leaves as much as the hand labels, and Cellpose leaves the least.

**The hand labels also confirm von Neumann's zero-crossing — and expose a detector offset.**
The law says a bubble with exactly six neighbours neither grows nor shrinks, so the fitted
line must cross zero at n = 6. Measured on the same bubbles, with the same code:

| | intercept | **crossing point** | growing-to-shrinking ratio of K |
|---|---|---|---|
| **hand-labelled truth** | −0.003 | **n = 6.01** [5.76, 6.31] | **1.24×** [0.95, 1.60] |
| Cellpose | +0.421 | **n = 5.21** [5.05, 5.37] | **2.42×** [1.95, 3.13] |

**The hand labels land on 6.01 — the textbook value — while the detector lands on 5.21.**
~~The detector's offset roughly doubles a real asymmetry between shrinking and growing
bubbles.~~ **Corrected Sept. 18:** the detector's offset widens the gap between the
shrinking and growing sides to 2.42×; in the hand labels the gap is 1.24× with an interval
that includes no gap at all (0.95–1.60, and 0.95–1.64 resampling whole frame pairs), so we
no longer call it real. The offset does not move our headline K, and it is the likely
reason the detected minimum-size sweep never settles (the hand-labelled sweep does, §7).
~~No detector-only analysis could have found it~~ — a detector-only analysis can see the
offset; what the hand labels add is that it comes from detection, not physics.
→ `figures/fig12_n0_zero_crossing.png`, `tables/n0_and_branch.csv`

**Reassuringly, K itself survives the same test.** K from ground-truth bubbles is +0.366
against +0.333 from detected bubbles on the identical frames — a difference that is not
statistically resolved (p = 0.51) — and the ground-truth value reproduces our published
Foam A figure of +0.367 to within 0.0003 (+0.3664 against +0.3667). Excluding the bubbles the detector misses
changes K by 0.004. **No reported K needed revision.** → `docs/gt_k_validation.md`

**⟨n⟩ = 6 is the wrong target for this system, and the hand labels prove it.** The
familiar result ⟨n⟩ → 6 is Euler's theorem for an *infinite* tiling. These are finite
rafts with a free perimeter: nearly two in five hand-labelled bubbles (38%) sit on that
edge with ≈4 neighbours, and the ground truth's own population mean is **5.08**. Even
the interior bubbles average 5.79, not 6. We had previously
used "⟨n⟩ → 6" as a success criterion; it was unattainable.

---

## 4. A methodological warning that generalises beyond foams

**A clean count curve does not imply a clean identity stream.**

All three foams lose bubbles smoothly and monotonically (rank correlation of count
against time: **ρ = −0.987 to −0.9993** for the series in the table below — corrected
Sept. 18 from "−0.995", which matched other runs, `tables/count_curve_spearman.csv`) and
pass our automated fragmentation guard.
That looks like clean tracking. It is not:

| foam | bubbles, start → end | new identities created mid-sequence |
|---|---|---|
| A | 118 → 61 | 22 (19% of the starting population) |
| C | 555 → 221 | **632 (114%)** |
| F | 62 → 20 | **271 (437%)** |

Foam F creates **four new identities for every bubble it started with**, while its count
curve looks impeccable. **Count-based quality checks verify how many objects exist, never
whether they are the same objects.** Anything that depends on identity — lifetimes,
per-object trajectories, coalescence events — needs a separate check.

This applies to any automated tracking of a cellular system: grain growth in metals,
epithelial tissue, granular packings. The failure is invisible to the statistic most
people report.

---

## 5. Honest limitations

* **One foam has ground truth.** Foams C and F detection accuracy is unmeasured. Foam C's
  only labels were made by deleting from the watershed's own output, so they cannot fairly
  score a different detector.
* **Foam F is weak.** 56 bubbles, wide confidence intervals, ~~48% of its interior
  unlabelled (roughly double the ground-truth figure, suggesting genuinely missed
  bubbles), and its distance-to-edge measure is uninterpretable because the foam extends
  past the field of view~~. **Corrected (Sept. 18):** the 48% was measured over a foam
  outline that leaks off the raft onto the plate; inside the raft it is 27%, which still
  includes bubbles the detector missed (one large missed bubble dominates late frames). The
  raft is fully inside the field of view — its distance-to-edge measure is unreliable
  because of the leak, not because the foam is cut off (the same leak affects Foams A and
  C, §7). It is reported, not weighted equally. Its pooled K varies with horizon (1.59×)
  in a way Foams A and C's does not — tested directly and **not** a sampling-rate artifact
  (§6). That is consistent with its wet and dry regimes being averaged in different
  proportions, but not proven (§6, §7). Worse: its K **changes sign** across the sequence
  (§7), so its pooled value is not a meaningful single number.
* **The neural network does not beat physics.** Across nine held-out-foam cells the graph
  network never beat the best simple baseline and was significantly worse in seven; on two
  foams it collapsed to predicting no change at all. The von Neumann law was the best
  model in eight of nine cells. Our reading: for this target, **the neighbour count `n`
  appears to be a sufficient statistic for the graph structure** — the law is a function
  of `n` alone, so topology is redundant by construction, and a model cannot beat a
  baseline at predicting something the baseline's one feature already determines.
  *Caveat added Sept. 18:* one of the learned models' input features, distance to the foam
  edge, was measured to the leaky foam outline in all three foams (§7), so they were given
  a noisier edge feature than intended. The von Neumann fits do not use it.
* **Event labels are usable on Foam A only** (§4). Coalescence and neighbour-swap analysis
  on Foams C and F is blocked on the tracker, not the detector. (The Foam C swap rate in
  the T1 addendum below rests on this same tracker, so it is unvalidated on both counts.)
* **T1 swaps are detected and hand-verified (0/22 false positives), but the swap
  RATE is not statistically resolved** — 22 events across six time bins, several holding
  0–2 events. See the T1 addendum package.

---

## 6. The one experiment you asked for: is Foam F's horizon drift a sampling artifact?

**No. Tested directly, and the answer is clean.**

Foam F is imaged every 10 s; Foams A and C every 30 s. Foam F is also the only foam whose
K drifts with horizon (1.59x, against 1.02x and 1.09x). Those two facts together are a
fair thing to suspect, so we ran the controlled version: **keep every third frame of Foam
F, giving a 30 s series from the identical images and the identical bubble outlines**, and
re-fit. Frame intervals were measured from the image filenames, not assumed — native
10.002 s, sub-sampled 30.004 s, against Foam A's own 30.002 s.

There are three equally valid ways to keep every third frame (start at frame 0, 1 or 2).
*Corrected Sept. 18:* the version we sent showed only the first; all three are below.

| horizon | Foam F, native 10 s | re-sampled to 30 s, phase 0 | phase 1 | phase 2 |
|---|---|---|---|---|
| 30 s | **+0.600** [0.400, 0.867] | +0.353 [0.092, 0.567] | +0.215 [−0.207, 0.550] | +0.583 [0.356, 0.872] |
| 150 s | **+0.490** [0.237, 0.805] | +0.303 [−0.037, 0.603] | +0.072 [−0.380, 0.540] | +0.459 [0.098, 0.780] |
| 600 s | **+0.376** [0.105, 0.803] | −0.266 [−0.718, 0.563] | +0.090 [−1.023, 0.379] | +0.378 [−0.179, 0.779] |

~~**The drift does not go away. It gets worse** — at 30 s/frame K falls all the way through
zero.~~ **The drift does not go away in any phase** (K at 30 s exceeds K at 600 s in all
three; the decline is resolved in phases 0 and 1, p = 0.02 and 0.01, not in phase 2,
p = 0.11), **but only phase 0 crosses zero**, and the level of K at 30 s is not stable
across phases (+0.22 to +0.58). → `figures/fig7_F_sampling_control.png`,
`tables/K_foamF_sampling_control.csv`, `tables/K_horizon_decline_test.csv`

Two further results settle the interpretation:

**The drift is real, not noise.** Testing it properly — resampling bubbles once and
re-fitting *all three horizons on the same resample*, so the shared-bubble variation
cancels — gives a drop of **+0.324 [+0.062, +0.617], p = 0.014** across the horizon range,
declining in 86% of resamples. Comparing the three intervals by eye had suggested this was
unresolvable; it is resolved. → `tables/K_horizon_decline_test.csv`

**But re-sampling is not the clean experiment it appears to be, and we should say so.**
Dropping two frames in three also forces the software to re-identify every bubble across
gaps three times longer. That job measurably degrades: bubble identities survive a step
97.3% of the time at 10 s but 94.9% at 30 s, and the tracker invents about twice as many
spurious new bubbles per step. Meanwhile the *measurements* are untouched — wherever both
versions agree on which bubble is which, the growth rate is identical to the last decimal.
So the collapse in the phase-0 column above is our tracking getting worse, not the foam
behaving differently. Two independent checks confirm it: thinning the 10 s data to the same
number of measurements barely moves K (+0.52 to +0.67 at 30 s, still declining), and out of
2000 random draws matched to the re-sampled version's bubble count, **not one** reproduces
its 600 s value.

**Bottom line for the write-up:** ~~Foam F's reported numbers stand as they are.~~
*Corrected Sept. 18:* Foam F's numbers are not a sampling-rate artifact, but its pooled K
should be reported by period (§7). Its horizon drift is a property of that foam or of how
well we can measure it — not of its camera timing. Full detail in `docs/f_sampling_interval_control.md`.

**Added Sept. 18 — a candidate explanation of the drift.** Longer horizons draw more of
their measurements from Foam F's first third (0–12 min), which contains its wet phase and
where its K is negative (52% of samples at 30 s, 64% at 600 s). Restricted to the drier
remainder, Foam F's K barely changes with horizon (+1.57, +1.59, +1.68; relative range 0.07
[0.02, 0.43], against 0.37 [0.07, 0.81] pooled). That is consistent with two regimes being
averaged in different proportions rather than a horizon-dependent law, but it is not a
resolved change: the intervals overlap and the window holds only 34 bubbles (§7).

---

## 7. Is Foam C wet? And how stable are these K values really?

Four checks prompted by the sign flip in §6. Two of the four answers go against what we
expected, and both are reported as found.

### Is Foam C wet? — **corrected on Sept. 18; please read this version**

> **Two numbers we sent you in this section were wrong, and we are withdrawing them rather
> than quietly replacing them.** When we checked them against the images
> (`docs/verification_wetness_t1.md`):
>
> * ~~**Foam F's junctions are five times the size of the other two** (junction size ÷ bubble
>   radius A 1.04, C 1.14, F 5.68)~~ — **withdrawn.** That statistic took every pixel inside
>   the foam outline that no bubble covered, and the outline extends past the outermost
>   bubbles, onto the empty plate in Foam F. None of its largest values lay inside the raft.
>   Measured where three bubbles actually meet, **Foam F's junctions are about 1.4× Foam
>   A's**.
> * ~~**"Bubble circularity is confounded by bubble size"** (small bubbles staying round)~~ —
>   the mechanism is **withdrawn.** The apparent ordering came from how perimeter is counted
>   on a pixel grid, which scores smaller objects as rounder; measured properly, Foams A and
>   F are equally round.
> * ~~**"Foam C is DRY — it belongs with Foam A"**~~ (this subsection's heading as first
>   sent) and ~~"Foam C is Foam A's twin on every one of these"~~ — **withdrawn.** Foam C is
>   intermediate-to-dry.
>
> Film thickness and the unlabelled fraction were inflated by the same leak (Foam F 0.668 →
> 0.30; 47.4% → 27%) and in Foam F cannot separate liquid from bubbles the detector missed,
> so we no longer use them as wetness measures. The brightness-based liquid fraction is the
> one number in the old table that stands.

Measured inside the raft, 20 frames per foam, one detector (medians across frames with 95%
intervals over frames):
→ `figures/fig8_foam_wetness.png`, `figures/fig13_junction_measurement.png`,
`figures/fig14_circularity_measurement.png`, `figures/fig9_foamC_frames.png`,
`tables/foam_wetness_summary.csv`

| measure | Foam A | **Foam C** | Foam F |
|---|---|---|---|
| **junction size**: liquid at 3-bubble junctions ÷ radius of those bubbles | **0.134** [0.129, 0.137] | **0.142** [0.139, 0.152] | **0.187** [0.175, 0.202] |
| same, 95th percentile across junctions | 0.19 [0.17, 0.21] | 0.26 [0.25, 0.28] | 0.38 [0.29, 0.66] |
| liquid fraction from image brightness (pixels classified by brightness alone) | 0.221 [0.212, 0.229] | **0.253** [0.239, 0.273] | **0.327** [0.302, 0.375] |

**Foam F is wetter, but mainly during its first ten minutes**: its junctions shrink from
0.77 to about 0.2 of a bubble radius by minute ten, then stay near 0.18 — about 1.3× Foam
A's for the rest of the sequence. The earliest junction values are upper bounds — some of
those junctions enclose small bubbles the detector missed — but the brightness fraction,
which does not rely on outlines inside the raft, also falls over the same ten minutes (0.53
to 0.38). That wet window falls inside the first third of the sequence (0–12 min), **where
Foam F's K is negative** (next subsection). Foam C sits with A on the median junction and
between A and F by the 95th percentile, and it too starts wetter (0.43 at frame 0), mostly
settling within about eight minutes — yet its first-third K is positive (+0.20), so an early
wet phase does not by itself make K negative. So: **Foam C is intermediate-to-dry, and Foam
F is the wettest foam, most of all in its early phase.** → `tables/foam_wetness_per_frame.csv`

### Wet or dry, K is not stable — none of the three foams has a constant K

Splitting each sequence into equal thirds by elapsed time and re-fitting:
→ `figures/fig10_K_by_period.png`, `tables/K_by_period.csv`

| foam | first third | middle third | last third | |
|---|---|---|---|---|
| A | +0.300 [0.283, 0.333] | +0.425 [0.384, 0.455] | +0.450 [0.367, 0.550] | rises 1.5× |
| C | +0.200 [0.183, 0.233] | +0.197 [0.178, 0.200] | +0.133 [0.125, 0.156] | falls 1.5× |
| **F** | **−0.300** [−0.608, −0.033] | **+1.567** [1.134, 1.916] | **+1.633** [1.134, 2.433] | **changes sign** |

Every cell has enough bubbles to clear our power gate. ~~Every interval excludes zero, so
this is real movement, not noise.~~ *Corrected Sept. 18:* the movement is resolved because
the range across periods clears the noise floor of random bubble subsets in every foam
(fragility table below) — an interval excluding zero only shows K is not zero. Foam F's
middle and last thirds are indistinguishable from each other. *(The Foam A middle-third
interval was also misprinted as [0.383, 0.467]; it is [0.384, 0.455].)* **We had expected A and C to be flat and F to decline.
None of that is what the data show.**

**Why Foam F goes negative, measured rather than guessed.** In its wet first third, 61% of
bubbles are *growing* — the liquid is draining out of the imaged plane, so gas area is not
conserved there — while the wet morphology drives the measured neighbour count down to 4.3
(Foam A: 5.2). Nearly half the measurements are therefore "fewer than six neighbours **and**
growing", which is precisely the combination that makes the fitted K negative.
→ `tables/K_sign_diagnostics.csv`

**This is not evidence against von Neumann's law.** The law describes area exchange between
neighbours at fixed total gas area; during drainage that premise simply does not hold, so
neither does the sign of a fit that assumes it. It does mean Foam F's pooled K averages
across two different regimes.

### The exclusion filters move the numbers, so we are not using them

Both suggested filters were tested, separately and together, and **every configuration is
reported** — including the ones that changed nothing.
→ `figures/fig11_fragility.png`, `tables/K_min_area_sweep.csv`,
`tables/K_exclusion_configs.csv` (perimeter measured from the raft edge; the earlier
foam-outline table is withdrawn — see below)

Rather than pick a minimum bubble size, we swept it. **K rises with the cut in all three
foams and never plateaus**: over the sweep Foam A moves 14%, Foam C 50%, Foam F 57%. There
is no threshold the data single out, so adopting one would be choosing a number.

~~**We now know why, and it is not measurement error.** Tested against the hand labels (§3),
K from ground-truth bubbles and from detected bubbles are statistically indistinguishable,
and the bubbles the detector misses contribute nothing. What a size cut actually does is
shift the population between two branches that genuinely differ [...] and it explains the
missing plateau: the mixture shifts continuously, so there is no point at which it stops.~~

**Corrected Sept. 18 — what the hand labels do and do not show.** On Foam A's 14
hand-labelled frames, K also moves with the size cut when the bubbles are drawn by hand
(relative range 0.15 [0.06, 0.31]: from +0.37 with no cut to +0.42 by 400 px², then level),
so the sensitivity is **not only** detection error. But the hand-labelled sweep levels off
and the detected sweep on the same frames does not (0.25 [0.03, 0.62]), consistent with the
detector's wider gap between bubbles with fewer and more than six neighbours (§3); the two
ranges are not resolved from each other, so "not measurement error" was too strong, and the
branch mixture does not by itself explain the missing plateau. How a cut shifts the fit is
clear: area and neighbour count are strongly correlated (Spearman 0.73 [0.68, 0.77] in the
hand labels), and none of the smallest third of hand-labelled bubbles has more than six
neighbours, so raising the cut removes low-n bubbles. Whether the two sides have genuinely
different K is not established by the hand labels (1.24× [0.95, 1.60], §3). Foams C and F,
where the size sensitivity is largest, have no hand labels to check against.
→ `tables/K_ground_truth_min_area_sweep.csv`, `tables/gt_branch_mixture_facts.csv`

> **Withdrawn (Sept. 18): every perimeter result we sent you.** ~~Dropping perimeter bubbles
> (a third of Foam A's) raises Foam A's K by 9% and *lowers* Foam F's by 18% — opposite
> directions. In Foam F the perimeter bubbles carry twice the interior's K, which is where
> evaporation is strongest and plausibly where the physics of interest sits.~~
> Our rule for "perimeter" measured distance to the foam outline, and because the outline
> extends beyond the outermost bubbles, the rule missed **a quarter (Foam A) to three-fifths
> (Foam C) of the genuine rim bubbles**. The Foam F "twice the interior's K" result, and the
> finding that Foam C showed no perimeter effect, came from that error.

**Re-measured from the raft's own edge:** in **Foams A and C** rim bubbles fit a lower K
than interior ones (Foam A +0.32 [0.28, 0.36] vs +0.43 [0.38, 0.48]; Foam C +0.12 [0.10,
0.13] vs +0.20 [0.19, 0.22]), and excluding them moves the pooled K by 18% and 13%. **Foam F
shows no resolved perimeter effect** (+0.57 [0.40, 0.88] vs +0.62 [0.15, 1.03]; relative
change 0.03 [0.00, 0.70], within noise — an effect as large as 70% of K cannot be excluded)
at a rim band of 1.5–2 bubble radii; a 3-radius band leaves only 31 of its bubbles
and an interval spanning zero, so a wider band cannot be tested. Neither filter is
adopted; the sensitivity itself is the result.
→ `tables/K_exclusion_configs.csv`

### How far does each foam's number move — and why?

The range of K under each perturbation, divided by K's own size (0.5 = moves by half its
value), with 95% intervals and a noise floor from random bubble subsets of the same sizes.
→ `figures/fig11_fragility.png`, `tables/K_fragility.csv`

| foam | bubbles | period of the foam's life | size cut | perimeter excluded |
|---|---|---|---|---|
| **A** | 156 | 0.41 [0.25, 0.67] | 0.14 [0.05, 0.25] | 0.18 [0.07, 0.27] |
| **C** | 466 | 0.38 [0.24, 0.54] | **0.50** [0.37, 0.60] | 0.13 [0.08, 0.20] |
| **F** | 56 | **3.22** [2.32, 5.04] | 0.57 [0.16, 1.37] | 0.03 [0.00, 0.70] — within noise |

The estimator itself is stable for Foams A and C: dropping a random fifth of the bubbles
moves K by 9% of its value, and changing the prediction horizon from 30 to 600 s by 2% (A)
and 9% (C). For Foam F those are 41% and 37%.

* ~~**Foam A is the only estimate robust across the board**~~ — **corrected:** Foam A's
  *estimator* is the most stable, and it is the only foam with hand labels, but its value
  depends on the time window and on the rim bubbles.
* **Foam C is precise but size-sensitive.** Its 466 bubbles buy tight intervals; the point
  estimate still moves by half its value depending on which bubbles are kept.
* ~~**Foam F is robust to nothing**~~ — **corrected:** Foam F shows no resolved response to
  the perimeter exclusion (though its interval reaches 0.70). Its period bar, far larger than
  any other, is what you would expect from **two regimes averaged into one number** — a
  first third containing the wet phase, with negative K, and a drier remainder with K ≈ +1.6
  — rather than from a law that fails. Restricted to the drier part, Foam F's K barely
  changes with prediction horizon (+1.57, +1.59, +1.68 at 30, 150 and 600 s; range 0.07
  [0.02, 0.43] against 0.37 [0.07, 0.81] pooled), and longer horizons draw more of their
  measurements from the first third (52% at 30 s, 64% at 600 s). But the intervals overlap,
  the window has 34 bubbles, restricting Foam A the same way moves its horizon range the
  other way (0.02 to 0.09), and restricting the window quiets the size bar in all three
  foams — so we call it consistent with the two-regime reading, not proof of it.

**Bottom line for the write-up: Foam A carries the result. Foam C supports it with a stated
size sensitivity. Foam F should be reported by period** — its pooled number describes
neither of its two regimes. Full detail in `docs/wetness_and_k_fragility.md` and
`docs/verification_wetness_t1.md`.

---

## Task-1 addendum: the missing neighbour swaps

Foam physics says neighbour swaps (T1 events) should be routine. Our pipeline found **1
in 198 frames** — implausible, and a reviewer would ask immediately.

**It was a detector artifact.** The swap detector was searching a neighbour graph built
*without* the gap-bridging repair used everywhere else in the pipeline, so it was missing
edges. A swap requires eight edge conditions to resolve simultaneously, so a modest
per-edge miss rate collapses swap detection almost to zero.

Restoring consistency raised the count from **1 to 22 swaps** in the same 198 frames.
**What is shipped is the consistency fix only** — using the same neighbour graph the rest
of the pipeline uses. Loosening the contact-length threshold as well would raise the
count further, but was measured and deliberately **not** adopted.

**All 22 were then verified by hand**, one at a time, against four-panel figures spanning
the frame before the swap, the swap, and two frames after — the fourth panel is what
separates a real swap from a momentary segmentation glitch, since the two are identical
over only two frames. **Result: 0 flicker, 0 unclear, false-positive rate 0/22, 95%
confidence interval [0%, 14.9%].** → `figures/fig5_verified_T1_swap.png`

Full detail, including the swap rate over time and an open question about whether the
shipped threshold is excluding genuine swaps, is in the separate T1 addendum package.

**Added Sept. 18 — two limits on what the swaps can say.**
* *"Swaps concentrate in the dense early foam" is true of counts, not of a rate.* The early
  foam also has more shared films on which a swap can happen. Per available contact, Foam
  A's first-third excess drops from 5.8× to **2.15× (p = 0.32, 95% CI [0.62, 11.4])** — no
  evidence of a decline, but with 20 events the test could not have resolved a ratio below
  about 7.
* *Other foams.* The same detector finds **113 swaps in Foam C and 3 in Foam F**, none
  checked by eye. Foam C's per-contact decline is resolved (2.29×, p = 0.001) but
  unvalidated — and it rests on a tracker that creates spurious new identities on Foam C
  (§4, §5); Foam F's three cannot test its wet-to-dry transition. Swaps are therefore
  a supplementary note, not a figure. Hand-checking the 116 cross-foam events has not been
  done. → `docs/verification_wetness_t1.md`
