# Foam C is intermediate-to-dry; K depends on when you measure it; Foam F's K changes sign

*(Title corrected 2026-09-18; it originally read "Foam C is dry". See the corrections block.)*

> ## ⚠ CORRECTIONS AND WITHDRAWALS (2026-09-18)
>
> Several claims in this document were shown to be wrong by the verification in
> `docs/verification_wetness_t1.md`. They are **left visible below, struck through, with the
> correction beside them**, rather than silently replaced. In summary:
>
> 1. **WITHDRAWN — the "junction half-width" numbers** (A 1.04, C 1.14, F 5.68), "Foam F's
>    junctions are five times the size", and the drying trajectory "6.10 → 3.75, still 3.6×
>    above A". The statistic measured the raft margin and places where the foam outline has
>    leaked onto empty plate, not junctions. Measured at actual junctions inside the raft:
>    **A 0.134, C 0.142, F 0.187** (F ≈ 1.4× A); Foam F dries from 0.77 to about 0.2 within
>    ten minutes and then stays near 0.18.
> 2. **WITHDRAWN — the circularity explanation** ("small bubbles have high Laplace pressure").
>    The apparent ordering came from the pixel-counting perimeter, which reads smaller objects
>    as rounder. With a scale-free perimeter, Foams A and F agree (0.978, 0.975).
> 3. **WITHDRAWN — "Foam F's foam extends past the field of view."** Its raft is fully in view;
>    the foam outline leaks onto the plate.
> 4. **WITHDRAWN — every perimeter-K result in Task 3(b)**, including "in Foam F the perimeter
>    bubbles have twice the interior's K" and the Foam C null. The perimeter rule measured
>    distance to the leaky foam outline and missed 26% (A), 59% (C) and 38% (F) of genuine
>    rim bubbles. Re-measured from the raft edge: interior K exceeds perimeter K in Foam A
>    (+0.433 vs +0.316) **and** Foam C (+0.200 vs +0.117); **Foam F shows no resolved
>    perimeter effect** (+0.616 vs +0.567; relative change 0.03 [0.00, 0.70], within noise —
>    an effect up to 70% of K cannot be excluded).
> 5. **CORRECTED — film half-width and unassigned fraction** were inflated by the same leak
>    (F 0.668 → 0.30; 47.4% → 26.9% inside the raft) and in Foam F cannot separate liquid
>    from undetected bubbles. They are no longer used as wetness measures.
> 6. **CORRECTED — "Foam C is dry and sits with A on every measure."** Foam C sits with A on
>    the median junction size (1.06×) but is intermediate by the 95th percentile, and it too
>    starts wetter (0.43 at frame 0). Read it as intermediate-to-dry.
> 7. **SUPERSEDED — the Task 4 fragility table and its verdicts** ("Foam A is the only
>    robust estimate", "Foam F is robust to nothing"). See `paper_figures/README.md`,
>    Figure 3, and the corrected Task 4 note below.
>
> 8. **CORRECTED (second review, same day)** — "Foams A and C are dry throughout" (Task 2
>    sign mechanism) and "the liquid content ... is Foam A's" (Task 1 montage): Foam C
>    starts wet (junction 0.43 at frame 0) yet its first-third K is +0.200, so early
>    wetness does not by itself make K negative. "The dry foams" (A and C) is replaced by
>    "Foams A and C" throughout. The Foam A middle-third interval was misprinted; the
>    within-window horizon drop for Foam F (0.37 → 0.07) is **not** resolved (intervals
>    [0.07, 0.81] and [0.02, 0.43] overlap). The size-cut explanation ("not measurement
>    error") is narrowed: see `results_package/SUMMARY.md` §7 and paper Figure 3.
>
> Unchanged: the K-by-period results (Task 2), the sign mechanism for Foam F, and the
> intensity-derived liquid fraction, the one wetness number that survives as published.

Four questions raised after the sub-sampling control (`docs/f_sampling_interval_control.md`),
answered here. The short version:

* ~~**Foam C is DRY.** It groups with Foam A on every measure that scales with liquid
  content. Foam F is 2.5-5x wetter than both.~~
  **Corrected:** Foam C is intermediate-to-dry — with A by the median junction size, between
  A and F by the 95th percentile. Foam F's junctions are about 1.4× Foam A's (not 2.5–5×),
  and F is wetter mainly during its first ten minutes.
* **But the wetness mechanism does not explain the fragility, because none of the three
  foams has a stable K across the life of the sequence.** Foam A rises 1.50x, Foam C falls
  1.50x, and **Foam F changes sign** — K = −0.300 [−0.608, −0.033] in its first third
  against +1.63 in its last.
* ~~**The exclusion filters move K substantially and in the same direction in all three
  foams**, with no plateau that would justify a threshold.~~ **Corrected:** the
  minimum-size cut moves K substantially and in the same direction in all three foams, with
  no plateau in the detected sweeps; the raft-edge perimeter exclusion moves Foams A (0.18)
  and C (0.13) but gives no resolved change in Foam F (0.03 [0.00, 0.70]). Neither filter
  is adopted.
* ~~**Only Foam A survives all four perturbations.** Foam C is stable except to bubble size;
  Foam F is stable to nothing.~~
  **Superseded** (perimeter rule withdrawn; see correction 7 above). With the raft-edge
  perimeter, every foam's K depends on the time window; Foams A and C also depend on the
  perimeter bubbles; Foam F does not. The estimator itself is stable for A and C.

Caveat on everything below: **Foams C and F have no hand-labelled ground truth**, so their
detection accuracy is unvalidated and every claim about them inherits that. Foam A's
detection is measured (Cellpose micro-pooled F1 0.966 against 14 hand-labelled frames).

---

## Task 1 — Is Foam C wet or dry?

~~**Dry. It sits with Foam A, not Foam F.**~~ **Corrected: intermediate-to-dry** — with Foam A
by the median junction size, between A and F by the 95th percentile. Twenty evenly spaced
frames per foam, one detector throughout. → `qc/wetness/fig_wetness_three_foams.png`,
`qc/wetness/wetness_summary.csv` *(superseded Sept. 18 by `paper_figures/fig4_wetness.png` and
`qc/verify_junction/raft_core_summary.csv`)*

> **Table as originally published — rows 1–4 withdrawn or corrected (see the table after it).**

| measure | Foam A | **Foam C** | Foam F | separates? |
|---|---|---|---|---|
| ~~median bubble circularity `4πA/P²`~~ | ~~0.905~~ | ~~**0.921**~~ | ~~0.890~~ | ~~**no** — see below~~ |
| ~~unlabelled foam interior (films + Plateau borders)~~ | ~~19.5%~~ | ~~**17.9%**~~ | ~~**47.4%**~~ | ~~yes, F 2.6x~~ |
| ~~film half-width ÷ median bubble radius~~ | ~~0.225~~ | ~~**0.189**~~ | ~~**0.668**~~ | ~~yes, F 3.0x~~ |
| ~~junction size: p95 liquid half-width ÷ bubble radius~~ | ~~1.04~~ | ~~**1.14**~~ | ~~**5.68**~~ | ~~yes, F **5.0x**~~ |
| liquid fraction from INTENSITY (no bubble labels) | 22.6% | **25.3%** | **32.3%** | yes, weaker |

**Corrected (2026-09-18), all measured inside the raft** (median across 20 frames, 95%
bootstrap over frames; `qc/verify_junction/raft_core_summary.csv`):

| measure | Foam A | Foam C | Foam F |
|---|---|---|---|
| **junction size**: inscribed radius at 3-bubble junctions ÷ radius of those bubbles | **0.134** [0.129, 0.137] | **0.142** [0.139, 0.152] | **0.187** [0.175, 0.202] |
| same, 95th percentile across junctions | 0.188 | 0.262 | 0.382 |
| liquid fraction from intensity (raft interior) | 0.221 | 0.253 | 0.327 |
| circularity, scale-free (Crofton) perimeter | 0.978 | 0.984 | 0.975 |
| *unassigned fraction, raft core (not used — see below)* | *0.070* | *0.090* | *0.269* |
| *film half-width ÷ radius, raft core (not used)* | *0.066* | *0.075* | *0.30* |

~~The junction measure is the sharpest discriminator and is the one that most directly
encodes the physical question: in a dry foam three films meet at a vertex, in a wet foam at
a liquid region of finite area. Foam F's junctions are **five times** the size of Foam A's
and Foam C's, relative to their own bubbles.~~
**Corrected:** junction size, measured where three bubbles actually meet, remains the
measure that most directly encodes the physical question, but Foam F's junctions are
**about 1.4×** Foam A's by the median (1.7–2.0× by the 95th percentile), not five times.
The published statistic was the 95th percentile of distance-to-nearest-bubble over every
unlabelled pixel inside the foam outline; none of those pixels lay inside the raft.

~~**Circularity fails as a discriminator, and it fails in the wrong direction.** Foam F —
the visibly wet one — is the *least* circular of the three, and Foam C is the most. Stating
this plainly because it contradicts the expected pattern: rounded bubbles did not track
wetness here. The likely reason is that circularity is confounded by bubble size. Foam C is
by far the finest foam (median bubble radius 18.9 px, against A's 30.2 and F's 36.1) and
strongly polydisperse; small bubbles have high Laplace pressure and stay round at low
liquid fraction, while Foam F's large bubbles are deformed by the drainage flow. **Do not
use circularity as a wetness proxy in this system.**~~
**Corrected:** the size confound was real, but it was a property of the pixel-counting
perimeter (an ideal circle scores 0.953 at 15 px radius and 0.920 at 40 px), not of Laplace
pressure. With a scale-free perimeter the three foams agree to within 0.01 and Foams A and
F are statistically identical. Circularity is still not used as a wetness measure, now
because it carries no signal rather than a reversed one.

~~**Two features of the data argue the conclusion is not an artifact:**~~

1. ~~*The obvious confound works against it.* The unlabelled-interior fraction inflates when
   bubbles are small, because films then occupy relatively more area at the same physical
   thickness. Foam C has the **smallest** bubbles and the **lowest** unlabelled fraction;
   Foam F has the **largest** bubbles and the **highest**. The confound would have pushed
   C toward looking wet, and it still looks dry.~~
   **Withdrawn:** the unlabelled fraction was computed over the leaky foam outline, and in
   Foam F it cannot separate liquid from undetected bubbles.
2. ~~*The measures reproduce a known answer.* Foam F was independently observed to dry over
   its 37.5 min without reaching Foam A's morphology. The measures say exactly that:
   unlabelled interior 69.7% → 50.0%, intensity-liquid 50.7% → 26.4%, junction size
   6.10 → 3.75 — a large drop that still ends 3.6x above Foam A's 1.04.~~
   **Corrected:** the junction "drying" 6.10 → 3.75 was a trajectory of the foam-outline
   leak. Measured at junctions, Foam F dries from 0.77 to about 0.2 within ten minutes and
   then stays near 0.18 — about 1.3× Foam A. The intensity-derived liquid fraction (which
   uses no outlines) still falls from 50.7% to 26.4%, so the drying itself stands; "never
   reaches A's morphology" holds only in that weaker form.

~~Foam C's own trajectory is the mirror image: it starts at 44.1% unlabelled and settles at
~17.9% within the first fifth of the sequence, then is flat. Its opening frames are its
finest (median radius 11.1 px), so that early transient is resolution, not drainage.~~
**Corrected:** Foam C also starts wetter by the junction measure: 0.43 at frame 0, falling
most of the way within about eight minutes (0.18 at 7.5 min) and then drifting to 0.14.
Whether that transient is drainage or the limited resolution of its finest early bubbles is
not established.

Montage for direct inspection: `qc/wetness/fig_foamC_montage.png`. It shows what the
numbers do not: **Foam C's bubbles are round and separated by thin dark films rather than
polygonal and space-filling.** That morphology is unusual for a dry foam and is worth your
eye — ~~but the liquid content, by every measure that scales with it, is Foam A's, not
Foam F's.~~ **Corrected:** with Foam A by the median junction size, between A and F by the
95th percentile (0.26 against 0.19 and 0.38) and by brightness liquid fraction (0.253
against 0.221 and 0.327), and wetter at the start (junction 0.43 at frame 0).

**Quantified in passing, and needed for Task 3:** the foam mask covers **0.0%** of the
image border for Foam A, **3.7%** for Foam C and **23.6%** for Foam F. ~~This is the concrete
form of the long-standing note that Foam F's `distance_to_evap_edge` is uninterpretable:
for roughly a quarter of its perimeter the mask is clipped by the field of view, so the
measure is distance-to-frame, not distance-to-evaporation-edge.~~
**Corrected (2026-09-18):** the border contact is **not** foam extending past the field of
view. Foam F's raft is a complete disc wholly inside the frame (the convex hull of its
bubbles touches the image border in 0 of 20 frames); the foam outline **leaks onto the empty
plate** and reaches the border that way. The outline over-reaches in every foam — 11% (A),
8% (C) and 25% (F) of it lies outside the bubbles' convex hull — so `distance_to_evap_edge`
is inflated near the raft edge in all three, and most in F.

---

## Task 2 — K by elapsed-time period

**The expected pattern is not found. None of the three foams is flat, and Foam F changes
sign.** Equal-duration thirds; the 30 s horizon so each measurement sits inside its own
period; samples built on the full trusted table and only then labelled, so no period
boundary truncates a segment. → `qc/k_robustness/fig_K_by_period.png`,
`qc/k_robustness/task2_K_by_period.csv`

| foam | initial third | middle third | final third | pooled | change |
|---|---|---|---|---|---|
| **A** | **+0.3001** [+0.2831, +0.3333]<br>n=5338, 105 bub | **+0.4249** [+0.3836, +0.4554]<br>n=3360, 114 bub *(interval misprinted as [+0.3834, +0.4665] until 2026-09-18; it came from a different bootstrap run)* | **+0.4497** [+0.3665, +0.5500]<br>n=2266, 43 bub | +0.3667 | **rises 1.50x** |
| **C** | **+0.2000** [+0.1832, +0.2333]<br>n=12697, 466 bub | **+0.1969** [+0.1777, +0.2000]<br>n=8988, 313 bub | **+0.1333** [+0.1250, +0.1556]<br>n=7347, 245 bub | +0.1776 | **falls 1.50x** |
| **F** | **−0.3000** [−0.6083, −0.0333]<br>n=3124, 56 bub | **+1.5671** [+1.1338, +1.9160]<br>n=1984, 34 bub | **+1.6331** [+1.1338, +2.4329]<br>n=864, 23 bub | +0.5995 | **SIGN CHANGE** |

Every cell clears the project's 20-trusted-bubble power gate and every interval excludes
zero, so **none of these is underpowered by the existing criteria** — the movement is
resolved, not noise. Foam A's initial and middle intervals do not overlap; neither do
Foam C's initial and final; Foam F's initial is entirely below zero while its middle and
final are entirely above +1.1. The 150 s horizon reproduces all three patterns
(A +0.313/+0.413/+0.471, C +0.210/+0.200/+0.147, F −0.620/+1.580/+1.642).

**Foam F's negative first third is not a small-bubble or edge artifact.** ~~It survives every
Task 3 filter and gets more negative, not less:~~

> The table below used the withdrawn foam-mask perimeter rule for its "interior" rows.

| Foam F, initial third | K | 95% CI | bubbles |
|---|---|---|---|
| full set | −0.3000 | [−0.6083, −0.0333] | 56 |
| ~~interior only~~ | ~~−0.3665~~ | ~~[−0.6661, −0.0632]~~ | ~~56~~ |
| area ≥ median | −0.4669 | [−1.1442, +0.4332] | 35 |
| ~~interior + area ≥ median~~ | ~~−0.5386~~ | ~~[−1.3310, +0.6458]~~ | ~~32~~ |

**Re-verified (2026-09-18) with the raft-edge perimeter** (`qc/k_robustness/period_filters_raft_edge.csv`):
every configuration stays negative, and the interior-only fit is itself resolved below zero.
The point estimates are not monotone, so "gets more negative" is withdrawn.

| Foam F, initial third | K | 95% CI | bubbles |
|---|---|---|---|
| full set | −0.300 | [−0.608, −0.033] | 56 |
| **interior only (raft edge)** | **−0.539** | **[−0.856, −0.200]** | 36 |
| area ≥ median | −0.467 | [−1.144, +0.433] | 35 |
| interior + area ≥ median | −0.245 | [−1.100, +0.922] | 27 |

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
5.66 interior (5.79 with the interior measured from the raft edge; Sept. 18). Almost half of all measurements are therefore "fewer than six neighbours
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
  the general explanation**, because ~~Foams A and C are dry throughout~~ Foam A is dry
  throughout and Foam C, although it starts wet (junction 0.43 at frame 0), keeps a positive
  K in its first third (+0.200), and both foams' K still moves by 41% and 38% of its own
  value across the sequence. *(Corrected 2026-09-18.)*

---

## Task 3 — Exclusion tests

Both filters are tested separately and together, at the 30 s horizon, and **every
configuration run is reported**. → `qc/k_robustness/fig_exclusions_and_fragility.png`,
`task3a_min_area_sweep.csv`, `task3b_exclusions.csv` *(the perimeter rows and the
figure's perimeter panel are withdrawn; raft-edge replacement:
`qc/k_robustness/exclusions_raft_edge.csv`, `paper_figures/fig3_fragility.png`)*

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

> ## ⚠ WITHDRAWN (2026-09-18) — every perimeter result in this subsection
>
> The rule below (centroid within 2 equivalent radii of the **foam-outline** edge, using
> `distance_to_evap_edge`) is wrong in a way this subsection did not detect: the foam
> outline extends beyond the outermost bubbles, so the rule labels **26% (A), 59% (C) and
> 38% (F) of genuine rim measurements as interior**, and never errs the other way. The
> caveat below ("a share of its perimeter bubbles are merely near the edge of the picture")
> had the direction backwards. The following claims are therefore **withdrawn**, not
> revised:
>
> * "**in Foam F the perimeter bubbles have twice the interior's K** (+0.975 vs +0.492)";
> * "**in Foam C the split does essentially nothing** (+0.178 vs +0.167)";
> * "**the perimeter effect has opposite sign in Foam F**";
> * "It changes Foam A's K by 9% and Foam F's by 18% in opposite directions."
>
> **Replacement measurement, with the perimeter taken from the raft's own edge** (the convex
> hull of the detected bubbles; `dev/raft_edge_distance.py`, `qc/k_robustness/exclusions_raft_edge.csv`;
> 95% bubble-bootstrap intervals, 30 s horizon):
>
> | configuration | Foam A | Foam C | Foam F |
> |---|---|---|---|
> | full set | +0.367 [0.333, 0.400] | +0.178 [0.167, 0.189] | +0.600 [0.406, 0.866] |
> | interior only (rim < 1.5 r) | +0.433 [0.400, 0.483] | +0.200 [0.195, 0.217] | +0.633 [0.167, 1.033] |
> | **interior only (rim < 2 r)** | **+0.433** [0.383, 0.478] | **+0.200** [0.189, 0.217] | **+0.616** [0.150, 1.033] |
> | interior only (rim < 3 r) | +0.400 [0.367, 0.467] | +0.200 [0.183, 0.200] | +0.167 [−0.378, 0.633] |
> | **perimeter only** | **+0.316** [0.283, 0.355] | **+0.117** [0.100, 0.133] | **+0.567** [0.400, 0.878] |
> | interior + area ≥ 200 px | +0.433 [0.400, 0.483] | +0.217 [0.200, 0.233] | +0.616 [0.167, 0.999] |
> | interior + area ≥ median | +0.500 [0.433, 0.567] | +0.267 [0.267, 0.292] | +1.483 [0.572, 2.198] |
>
> What this shows: in **Foams A and C**, rim bubbles fit a lower K than interior bubbles
> (A +0.316 vs +0.433; C +0.117 vs +0.200), and excluding them moves the pooled K by 18%
> (A) and 13% (C), both well above the noise floor of random same-size subsets. In **Foam F**
> excluding the rim changes K by 3% (95% CI 0–70%), within its noise floor — not a resolved
> change, but not evidence of no effect either. The rim threshold is not
> load-bearing between 1.5 and 2 radii; Foam F's 3-radius interior (31 bubbles) is too small
> to read. No perimeter filter is adopted.

