# Foam C is dry; K depends on when you measure it; Foam F's K changes sign

Four questions raised after the sub-sampling control (`docs/f_sampling_interval_control.md`),
answered here. The short version:

* **Foam C is DRY.** It groups with Foam A on every measure that scales with liquid
  content. Foam F is 2.5-5x wetter than both.
* **But the wetness mechanism does not explain the fragility, because none of the three
  foams has a stable K across the life of the sequence.** Foam A rises 1.50x, Foam C falls
  1.50x, and **Foam F changes sign** — K = −0.300 [−0.608, −0.033] in its first third
  against +1.63 in its last.
* **The exclusion filters move K substantially and in the same direction in all three
  foams**, with no plateau that would justify a threshold. Neither filter is adopted.
* **Only Foam A survives all four perturbations.** Foam C is stable except to bubble size;
  Foam F is stable to nothing.

Caveat on everything below: **Foams C and F have no hand-labelled ground truth**, so their
detection accuracy is unvalidated and every claim about them inherits that. Foam A's
detection is measured (Cellpose micro-pooled F1 0.966 against 14 hand-labelled frames).

---

## Task 1 — Is Foam C wet or dry?

**Dry. It sits with Foam A, not Foam F.** Twenty evenly spaced frames per foam, one
detector throughout. → `qc/wetness/fig_wetness_three_foams.png`,
`qc/wetness/wetness_summary.csv`

| measure | Foam A | **Foam C** | Foam F | separates? |
|---|---|---|---|---|
| median bubble circularity `4πA/P²` | 0.905 | **0.921** | 0.890 | **no** — see below |
| unlabelled foam interior (films + Plateau borders) | 19.5% | **17.9%** | **47.4%** | yes, F 2.6x |
| film half-width ÷ median bubble radius | 0.225 | **0.189** | **0.668** | yes, F 3.0x |
| junction size: p95 liquid half-width ÷ bubble radius | 1.04 | **1.14** | **5.68** | yes, F **5.0x** |
| liquid fraction from INTENSITY (no bubble labels) | 22.6% | **25.3%** | **32.3%** | yes, weaker |

The junction measure is the sharpest discriminator and is the one that most directly
encodes the physical question: in a dry foam three films meet at a vertex, in a wet foam at
a liquid region of finite area. Foam F's junctions are **five times** the size of Foam A's
and Foam C's, relative to their own bubbles.

**Circularity fails as a discriminator, and it fails in the wrong direction.** Foam F —
the visibly wet one — is the *least* circular of the three, and Foam C is the most. Stating
this plainly because it contradicts the expected pattern: rounded bubbles did not track
wetness here. The likely reason is that circularity is confounded by bubble size. Foam C is
by far the finest foam (median bubble radius 18.9 px, against A's 30.2 and F's 36.1) and
strongly polydisperse; small bubbles have high Laplace pressure and stay round at low
liquid fraction, while Foam F's large bubbles are deformed by the drainage flow. **Do not
use circularity as a wetness proxy in this system.**

**Two features of the data argue the conclusion is not an artifact:**

1. *The obvious confound works against it.* The unlabelled-interior fraction inflates when
   bubbles are small, because films then occupy relatively more area at the same physical
   thickness. Foam C has the **smallest** bubbles and the **lowest** unlabelled fraction;
   Foam F has the **largest** bubbles and the **highest**. The confound would have pushed
   C toward looking wet, and it still looks dry.
2. *The measures reproduce a known answer.* Foam F was independently observed to dry over
   its 37.5 min without reaching Foam A's morphology. The measures say exactly that:
   unlabelled interior 69.7% → 50.0%, intensity-liquid 50.7% → 26.4%, junction size
   6.10 → 3.75 — a large drop that still ends 3.6x above Foam A's 1.04.

Foam C's own trajectory is the mirror image: it starts at 44.1% unlabelled and settles at
~17.9% within the first fifth of the sequence, then is flat. Its opening frames are its
finest (median radius 11.1 px), so that early transient is resolution, not drainage.

Montage for direct inspection: `qc/wetness/fig_foamC_montage.png`. It shows what the
numbers do not: **Foam C's bubbles are round and separated by thin dark films rather than
polygonal and space-filling.** That morphology is unusual for a dry foam and is worth your
eye — but the liquid content, by every measure that scales with it, is Foam A's, not
Foam F's.

