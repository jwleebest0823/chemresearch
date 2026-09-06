# Is Foam F's K-vs-horizon decline an artifact of its 10 s sampling interval?

**Verdict: NO — the second of the three pre-committed outcomes. K still declines when
Foam F is re-sampled at 30 s/frame, so the sampling interval is not the cause. The
decline is also, for the first time, shown to be _statistically resolved_ in the native
series (ΔK = +0.324 [+0.062, +0.617], p = 0.014).**

A second finding fell out of the controls and matters more for how Foam F should be
reported: **sub-sampling is not a clean isolation of the sampling interval.** It also
re-runs tracking on a 3× sparser series, and that — not the interval — is what makes the
sub-sampled K collapse. The experiment answers the question it was asked, and separately
shows why its own headline arm cannot be taken at face value.

## The question

With horizons matched in seconds (`docs/cellpose_replication_v2.md`, units correction),
Foams A and C are flat across horizon and Foam F is not:

| foam | interval | 30 s | 150 s | 600 s | max/min |
|---|---|---|---|---|---|
| A (exp1) | 30 s/frame | +0.3667 | +0.3643 | +0.3583 | 1.02× |
| C (exp3) | 30 s/frame | +0.1776 | +0.1800 | +0.1933 | 1.09× |
| F (exp10) | **10 s/frame** | +0.5995 | +0.4900 | +0.3764 | **1.59×** |

Foam F is also the only foam imaged at 10 s. Dr. Oh's proposal isolates that variable:
keep every third frame of exp10 and re-fit. Same foam, same images, same detector, same
committed masks — only the sampling interval changes.

## Task 1 — the sub-sampled series, verified from the filename timestamps

Frame intervals here are **measured from the parsed image filenames**, never read from
`dataset.EXPERIMENTS[...].interval_seconds`.

| series | frames | dt median (s) | dt min–max (s) | span |
|---|---|---|---|---|
| exp10 native (window f000–f225) | 226 | **10.0020** | 9.9820 – 10.0220 | 2250.1 s = 37.50 min |
| exp10 every 3rd, phase 0 | **76** | **30.0040** | 29.9840 – 30.0270 | 2250.1 s = 37.50 min |
| exp10 every 3rd, phase 1 | 75 | 30.0050 | 29.9850 – 30.0240 | 2220.1 s = 37.00 min |
| exp10 every 3rd, phase 2 | 75 | 30.0040 | 29.9870 – 30.0260 | 2220.1 s = 37.00 min |
| *exp1 (Foam A), for reference* | *198* | *30.0020* | *29.9780 – 30.1090* | — |
| *exp3 (Foam C), for reference* | *99* | *30.0050* | *29.9730 – 30.0860* | — |

The sub-sampled series sits within **0.003 s** of Foam A's and Foam C's own measured
intervals, over the identical 37.5 minutes of foam evolution. The window f000–f225 is
the pre-registered usable window from `dev/v2_verify_and_window.py` (count ≥ 20
objects), unchanged.

## Design

### What sub-sampling can and cannot change

The Cellpose masks are committed per frame and the foam mask is recomputed from the same
raw image, so on any absolute frame both arms must contain **exactly the same regions**.
Verified as a fail-loud guard rather than assumed: on all 76 shared absolute frames the
two arms carry an identical multiset of region areas *and* an identical multiset of
neighbour counts. Sub-sampling therefore cannot change what is available to measure.
It can only change

1. **which** (bubble, frame-pair) measurements enter the fit, via tracking and the
   trusted-segment filter, and
2. the **phase** — the sub-sampled arm's start frames are only those ≡ p (mod 3), so at
   a matched horizon it is a 1-in-3 subsample of the native arm's pair set.

### The guard that failed first, and what it taught

The first version of the measurement-equivalence guard joined the two arms on
(absolute start frame, absolute end frame, start area, n) and asserted `dA/dt` matched.
**It failed loudly, and it was right to.** Two arms can carry the *same starting region*
to a *different end region*, because re-tracking a 3× sparser series is a different
identity problem — and that divergence is exactly what this experiment measures, so it
must not be asserted away.

Keying on both endpoints isolates the claim that does have to hold:

| horizon | measurements sharing both endpoints | max &#124;ΔdA/dt&#124; | same start → same end |
|---|---|---|---|
| 30 s | 1346 (94.3% of the sub-sampled arm) | **0.0e+00** | 99.04% (13 divergences of 1359) |
| 150 s | 1106 (92.8%) | **0.0e+00** | 99.28% (8 of 1114) |
| 600 s | 624 (90.7%) | **0.0e+00** | 99.52% (3 of 627) |

**Wherever the two arms agree on which pair of regions they are looking at, `dA/dt` is
identical to the last bit.** The measurement is not what changes.

### The confound, and the control arms

Sub-sampling changes two things at once. It removes one-frame flicker from the tracker's
view, but every frame-counted filter constant becomes 3× stricter in physical time:

| constant | native (10 s) | sub-sampled (30 s) |
|---|---|---|
| `min_persist_frames = 5` | 50 s | **150 s** |
| `dropout_window = 2` | 20 s | 60 s |
| `area_jump_tol = 0.5` (per step) | over 10 s | over **30 s** of real coarsening |

Four controls, each isolating one candidate cause:

* **`native_p15`** — the native 10 s series re-filtered with `min_persist_frames = 15`
  (= 150 s), the sub-sampled arm's *physical* persistence requirement.
* **phases 1 and 2** — a single phase is one of three equally valid sub-samples.
* **phase-thinned native** — the native arm's own samples restricted to start frames
  ≡ p (mod 3): the sub-sampled arm's measurement count and phase structure, with the
  native arm's tracking and filter.
* **a bubble-count-matched null** — 2000 random draws of whole bubbles from the native
  arm, matched to the sub-sampled arm's bubble count at each horizon.

### Statistics

K is the shipped robust estimator `median(y/x)`; Theil–Sen and least squares are
recorded alongside in `K_arms.csv`. Every interval is a cluster bootstrap resampling
**whole bubbles**, 1000 replicates, 95% percentile.

"Does it decline at all" is answered by a **paired** bootstrap: each replicate resamples
one set of bubbles and refits *all three horizons on that same resample*, so ΔK is
measured with the shared-bubble variance cancelled. This is the argument
`modeling.paired_delta_ci` already makes for MAE comparisons, and it is the reason the
decline resolves here when marginal-interval overlap suggested it would not.

## Task 3 — the two curves

| horizon | native, 10 s/frame | sub-sampled, 30 s/frame (phase 0) |
|---|---|---|
| 30 s | **+0.5995** [+0.4001, +0.8672] — n = 5972, 56 bubbles | **+0.3527** [+0.0916, +0.5665] — n = 1428, 56 bubbles |
| 150 s | **+0.4900** [+0.2367, +0.8045] — n = 5221, 49 bubbles | **+0.3027** [−0.0367, +0.6027] — n = 1192, 37 bubbles |
| 600 s | **+0.3764** [+0.1050, +0.8033] — n = 3107, 34 bubbles | **−0.2664** [−0.7178, +0.5629] — n = 688, 25 bubbles |
| max/min | **1.59×** | n/a — K changes sign (ΔK = +0.62) |

**Stated plainly: the decline does not flatten, does not reverse — it steepens, to the
point of a sign change.** The sub-sampled arm is *worse behaved* than the native one at
every horizon.

### All three phases, and the filter control

| arm | 30 s | 150 s | 600 s | max/min |
|---|---|---|---|---|
| native (10 s) | +0.5995 | +0.4900 | +0.3764 | 1.59× |
| **`native_p15`** (10 s, 150 s persistence) | **+0.5997** | **+0.4900** | **+0.3764** | **1.59×** |
| sub-sampled, phase 0 | +0.3527 | +0.3027 | −0.2664 | sign change |
| sub-sampled, phase 1 | +0.2150 | +0.0717 | +0.0902 | 3.00× |
| sub-sampled, phase 2 | +0.5832 | +0.4588 | +0.3783 | 1.54× |

Two things to read off this table:

**The time-matched persistence filter explains nothing.** `native_p15` is
indistinguishable from `native` — identical at 150 s and 600 s to four decimals, and
+0.5997 vs +0.5995 at 30 s. Raising `min_persist_frames` from 5 to 15 drops 6 of 56
trusted bubbles (all 50 survivors are also trusted natively) and removes only segments
too short to have contributed at the longer horizons anyway. That candidate cause is
dead.