The first definition tried — "centroid at least one equivalent radius from the foam-mask
edge" — was **geometrically wrong and flagged only 3 of Foam A's 156 bubbles.** The reason
is instructive: the foam mask wraps *around the outside* of the outermost bubbles, so a rim
bubble's centroid already sits ~1 radius from that boundary (observed minimum 1.06 for A,
1.35 for C, 1.08 for F) and the next layer in sits at ~3. ~~The corrected cut at **2
equivalent radii** puts **33.8%** of Foam A's measurements on the perimeter, matching the
~⅓ expected.~~ *(That match was coincidental: measured from the raft edge, 45.4% of Foam A's
trusted measurements are on the perimeter, and the mask-based rule missed a quarter of them.)*

**Original table — WITHDRAWN (foam-outline perimeter rule):**

| configuration | Foam A | Foam C | Foam F |
|---|---|---|---|
| full set | +0.3667 | +0.1776 | +0.5995 |
| interior only (rim < 1.5r) | +0.3998 | +0.1750 | +0.4933 |
| **interior only (rim < 2r)** | **+0.3999** | **+0.1777** | **+0.4916** |
| interior only (rim < 3r) | +0.3999 | +0.1832 | +0.4002 |
| **perimeter only** | **+0.3166** (63 bub) | **+0.1667** (62 bub) | **+0.9748** (18 bub) |
| interior + area ≥ 200 px | +0.4000 | +0.2000 | +0.4916 |
| interior + area ≥ median | +0.5000 | +0.2666 | +1.1914 |

