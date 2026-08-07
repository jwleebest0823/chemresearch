# exp10 (Foam F) replication attempt — BLOCKED: exp10 is guard-rejected like Foam C

**Answer up front: the Foam A result does NOT replicate on exp10, but the honest reading
is that exp10 is not measurable, not that the law fails.** The attempt is blocked at Task
2 — exp10 has the same fragmentation defect that rejected Foam C — so no corrected K
could be produced.

**Two things were nevertheless established, and both matter:**

1. **The published exp10 K = −1.74 reproduces exactly, and is an estimator artifact.** On
   the *same* July trusted set, swapping least squares for the leverage-resistant
   estimator moves K from **−1.7409 to +0.0500**. The large negative K should never have
   been read as physics.
2. **exp10's neighbour statistics are pathological** — ⟨n⟩ = 4.15 / 3.76 and a free-fit
   n₀ of **0.83–3.23** against the physical requirement of 6. This was checked *before*
   fitting anything, as instructed.

Consequently **the conclusion in `docs/exp10_10s_vonneumann.md` — that von Neumann's
failure is robust to sampling rate — is withdrawn as unsupported**, on two independent
grounds (§5).

## Scope limits, stated once and applying to everything below
* **exp10 has NO ground truth.** Its detection accuracy is unvalidated, so every number
  here inherits that limitation. Nothing in this document is GT-anchored.
* **exp10 trips the mask clipping warning at 21–28%.** `distance_to_evap_edge` is *not*
  interpretable and **no radial or edge-distance conclusion may be drawn from exp10**.
  von Neumann needs only `area` and `n_sides`, so the clipping does not block the K work.

## 1. Task 2 — the physical-trend gate: exp10 FAILS

A coarsening foam must lose bubbles and grow the survivors. exp10 does neither
consistently. Independent per-frame segmentation:

| frame | 0 | 10 | 20 | 50 | 80 | 120 | 180 | 260 | **300** | 380 | 460 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| n_bubbles | 21 | 18 | 43 | 65 | 65 | 52 | 45 | 33 | **78** | 62 | 39 | 7 |
| median area px² | **329** | 3257 | 2771 | 2397 | 2190 | 2052 | 2188 | 4181 | **438** | 315 | 176 | 73 |
| foam % of frame | 45.4 | 43.7 | 42.2 | 40.0 | 36.7 | 33.0 | 29.0 | 23.7 | 20.5 | 14.0 | 13.7 | 13.3 |
| bubbles / 1e5 foam px | 3.53 | 3.15 | 7.77 | 12.38 | 13.53 | 12.01 | 11.85 | 10.62 | **28.98** | 33.71 | 21.80 | 4.01 |

Three separate pathologies:

* **Frame 0 is anomalous** — median bubble area 329 px² against 3257 px² one frame later
  (10 s). A 10× jump in the median in 10 s is not physical.
* **Bubble DENSITY rises 3.5 → 12.4 per 1e5 foam px over frames 0–50** while the foam area
  *falls* 45.4% → 40.0%. Density rising as area falls is the fragmentation signature that
  rejected Foam C.
* **After f260 the median bubble area collapses ~10×** (4181 → 438 px² by f300) and
  density jumps to 29–34. The foam has drained and the segmenter is shattering it.

Over the whole sequence Spearman ρ(count) = −0.158 (p = 0.44) — no significant trend
either way, against Foam A's ρ = −0.870.

### Even the best window fails
Scanning for a window satisfying **both** physical requirements simultaneously (count
falls *and* median bubble area rises) gives **f140–260**: ρ(count) = −0.592,
ρ(median area) = +0.457. But that is a coarse rank test, and the underlying measurement is
unstable inside it — median bubble area swings 1372 → 5760 → 2896 → 4181 px² between
consecutive sampled frames.

Running the actual propagation over that window, **the fragmentation guard fires**:

> `FRAGMENTATION GUARD: at frame 94 the region count (48) has exceeded 1.50x the running
> minimum (26) for 3 consecutive frames.`