**At 30 s/frame the *level* of K on this foam is not stably estimable.** Three equally
valid sub-samples of the same 37 minutes give K(30 s) = +0.215, +0.353 and +0.583 — a
factor of **2.7**. Phase 2 nearly reproduces the native curve; phase 1 is barely
distinguishable from zero.

## Is the decline distinguishable from flat? (asked independently of sub-sampling)

Yes — in the native series it is, and this is the first time the project has tested it
properly rather than by eyeballing overlapping marginal intervals.

| arm | bubbles at all 3 horizons | ΔK = K(30 s) − K(600 s) | 95% CI | boot p | monotone | verdict |
|---|---|---|---|---|---|---|
| **native (10 s)** | 34 | **+0.3235** | **[+0.0619, +0.6173]** | **0.014** | 86% | **RESOLVED — declines** |
| `native_p15` | 34 | +0.3235 | [+0.0619, +0.6173] | 0.014 | 86% | RESOLVED — declines |
| sub-sampled, phase 0 | 25 | +0.7899 | [+0.1132, +1.1955] | 0.020 | 92% | RESOLVED — declines |
| sub-sampled, phase 1 | 23 | +0.2947 | [+0.0562, +1.2521] | 0.010 | 83% | RESOLVED — declines |
| sub-sampled, phase 2 | 23 | +0.2744 | [−0.0681, +0.7917] | 0.114 | 71% | not resolved |

Four of five arms resolve as declining; the fifth is the phase that most resembles the
native curve and simply lacks power. **ΔK > 0 in every arm without exception.**

Note the paired test restricts to bubbles present at all three horizons, which shifts the
point estimates (native K(30 s) is +0.6999 on those 34 bubbles, against +0.5995 on all
56). That is by construction, not a discrepancy.

## Task 5 — the decomposition, and which cause survives

Phase-thinning the native arm gives it the sub-sampled arm's measurement count while
keeping its tracking and its filter:

| horizon | native, all | thinned p0 | thinned p1 | thinned p2 | thinned range | sub-sampled range |
|---|---|---|---|---|---|---|
| 30 s | +0.5995 | +0.5221 | +0.5699 | +0.6661 | **0.144** | 0.368 |
| 150 s | +0.4900 | +0.4466 | +0.4688 | +0.5689 | **0.122** | 0.387 |
| 600 s | +0.3764 | +0.3550 | +0.3583 | +0.4176 | **0.063** | **0.645** |

**Removing two thirds of the measurements barely moves K, and all three thinned curves
still decline monotonically.** The sub-sampled arm's behaviour is therefore not a
sample-size effect.

The bubble-count-matched null says the same thing about bubbles rather than rows:

| horizon | native drawn down to | null median K | null 95% range | sub-sampled | percentile |
|---|---|---|---|---|---|
| 30 s | 56 of 56 — no loss | — | — | +0.3527 | n/a |
| 150 s | 37 bubbles | +0.4866 | [+0.3291, +0.6650] | +0.3027 | **1st** |
| 600 s | 25 bubbles | +0.3778 | [+0.2305, +0.5987] | −0.2664 | **0th** |

At 600 s, **no** draw of 25 native bubbles out of 2000 reaches the sub-sampled arm's
value. Losing bubbles does not produce that number.

And it is not a different *selection* of bubbles either: the sub-sampled arm's 56 trusted
bubbles include 53 of the native arm's 56 (95% — bubble IDs are comparable because both
arms start at absolute frame 0 and are seeded from the same committed mask).

**What is left is the identity layer**, and it is measurably degraded at 30 s:

| | native | sub p0 | sub p1 | sub p2 | `native_p15` |
|---|---|---|---|---|---|
| trusted bubbles | 56 | 56 | 45 | 35 | 50 |
| trusted segments | 65 | 59 | 47 | 38 | 58 |
| fraction of rows trusted | **0.642** | 0.461 | 0.412 | 0.429 | 0.634 |
| fraction of area trusted | 0.688 | 0.482 | 0.392 | 0.430 | 0.681 |
| reorganization births, total | 271 | 174 | 165 | 166 | 271 |
| …per tracking step | **1.20** | **2.32** | 2.20 | 2.21 | 1.20 |
| …per 1000 s | 120.4 | 77.3 | 74.3 | 74.8 | 120.4 |
| ID retention per step | **0.9730** | **0.9492** | 0.9570 | 0.9538 | 0.9730 |
| median trusted segment | 880 s | 570 s | 660 s | 975 s | 985 s |
| dropout rows caught | 12 | 1 | 3 | 6 | 12 |
| fragmentation guard | passes | passes | passes | passes | passes |

A 3× longer gap makes matching harder exactly as expected: per-step ID retention falls
from 0.973 to 0.949 and the tracker mints **roughly twice as many new identities per
step**. Only 46% of rows survive the trusted filter against 64% natively. Both effects
push in the same direction — fewer, shorter, less reliable trajectories — and at the
600 s horizon that is enough to flip K's sign.

Note the two framings of the birth rate disagree and both are reported: *per step* the
sub-sampled tracker is about twice as bad, *per unit time* it looks better only because
there are a third as many steps in which to fail.

### One premise of the session that the data corrects

The motivating observation was that Foam F's median |dA/dt| is 7.60 px² s⁻¹ "at 10 s" and
4.23 "at 30 s", read as a sampling-rate effect. Both numbers are confirmed exactly
(7.599 at h = 1 and 4.233 at h = 3) — **but they are two _horizons_ measured on the same
native 10 s series, not two sampling rates.** Measured at matched horizons the two arms
agree closely:

| horizon | native | sub p0 | sub p1 | sub p2 |
|---|---|---|---|---|
| 30 s | 4.233 | 4.333 | 4.334 | 3.966 |
| 150 s | 2.940 | 2.967 | 3.337 | 2.786 |
| 600 s | 2.442 | 2.796 | 2.795 | 2.390 |

**Sub-sampling does not reduce noise amplification**, because that quantity is set by the
horizon, not by the acquisition rate. So the "helping" half of the anticipated confound
does not operate at all, and the only live mechanism is the "hurting" half — the
identity layer. This is why the sub-sampled arm is worse rather than better.

## What this means for how Foam F is reported

* **The 1.59× horizon spread stands.** It is not a sampling-rate artifact, and the
  decline behind it is statistically resolved (p = 0.014). The native 10 s numbers stay
  as reported; no caveat about the interval is needed, and none is added.
* **The sub-sampled numbers are not a better measurement of Foam F and are not adopted.**
  They come from a degraded identity layer, and their phase-to-phase spread (2.7× at
  30 s) shows a 30 s cadence cannot pin K on this foam at all.
* **Foam F remains the weak foam, for the reasons already documented** — 56 bubbles, wide
  intervals, 48% of its interior unlabelled — and this session adds one: its K genuinely
  varies with horizon in a way Foams A and C's does not, which is a property of the foam
  or its measurement, not of its clock.
* **A methodological point worth keeping.** Sub-sampling looks like a clean single-variable
  experiment and is not one, because every frame-counted constant downstream silently
  changes meaning and the tracker's job gets harder. The phase-thinned control is the
  version that actually holds everything else fixed, and it is cheap. Any future "does
  the sampling rate matter" test on this pipeline should run it alongside.

## Artifacts

`qc/f_subsample/` — `series.csv`, `K_arms.csv`, `arm_diagnostics.csv`,
`paired_decline.csv`, `decomposition.csv`, `phase_instability.csv`,
`bubble_matched_null.csv`, `equivalence.json`, `power_analysis.json`, `summary.json`,
`figF_subsample_control.png`, plus per-arm trusted sets and node tables.

Drivers: `dev/f_subsample_control.py` (series, arms, guards, K, paired test),
`dev/f_subsample_power.py` (decomposition, nulls, overlap),
`dev/f_subsample_figure.py`. Guard tests: `tests/test_f_subsample_guards.py`.

The native arm reproduces the published Foam F trusted set exactly (6167 rows, 56
trusted bubbles, 333 tracks, 62 frame-0 IDs) — asserted as a guard in the driver.