**Quantified in passing, and needed for Task 3:** the foam mask covers **0.0%** of the
image border for Foam A, **3.7%** for Foam C and **23.6%** for Foam F. This is the concrete
form of the long-standing note that Foam F's `distance_to_evap_edge` is uninterpretable:
for roughly a quarter of its perimeter the mask is clipped by the field of view, so the
measure is distance-to-frame, not distance-to-evaporation-edge.

---

## Task 2 — K by elapsed-time period

**The expected pattern is not found. None of the three foams is flat, and Foam F changes
sign.** Equal-duration thirds; the 30 s horizon so each measurement sits inside its own
period; samples built on the full trusted table and only then labelled, so no period
boundary truncates a segment. → `qc/k_robustness/fig_K_by_period.png`,
`qc/k_robustness/task2_K_by_period.csv`

| foam | initial third | middle third | final third | pooled | change |
|---|---|---|---|---|---|
| **A** | **+0.3001** [+0.2831, +0.3333]<br>n=5338, 105 bub | **+0.4249** [+0.3834, +0.4665]<br>n=3360, 114 bub | **+0.4497** [+0.3665, +0.5500]<br>n=2266, 43 bub | +0.3667 | **rises 1.50x** |
| **C** | **+0.2000** [+0.1832, +0.2333]<br>n=12697, 466 bub | **+0.1969** [+0.1777, +0.2000]<br>n=8988, 313 bub | **+0.1333** [+0.1250, +0.1556]<br>n=7347, 245 bub | +0.1776 | **falls 1.50x** |
| **F** | **−0.3000** [−0.6083, −0.0333]<br>n=3124, 56 bub | **+1.5671** [+1.1338, +1.9160]<br>n=1984, 34 bub | **+1.6331** [+1.1338, +2.4329]<br>n=864, 23 bub | +0.5995 | **SIGN CHANGE** |

Every cell clears the project's 20-trusted-bubble power gate and every interval excludes
zero, so **none of these is underpowered by the existing criteria** — the movement is
resolved, not noise. Foam A's initial and middle intervals do not overlap; neither do
Foam C's initial and final; Foam F's initial is entirely below zero while its middle and
final are entirely above +1.1. The 150 s horizon reproduces all three patterns
(A +0.313/+0.413/+0.471, C +0.210/+0.200/+0.147, F −0.620/+1.580/+1.642).

**Foam F's negative first third is not a small-bubble or edge artifact.** It survives every
Task 3 filter and gets more negative, not less:

| Foam F, initial third | K | 95% CI | bubbles |
|---|---|---|---|
| full set | −0.3000 | [−0.6083, −0.0333] | 56 |
| interior only | −0.3665 | [−0.6661, −0.0632] | 56 |
| area ≥ median | −0.4669 | [−1.1442, +0.4332] | 35 |
| interior + area ≥ median | −0.5386 | [−1.3310, +0.6458] | 32 |

### Why the sign changes — the mechanism, measured

K = median(y/x) with x = n − 6 and y = dA/dt, so a negative K requires most per-point
slopes to be negative, i.e. most measurements in the (x<0, y>0) or (x>0, y<0) quadrants.
→ `qc/k_robustness/task2_sign_diagnostics.csv`

| foam, period | ⟨n⟩ | n < 6 | **growing** | median dA/dt | **(n<6 AND growing)** | negative slopes |
|---|---|---|---|---|---|---|
| A, all | 5.17 | 61.8% | 38.4% | −0.267 | 12.3% | 18.8% |
| C, all | 5.63 | 52.2% | 49.3% | 0.000 | 16.5% | 28.2% |
| **F, initial** | **4.27** | **78.3%** | **61.4%** | **+1.750** | **45.5%** | **54.3%** |
| F, middle | 4.89 | 67.0% | 39.2% | −1.466 | 17.9% | 26.4% |
| F, final | 4.81 | 57.1% | 38.2% | −1.750 | 12.4% | 25.6% |

In Foam F's wet first third **the majority of bubbles are growing** (61.4%, median
dA/dt = +1.75 px² s⁻¹) while the wet morphology drives the measured neighbour count down to
⟨n⟩ = 4.27 — against 5.17 for Foam A and a hand-labelled Foam A truth of 5.08 population /
5.66 interior. Almost half of all measurements are therefore "fewer than six neighbours
**and** growing", the slopes go negative, and so does K.