~~The rim threshold itself is **not** load-bearing — 1.5r, 2r and 3r give the same interior K
to three decimals in Foam A and within 5% in Foam C — so the finding is not a threshold
artifact.~~ **Corrected:** that stability was a property of the wrong rule. With the raft
edge, 1.5 and 2 radii agree in all three foams; 3 radii agrees for Foam C, lowers Foam A's
interior K by 8% (+0.433 → +0.400), and leaves Foam F with 31 bubbles and an interval
spanning zero (+0.167 [−0.378, 0.633]), which cannot be read.

~~**The perimeter effect has opposite sign in Foam F.** In Foam A the interior bubbles have
the higher K (+0.400 vs +0.317, a 26% gap); in Foam C the split does essentially nothing
(+0.178 vs +0.167); in **Foam F the perimeter bubbles have twice the interior's K**
(+0.975 vs +0.492). This is exactly the tension flagged in the request: excluding perimeter
bubbles removes the population most affected by evaporation, and in Foam F that population
is where the largest signal sits. **Foam F's perimeter result additionally cannot be taken
at face value**, because 23.6% of its foam mask lies on the image border, so a share of its
"perimeter" bubbles are merely near the edge of the picture.~~
**WITHDRAWN** — see the notice at the head of this subsection. With the raft edge, Foam F
shows no resolved perimeter effect, and Foam C shows the same direction as Foam A.

