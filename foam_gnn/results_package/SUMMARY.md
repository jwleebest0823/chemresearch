# Foam coarsening: von Neumann's law across three foams

Prepared for Dr. Oh. Every number here traces to a table in `tables/` or a figure in
`figures/`. Plain language throughout; the methods are in `METHODS_BRIEF.md`.

---

## 1. Headline result

**Von Neumann's law holds on all three foams, measured with one detector.** The law says
a bubble with more than six neighbours grows and one with fewer shrinks:
`dA/dt = K·(n − 6)`, with K positive.

| foam | t+1 | t+5 | t+20 | variation across horizons | beats "no change" out-of-sample |
|---|---|---|---|---|---|
| **A** (exp1) | **+0.367** [0.333, 0.400] | **+0.364** [0.333, 0.393] | **+0.358** [0.327, 0.398] | **1.02×** | **6 of 6 folds** |
| **C** (exp3) | **+0.178** [0.167, 0.189] | **+0.180** [0.170, 0.193] | **+0.193** [0.180, 0.206] | 1.09× | 3 of 6 |
| **F** (exp10) | **+0.633** [0.400, 0.850] | **+0.540** [0.313, 0.777] | **+0.458** [0.182, 0.815] | 1.38× | 3 of 6 |

Brackets are 95% confidence intervals from a bootstrap that resamples whole bubbles
(not individual measurements), so within-bubble correlation cannot inflate significance.
**K is positive with the interval clear of zero in all nine cells.** → `figures/fig1_K_vs_horizon.png`, `tables/K_fits.csv`

Foam A's K changes by only **2% across a twentyfold change in prediction horizon**. A
quantity that stable across timescales is behaving like a physical constant.

**The foams disagree on K's size, and most of that disagreement is explained.** Raw, Foam
A looked 2.7× Foam C. Two corrections account for nearly all of it:

| horizon | raw gap | after matching the detector | after also normalising by coarsening rate |
|---|---|---|---|
| t+1 | 2.72× | 2.06× | **1.31×** |
| t+5 | 2.76× | 2.02× | **1.18×** |
| t+20 | 2.59× | 1.85× | **0.98×** |

The detector accounts for 38–46%, the coarsening-rate normalisation a further 44–55% —
**82–101% together, and at t+20 Foams A and C agree to within 2%.** The remaining
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
  past the field of view. It is reported, not weighted equally.
* **The neural network does not beat physics.** Across nine held-out-foam cells the graph
  network never beat the best simple baseline and was significantly worse in seven; on two
  foams it collapsed to predicting no change at all. The von Neumann law was the best
  model in eight of nine cells. Our reading: for this target, **the neighbour count `n`
  appears to be a sufficient statistic for the graph structure** — the law is a function
  of `n` alone, so topology is redundant by construction, and a model cannot beat a
  baseline at predicting something the baseline's one feature already determines.
* **Event labels are usable on Foam A only** (§4). Coalescence and neighbour-swap analysis
  on Foams C and F is blocked on the tracker, not the detector.
* **T1 swaps (§below) are now detected but not yet hand-verified.**

## Task-1 addendum: the missing neighbour swaps

Foam physics says neighbour swaps (T1 events) should be routine. Our pipeline found **1
in 198 frames** — implausible, and a reviewer would ask immediately.

**It was a detector artifact.** The swap detector was searching a neighbour graph built
*without* the gap-bridging repair used everywhere else in the pipeline, so it was missing
edges. A swap requires eight edge conditions to resolve simultaneously, so a modest
per-edge miss rate collapses swap detection almost to zero. Restoring consistency:

| setting | T1 swaps found (Foam A, 198 frames) |
|---|---|
| as shipped (unbridged graph) | **1** |
| **bridged graph, thresholds unchanged (now shipped)** | **24** |
| bridged, border threshold relaxed to 3 px | 35 *(measured, not shipped)* |
| bridged, relaxed to 1 px | 60 *(measured, not shipped)* |

→ `figures/fig5_t1_counts.png`, `tables/t1_counts.csv`

**What is shipped is the consistency fix only** — using the same neighbour graph the rest
of the pipeline uses. The threshold relaxations were measured and deliberately **not**
adopted, because they could not be verified by hand within this session.

**Caveat, stated plainly: the 24 swaps are not yet hand-verified.** Candidate overlays
were rendered (`figures/fig7_t1_candidates_foamA.png`) but at the rendering quality
achieved they are not sharp enough to confirm individual events by eye. A false-positive
rate is therefore **not yet established**, and the T1 rate should not go in a paper until
it is. This is the clearest next task.