**Read carefully, this is not evidence against von Neumann's law.** The law describes area
*exchange* between neighbours at fixed total gas area. During drainage the imaged plane is
not a closed system — liquid leaves and bubbles expand for reasons unrelated to their
neighbour count — so the law's premise does not hold in that regime, and neither does the
sign of a fit that assumes it. Two things follow, and both matter:

* **Foam F's pooled K of +0.5995 averages across a sign change and is not a meaningful
  single number.** It should not be reported as one.
* **The wetness mechanism is supported for Foam F specifically** — K is negative exactly
  where the foam is wettest, and the sign diagnostics show the route — **but it cannot be
  the general explanation**, because Foams A and C are dry throughout and their K still
  moves by 41% and 38% of its own value across the sequence.

---

## Task 3 — Exclusion tests

Both filters are tested separately and together, at the 30 s horizon, and **every
configuration run is reported**. → `qc/k_robustness/fig_exclusions_and_fragility.png`,
`task3a_min_area_sweep.csv`, `task3b_exclusions.csv`

### (a) Minimum bubble size — swept, not chosen

| min area (px²) | Foam A | Foam C | Foam F |
|---|---|---|---|
| 0 (no cut) | +0.3667 | +0.1776 | +0.5995 |
| 200 | +0.3668 | +0.1999 | +0.5995 |
| 800 | +0.4000 | +0.2467 | +0.5999 |
| 1600 | +0.4000 | +0.2666 | +0.7328 |
| 3200 | +0.4166 | +0.2444 | +0.9420 |
| **range** | **+0.050 (14%)** | **+0.089 (50%)** | **+0.343 (57%)** |

**K rises with the size cut in all three foams, and there is no plateau.** For Foams C and
F the estimate moves by half its own value across the sweep. The cut that removes half of
Foam C's measurements raises its K by 41%; the same cut on Foam F raises it by 72%.

The filter is *defensible on measurement grounds* — the ground-truth work measured recall
at 0.625 for small near-edge bubbles against 1.000 for medium and large — but that
justification does not select a threshold, and the data offer no natural one. **The
sensitivity is the finding. No minimum-size filter is adopted.**

### (b) Perimeter exclusion

The first definition tried — "centroid at least one equivalent radius from the foam-mask
edge" — was **geometrically wrong and flagged only 3 of Foam A's 156 bubbles.** The reason
is instructive: the foam mask wraps *around the outside* of the outermost bubbles, so a rim
bubble's centroid already sits ~1 radius from that boundary (observed minimum 1.06 for A,
1.35 for C, 1.08 for F) and the next layer in sits at ~3. The corrected cut at **2
equivalent radii** puts **33.8%** of Foam A's measurements on the perimeter, matching the
~⅓ expected.

| configuration | Foam A | Foam C | Foam F |
|---|---|---|---|
| full set | +0.3667 | +0.1776 | +0.5995 |
| interior only (rim < 1.5r) | +0.3998 | +0.1750 | +0.4933 |
| **interior only (rim < 2r)** | **+0.3999** | **+0.1777** | **+0.4916** |
| interior only (rim < 3r) | +0.3999 | +0.1832 | +0.4002 |
| **perimeter only** | **+0.3166** (63 bub) | **+0.1667** (62 bub) | **+0.9748** (18 bub) |
| interior + area ≥ 200 px | +0.4000 | +0.2000 | +0.4916 |
| interior + area ≥ median | +0.5000 | +0.2666 | +1.1914 |

The rim threshold itself is **not** load-bearing — 1.5r, 2r and 3r give the same interior K
to three decimals in Foam A and within 5% in Foam C — so the finding is not a threshold
artifact.

**The perimeter effect has opposite sign in Foam F.** In Foam A the interior bubbles have
the higher K (+0.400 vs +0.317, a 26% gap); in Foam C the split does essentially nothing
(+0.178 vs +0.167); in **Foam F the perimeter bubbles have twice the interior's K**
(+0.975 vs +0.492). This is exactly the tension flagged in the request: excluding perimeter
bubbles removes the population most affected by evaporation, and in Foam F that population
is where the largest signal sits. **Foam F's perimeter result additionally cannot be taken
at face value**, because 23.6% of its foam mask lies on the image border, so a share of its
"perimeter" bubbles are merely near the edge of the picture.