~~**No perimeter filter is adopted either.** It changes Foam A's K by 9% and Foam F's by 18%
in opposite directions, which is a statement about estimate stability, not a correction.~~
**No perimeter filter is adopted** — that decision stands. The reason now is that excluding
rim bubbles moves Foam A's and Foam C's K by 13–18% with no measurement argument that selects the
rim as erroneous.

---

## Task 4 — How fragile is each estimate?

> ## ⚠ SUPERSEDED (2026-09-18)
>
> The "exclusions" column below mixes size cuts with the withdrawn perimeter rule, and the
> verdicts rest on it. The revised analysis (`dev/fragility_v2.py`, `qc/k_robustness/fragility_v2.csv`;
> paper Figure 3) keeps three perturbations with 95% bubble-bootstrap intervals and a noise
> floor from random bubble subsets of the same sizes:
>
> | foam | period of the foam's life | minimum size cut | perimeter excluded (raft edge) |
> |---|---|---|---|
> | A | **0.41** [0.25, 0.67] | **0.14** [0.05, 0.25] | **0.18** [0.07, 0.27] |
> | C | **0.38** [0.24, 0.54] | **0.50** [0.37, 0.60] | **0.13** [0.08, 0.20] |
> | F | **3.22** [2.32, 5.04] | **0.57** [0.16, 1.37] | 0.03 [0.00, 0.70] — within noise |
>
> **Corrected verdicts.** Every foam's K depends on the time window. Foams A and C also
> depend on which bubbles are included — Foam C most on size, Foam A modestly on both size
> and rim. **"Foam A is the only robust estimate" is withdrawn as worded**: Foam A's
> *estimator* is robust (random 20% drops 0.09, horizon 0.02), but its value depends on
> window and rim. **"Foam F is robust to nothing" is withdrawn**: Foam F shows no resolved
> response to the perimeter exclusion (0.03 [0.00, 0.70]). Its period sensitivity is what two
> regimes averaged into one pooled value predicts. Restricted to its drier window (after the
> first third, 34 bubbles), Foam F's K barely changes with prediction horizon (+1.57 / +1.59 /
> +1.68 at 30 / 150 / 600 s; horizon range 0.37 [0.07, 0.81] → 0.07 [0.02, 0.43]) — but the
> intervals overlap, so the drop is not resolved, and restricting Foam A the same way moves
> its range the other way (0.02 → 0.09). Its size-cut bar falls within its noise floor there,
> but so do Foam A's and Foam C's, so that half of the test does not single out Foam F.

