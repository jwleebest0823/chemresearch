# Foam coarsening: von Neumann's law across three foams

Prepared for Dr. Oh. Every number here traces to a table in `tables/` or a figure in
`figures/`. Plain language throughout; the methods are in `METHODS_BRIEF.md`.

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

**† Foam F's row should not be read as a single number.** Split by period of the sequence, its K is **negative** in the first third and **+1.63** in the last (§7). The values above average across that sign change. Foams A and C are unaffected.

Brackets are 95% confidence intervals from a bootstrap that resamples whole bubbles
(not individual measurements), so within-bubble correlation cannot inflate significance.
**K is positive with the interval clear of zero in all nine cells.** → `figures/fig1_K_vs_horizon.png`, `tables/K_fits.csv`

Foam A's K changes by only **2% across a twentyfold change in prediction horizon**
(30 s to 600 s). A quantity that stable across timescales is behaving like a physical
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
| 4 | **Leverage.** K was fitted by least squares, which weights each bubble by `(n−6)²`. | **86 of 7106 measurements — 1.2% — carried 48% of the fit weight and flipped K's sign at t+1.** Those 86 were giant flickering bubbles, not physics. On another foam this produced K = −1.74. | Stratifying the fit weight by `|n−6|`. → `figures/fig3_leverage.png` |
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

| | ⟨n⟩, all bubbles | ⟨n⟩, interior bubbles | foam interior left unlabelled |
|---|---|---|---|
| **hand-labelled truth** | **5.08** | **5.66** | **25.3%** |
| Cellpose | 5.11 (**+0.03**) | 5.76 (+0.10) | 20.9% |
| watershed | 5.67 (**+0.60**) | 5.71 (+0.09) | 12.4% |

**Cellpose reproduces the hand-labelled neighbour count to within 0.03. The watershed
over-counts by 0.60**, all of it at the raft edge, where flooding the foam mask makes
perimeter bubbles touch each other spuriously.

**⟨n⟩ = 6 is the wrong target for this system, and the hand labels prove it.** The
familiar result ⟨n⟩ → 6 is Euler's theorem for an *infinite* tiling. These are finite
rafts with a free perimeter: about a third of bubbles sit on that edge with ≈4
neighbours, and the ground truth's own population mean is **5.08**. We had previously
used "⟨n⟩ → 6" as a success criterion; it was unattainable.

---

## 4. A methodological warning that generalises beyond foams

**A clean count curve does not imply a clean identity stream.**

All three foams lose bubbles smoothly and monotonically (rank correlation of count
against time: **ρ = −0.995 to −0.9993**) and pass our automated fragmentation guard.
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
* **Foam F is weak.** 56 bubbles, wide confidence intervals, 48% of its interior
  unlabelled (roughly double the ground-truth figure, suggesting genuinely missed
  bubbles), and its distance-to-edge measure is uninterpretable because the foam extends
  past the field of view. It is reported, not weighted equally. Its K also genuinely
  varies with horizon (1.59x) in a way Foams A and C's does not — tested directly and
  **not** a sampling-rate artifact (§6). Worse: its K **changes sign** across the sequence
  (§7), so its pooled value is not a meaningful single number.
* **The neural network does not beat physics.** Across nine held-out-foam cells the graph
  network never beat the best simple baseline and was significantly worse in seven; on two
  foams it collapsed to predicting no change at all. The von Neumann law was the best
  model in eight of nine cells. Our reading: for this target, **the neighbour count `n`
  appears to be a sufficient statistic for the graph structure** — the law is a function
  of `n` alone, so topology is redundant by construction, and a model cannot beat a
  baseline at predicting something the baseline's one feature already determines.
* **Event labels are usable on Foam A only** (§4). Coalescence and neighbour-swap analysis
  on Foams C and F is blocked on the tracker, not the detector.
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

| horizon | Foam F, native 10 s | Foam F, re-sampled to 30 s |
|---|---|---|
| 30 s | **+0.600** [0.400, 0.867] | +0.353 [0.092, 0.567] |
| 150 s | **+0.490** [0.237, 0.805] | +0.303 [−0.037, 0.603] |
| 600 s | **+0.376** [0.105, 0.803] | −0.266 [−0.718, 0.563] |

**The drift does not go away. It gets worse** — at 30 s/frame K falls all the way through
zero. → `figures/fig7_F_sampling_control.png`, `tables/K_foamF_sampling_control.csv`

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
So the collapse in the right-hand column above is our tracking getting worse, not the foam
behaving differently. Two independent checks confirm it: thinning the 10 s data to the same
number of measurements barely moves K (+0.52 to +0.67 at 30 s, still declining), and out of
2000 random draws matched to the re-sampled version's bubble count, **not one** reproduces
its 600 s value.

**Bottom line for the write-up:** Foam F's reported numbers stand as they are. Its horizon
drift is a property of that foam or of how well we can measure it — not of its camera
timing. Full detail in `docs/f_sampling_interval_control.md`.