**No perimeter filter is adopted either.** It changes Foam A's K by 9% and Foam F's by 18%
in opposite directions, which is a statement about estimate stability, not a correction.

---

## Task 4 — How fragile is each estimate?

K at the 30 s horizon, and the range it spans under each perturbation, divided by its own
magnitude so the three foams are comparable. → `task4_fragility.csv`

| foam | bubbles | K | drop 20% of bubbles | min-area cut | exclusions | horizon | **period** | sign flip |
|---|---|---|---|---|---|---|---|---|
| **A** | 156 | +0.3667 | [+0.350, +0.383] **0.09** | **0.14** | 0.50 | **0.02** | 0.41 | no |
| **C** | 466 | +0.1776 | [+0.167, +0.183] **0.09** | **0.50** | 0.56 | **0.09** | 0.38 | no |
| **F** | 56 | +0.5995 | [+0.489, +0.733] **0.41** | **0.57** | **1.32** | 0.37 | **3.22** | **YES, via period** |

Stated plainly:

* **Foam A is the only robust estimate.** Resampling bubbles moves it 9%, the horizon 2%,
  the size cut 14%. It is sensitive to the exclusion configurations (50%) and to period
  (41%), which is real but not disqualifying — it never approaches zero and never flips.
* **Foam C is robust to resampling (9%) and horizon (9%) but not to bubble size (50%).**
  Its K is a strong function of which bubbles are kept. Its 466 bubbles buy precision, not
  accuracy: the intervals are tight and the point estimate still moves by half its value.
* **Foam F is robust to nothing.** Dropping a fifth of its bubbles moves K by 41%; the
  exclusions move it by 132%; the period moves it by 322% **and through zero**. The
  sub-sampling control's sign flip was not an isolated fragility — it is the normal
  behaviour of this estimate.

The perturbation the mentor's question was really about — "is a sign flip possible at
all?" — has a clear answer: **yes, and not only under degraded tracking.** Foam F's K
changes sign under a perturbation with no tracking change whatsoever, namely restricting to
the first third of its own sequence.

---

## Which pre-committed outcomes held

| pre-committed statement | verdict |
|---|---|
| Filters do not change K meaningfully | **false** |
| Filters change K substantially in a way that undermines the current values | **true for C and F**; for A the values survive |
| Foam C is wet and behaves like F | **false** |
| Foam C is dry and behaves like A | **true morphologically** — but this does *not* make its K stable |
| (Task 2 expectation) A and C stable across periods, F declining | **false on both halves.** A rises, C falls, and F does not decline — it starts negative and rises steeply |

The last row is the one to carry forward. The wetness hypothesis predicted the wrong
pattern for Foam F (rising, not declining, as it dries) and predicted stability for A and C
that is not there.

## What should change in how results are reported

1. **Foam F's pooled K should not be quoted as a single number.** It averages a negative
   first third with a strongly positive remainder. Either report it by period, or restrict
   it to the dried-out portion and say so.
2. **Foam A's headline K stands.** It is the only foam whose estimate survives all four
   perturbations, and it is the only foam with hand-labelled ground truth.
3. **Foam C's K should carry its size sensitivity explicitly.** +0.178 with no cut and
   +0.267 with a cut at 1600 px² are both defensible fits of the same data.
4. **Neither exclusion filter is adopted**, and the reason is on the record: they were
   evaluated, they move the numbers, and no measurement argument selects a threshold.

## Artifacts

`qc/wetness/` — `wetness_per_frame.csv`, `wetness_summary.csv`, `summary.json`,
`fig_wetness_three_foams.png`, `fig_foamC_montage.png`.
`qc/k_robustness/` — `task2_K_by_period.csv`, `task2_sign_diagnostics.csv`,
`task3a_min_area_sweep.csv`, `task3b_exclusions.csv`, `task4_fragility.csv`,
`summary.json`, `fig_K_by_period.png`, `fig_exclusions_and_fragility.png`.

Drivers: `dev/foam_wetness.py` (Task 1), `dev/k_robustness.py` (Tasks 2-4),
`dev/k_period_diagnostics.py` (sign mechanism + Task 2 figure),
`dev/k_robustness_figure.py`.