K at the 30 s horizon, and the range it spans under each perturbation, divided by its own
magnitude so the three foams are comparable. → `task4_fragility.csv`

| foam | bubbles | K | drop 20% of bubbles | min-area cut | exclusions | horizon | **period** | sign flip |
|---|---|---|---|---|---|---|---|---|
| **A** | 156 | +0.3667 | [+0.350, +0.383] **0.09** | **0.14** | 0.50 | **0.02** | 0.41 | no |
| **C** | 466 | +0.1776 | [+0.167, +0.183] **0.09** | **0.50** | 0.56 | **0.09** | 0.38 | no |
| **F** | 56 | +0.5995 | [+0.489, +0.733] **0.41** | **0.57** | **1.32** | 0.37 | **3.22** | **YES, via period** |

Stated plainly:

* ~~**Foam A is the only robust estimate.** Resampling bubbles moves it 9%, the horizon 2%,
  the size cut 14%. It is sensitive to the exclusion configurations (50%) and to period
  (41%), which is real but not disqualifying — it never approaches zero and never flips.~~
  *(superseded — see the notice above)*
* **Foam C is robust to resampling (9%) and horizon (9%) but not to bubble size (50%).**
  Its K is a strong function of which bubbles are kept. Its 466 bubbles buy precision, not
  accuracy: the intervals are tight and the point estimate still moves by half its value.
  *(stands; the revised analysis also finds a resolved rim effect, 0.13)*