(window frame 94 = absolute frame 234; 48/26 = **1.85×**.)

**So exp10 is guard-rejected exactly as Foam C is, including inside the one window that
passed the coarse trend test.** Per the brief, K was NOT fitted to the corrected pipeline:
there is no corrected trusted set to fit.

**Count curves inside the window, guard in warn mode** (so the whole curve is visible):

| arm | frames | counts (first 12) | min | max | **max/min** | ρ(count) | guard trips? |
|---|---|---|---|---|---|---|---|
| stride 3 (30 s) | 41 | 60, 52, 43, 54, 43, 35, 28, 37, 43, 41, 43, 47 … | 26 | 60 | **2.31×** | −0.416 | **YES** |
| stride 1 (10 s) | 61 | 60, 57, 52, 44, 38, 46, 45, 41, 43, 29, 31, 41 … | 25 | 60 | **2.40×** | −0.325 | **YES** |

Both arms exceed the 1.50× threshold by a wide margin. The negative ρ is a *net* decline
across the window, but the count oscillates by more than 2× within it — the count is
tracking segmentation instability, not coarsening. **Both sampling rates are rejected, so
the 10 s vs 30 s comparison cannot be run on corrected data either.**



## 2. Tasks 1 and 3 — not completed, and why
Task 1 (rebuild exp10's trusted set on the corrected pipeline) and Task 3 (fit K on it)
**cannot be completed**: `segment_track_propagated` raises on the fragmentation guard, by
design, before a trusted set exists. Disabling the guard to force a number would be
precisely the "fit K to fragmenting data" the brief forbids.

What *can* be reported is exp10's n statistics on the July trusted sets — and they are
pathological, which is the answer to "if exp10's n statistics look pathological, say so
before fitting anything":

| dataset | rows | bubbles | **⟨n_sides⟩** | **free-fit n₀** (physics: 6) |
|---|---|---|---|---|
| Foam A, corrected | 7249 | 120 | **5.93** | **6.09–6.17** |
| exp10 s1 (10 s), July | 6229 | 119 | **4.15** | **1.65–3.08** |
| exp10 s3 (30 s), July | 981 | 54 | **3.76** | **0.83–3.23** |

exp10's ⟨n⟩ is far below Foam A's even before the gap-bridging fix, and its n₀ is
nowhere near 6 at any horizon. A foam whose regression says area stops changing at n ≈ 2
is not a foam whose n is being measured correctly.

## 3. Task 3b — isolating the cause of the change from −1.74

**The re-implementation is faithful: the published number reproduces exactly.**

| state | h | dt | **K (least squares)** | **K (robust)** | robust 95% CI | Theil–Sen | n₀ |
|---|---|---|---|---|---|---|---|
| **s1, July data** | 1 | 10 s | **−1.7409** (published −1.7409, n = 5993 ✓) | **+0.0500** | [−0.0599, +0.1499] | −0.3665 | 3.08 |
| s1 | 5 | 50 s | −1.0223 | +0.0450 | [−0.0690, +0.1266] | −0.4451 | 2.34 |
| s1 | 20 | 200 s | −0.3415 | +0.0887 | [−0.0063, +0.2540] | −0.3962 | 1.65 |
| **s3, July data** | 1 | 30 s | **−1.4663** (published −1.47) | **+0.0250** | [−0.0667, +0.1556] | −0.4334 | 3.23 |
| s3 | 5 | 150 s | −0.2598 | +0.0200 | [−0.0975, +0.1900] | −0.6399 | 1.74 |
| s3 | 20 | 600 s | +0.4282 | +0.4929 | [+0.0166, +0.8261] | −0.8277 | 0.83 |

**Reading:**
* The **estimator alone** accounts for essentially the entire change: −1.74 → +0.05, a
  swing of 1.79 on the *identical* data. This is the behaviour the audit benchmark
  predicted (LS biased −0.093 with IQR 1.04 at 1.2% contamination; here the contamination
  is evidently worse).
* **The corrected estimate is not +0.5 — it is ~0.** Five of the six robust CIs include
  zero. exp10 shows **no von Neumann signal**, rather than a negative one.
* Theil–Sen disagrees with median(y/x) here (−0.37 to −0.83 vs ~0), which it did *not* do
  on Foam A (agreement to 3 decimals). Estimator disagreement of that size is itself a
  data-quality alarm: on well-conditioned data these estimators coincide.
* The s3/h=20 cell (+0.49) is the only positive one, and it rests on 177 samples from 54
  bubbles with n₀ = 0.83 — it should not be read as support for anything.

## 4. Task 4 — the 10 s vs 30 s sampling comparison is UNSUPPORTED
The original conclusion ("von Neumann's failure survives finer sampling; the 10 s and 30 s
K-curves overlap") rested on the least-squares K values −1.74 and −1.47. Both are now
shown to be estimator artifacts. Under the robust estimator the two arms give **+0.050 and
+0.025 at matched-ish horizons — both statistically indistinguishable from zero**, so
there is no longer a "failure" whose robustness to sampling could be demonstrated.

**Verdict: the sampling-rate conclusion is withdrawn as unsupported.** It is not reversed
— nothing here shows von Neumann *succeeds* at 10 s — it simply has no evidential basis
left, and cannot be re-established while exp10 is guard-rejected.

This matters beyond exp10: `docs/exp10_10s_vonneumann.md` was cited as *strengthening* the
Gate-2 failure claim by ruling out temporal undersampling. That support is now removed.
(The Gate-2 failure claim has separately been superseded on Foam A — see
`docs/gates_v4_repairs.md`.)

## 5. Task 5 — interpretation, against the pre-commitment

The brief pre-committed to three outcomes. The result is the third, with an important
qualification:

> **K still negative or unresolved → the Foam A result does not generalise, and that is
> the honest finding.**

**It is "unresolved", not "negative".** Precisely:

* **The Foam A result does not replicate on exp10.** exp10's robust K is ~0 with CIs
  spanning zero, against Foam A's +0.483 / +0.497 / +0.501 with CIs clear of zero and a
  1.04× horizon spread.
* **But the non-replication cannot be attributed to physics**, because exp10 fails the
  same data-quality gate that rejected Foam C: the fragmentation guard fires, ⟨n⟩ is 4.15
  against a required ~6, n₀ is 0.83–3.23 against 6, and there is no ground truth to
  adjudicate any of it. A foam whose neighbour count is mis-measured by ~2 cannot test a
  law about neighbour count.
* **No tuning was attempted toward a positive K.** The one window that passed the coarse
  trend test was selected by a pre-registered physical criterion (count down, size up),
  not by inspecting K, and it failed the guard anyway.

**So Foam A remains the only foam on which the corrected von Neumann result stands, and it
still has no independent replication.** exp10 joins Foam C as measured-unusable rather than
as evidence against the law. Three of the project's six foams (C, F, and B by earlier
work) are now rejected on data quality; the binding constraint remains segmentation, and
the learned per-frame detector (`docs/segmentation_hybrid_seeding.md` §5) is the
prerequisite for enlarging the usable set.

## Status
| task | outcome |
|---|---|
| 1 rebuild exp10 trusted set | **blocked** — guard raises before a trusted set exists |
| 2 fragmentation / physical-trend gate | **FAILS** — guard fires at f234 (1.85×); density rises 3.5→12; median area collapses 10× at f300 |
| 3 fit K on corrected pipeline | **not run** — no corrected trusted set (would require overriding a correctly-firing guard) |
| 3b isolate the change from −1.74 | **done** — published value reproduces exactly; the estimator accounts for the whole swing; corrected K ≈ 0 |
| 4 10 s vs 30 s comparison | **withdrawn as unsupported** |
| 5 interpretation | **does not replicate; exp10 is unmeasurable, not evidence against the law** |

GT masks untouched and verified byte-identical (exp10 has none of its own).

**Artifacts:** `qc/exp10/{prop_trusted_s1,prop_trusted_s3}.csv` (July, preserved),
`analysis_summary.json`. Driver: `dev/exp10_v4.py`.