---

## 7. Is Foam C wet? And how stable are these K values really?

Four checks prompted by the sign flip in §6. Two of the four answers go against what we
expected, and both are reported as found.

### Foam C is DRY — it belongs with Foam A

Twenty frames per foam, one detector, four measures of liquid content.
→ `figures/fig8_foam_wetness.png`, `figures/fig9_foamC_frames.png`,
`tables/foam_wetness_summary.csv`

| measure | Foam A | **Foam C** | Foam F |
|---|---|---|---|
| unlabelled foam interior (films + liquid) | 19.5% | **17.9%** | **47.4%** |
| film thickness ÷ bubble radius | 0.225 | **0.189** | **0.668** |
| **junction size ÷ bubble radius** | **1.04** | **1.14** | **5.68** |
| liquid fraction from image brightness alone | 22.6% | **25.3%** | **32.3%** |

Foam F's junctions are **five times** the size of the other two relative to their own
bubbles — the direct signature of a wet foam, where three films meet at a liquid pool
rather than at a vertex. Foam C is Foam A's twin on every one of these.

Two honest caveats. **Bubble circularity did not work as a wetness measure** — Foam F, the
visibly wet one, came out the *least* round. It is confounded by bubble size, and we are
not using it. And the last row above is the only measure that never touches the bubble
outlines (it reads image brightness and the foam outline only), so it is the one immune to
how generously the software draws boundaries.

### But being dry does not make K stable — none of the three foams is

Splitting each sequence into equal thirds by elapsed time and re-fitting:
→ `figures/fig10_K_by_period.png`, `tables/K_by_period.csv`

| foam | first third | middle third | last third | |
|---|---|---|---|---|
| A | +0.300 [0.283, 0.333] | +0.425 [0.383, 0.467] | +0.450 [0.367, 0.550] | rises 1.5× |
| C | +0.200 [0.183, 0.233] | +0.197 [0.178, 0.200] | +0.133 [0.125, 0.156] | falls 1.5× |
| **F** | **−0.300** [−0.608, −0.033] | **+1.567** [1.134, 1.916] | **+1.633** [1.134, 2.433] | **changes sign** |

Every cell has enough bubbles to clear our power gate and every interval excludes zero, so
this is real movement, not noise. **We had expected A and C to be flat and F to decline.
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
→ `figures/fig11_exclusions_and_fragility.png`, `tables/K_min_area_sweep.csv`,
`tables/K_exclusion_configs.csv`

Rather than pick a minimum bubble size, we swept it. **K rises with the cut in all three
foams and never plateaus**: over the sweep Foam A moves 14%, Foam C 50%, Foam F 57%. There
is no threshold the data single out, so adopting one would be choosing a number.

Dropping perimeter bubbles (a third of Foam A's) raises Foam A's K by 9% and *lowers* Foam
F's by 18% — opposite directions. In Foam F the perimeter bubbles carry twice the interior's
K, which is where evaporation is strongest and plausibly where the physics of interest sits.
Neither filter is adopted; the sensitivity itself is the result.

### How fragile is each foam's number?

Range of K under each perturbation, divided by K's own size (0.5 = moves by half its value):
→ `tables/K_fragility.csv`

| foam | bubbles | drop 20% of bubbles | size cut | exclusions | horizon | **period** | sign flip |
|---|---|---|---|---|---|---|---|
| **A** | 156 | 0.09 | 0.14 | 0.50 | **0.02** | 0.41 | no |
| **C** | 466 | 0.09 | **0.50** | 0.56 | 0.09 | 0.38 | no |
| **F** | 56 | 0.41 | 0.57 | **1.32** | 0.37 | **3.22** | **yes** |

* **Foam A is the only estimate robust across the board** — and it is also the only foam
  with hand-labelled ground truth.
* **Foam C is precise but size-sensitive.** Its 466 bubbles buy tight intervals; the point
  estimate still moves by half its value depending on which bubbles are kept.
* **Foam F is robust to nothing**, and its sign flips under a change involving no tracking
  at all — just looking at the first third of its own sequence.

**Bottom line for the write-up: Foam A carries the result. Foam C supports it with a stated
size sensitivity. Foam F should be reported by period or not as a single number.** Full
detail in `docs/wetness_and_k_fragility.md`.

---

## Task-1 addendum: the missing neighbour swaps

Foam physics says neighbour swaps (T1 events) should be routine. Our pipeline found **1
in 198 frames** — implausible, and a reviewer would ask immediately.

**It was a detector artifact.** The swap detector was searching a neighbour graph built
*without* the gap-bridging repair used everywhere else in the pipeline, so it was missing
edges. A swap requires eight edge conditions to resolve simultaneously, so a modest
per-edge miss rate collapses swap detection almost to zero. Restoring consistency:

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