* ~~**Foam F is robust to nothing.** Dropping a fifth of its bubbles moves K by 41%; the
  exclusions move it by 132%; the period moves it by 322% **and through zero**. The
  sub-sampling control's sign flip was not an isolated fragility — it is the normal
  behaviour of this estimate.~~ *(withdrawn — Foam F shows no resolved response to the
  perimeter exclusion; its period bar is consistent with two regimes averaged, see the
  notice above)*

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
| Foam C is dry and behaves like A | ~~**true morphologically**~~ **corrected: intermediate-to-dry** (with A by the median junction, between A and F by the 95th percentile) — and this does *not* make its K stable |
| (Task 2 expectation) A and C stable across periods, F declining | **false on both halves.** A rises, C falls, and F does not decline — it starts negative and rises steeply |

The last row is the one to carry forward. The wetness hypothesis predicted the wrong
pattern for Foam F (rising, not declining, as it dries) and predicted stability for A and C
that is not there.

## What should change in how results are reported

1. **Foam F's pooled K should not be quoted as a single number.** It averages a negative
   first third with a strongly positive remainder. Either report it by period, or restrict
   it to the dried-out portion and say so.
2. **Foam A's headline K stands.** ~~It is the only foam whose estimate survives all four
   perturbations, and it is the only foam with hand-labelled ground truth.~~ **Corrected:**
   its estimator is the most stable and it is the only foam with hand-labelled ground truth
   (which reproduces its K to 0.0003), but its value depends on the time window (0.41) and
   on the rim bubbles (0.18).
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

**Added Sept. 18 (corrections):** `qc/verify_junction/raft_core_summary.csv` and
`raft_core_measures_per_frame.csv` (wetness inside the raft); `qc/verify_circularity/`
(scale-free circularity); `qc/k_robustness/trusted_raft_edge.csv`,
`exclusions_raft_edge.csv`, `fragility_v2.csv`, `fragility_v2_estimator_within_regime.csv`,
`regime_share_by_horizon.csv`, `period_filters_raft_edge.csv`. Drivers:
`dev/verify_wetness_raft.py`, `dev/circularity_scalefree.py`, `dev/raft_edge_distance.py`,
`dev/fragility_v2.py`, `dev/fragility_v2_estimator.py`, `dev/regime_share_by_horizon.py`,
`dev/first_third_filters_raft.py`. Figures: `paper_figures/` (see its README).

Drivers: `dev/foam_wetness.py` (Task 1), `dev/k_robustness.py` (Tasks 2-4),
`dev/k_period_diagnostics.py` (sign mechanism + Task 2 figure),
`dev/k_robustness_figure.py`.
