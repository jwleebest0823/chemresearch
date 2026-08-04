# Foam C mid/late failure is FRAGMENTATION, not a threshold problem

**The premise of the intensity-threshold task is refuted by measurement.** I did not
ship a threshold fix, because the gate is not what is failing. This documents the
evidence, the two candidate fixes I tested and rejected, the guard I did add, and what
would actually work.

## 1. The gate has nothing left to reject
The hypothesis was that Otsu's bimodality assumption breaks as Foam C drains, so Plateau
borders stop being rejected. Measured on the surviving regions:

| frame | gate threshold | kept regions | region mean intensity p10 / median | **fraction below threshold** |
|---|---|---|---|---|
| exp3 f000 | 125.1 | 554 | 128 / 149 | **0.0%** |
| exp3 f049 | 115.9 | 1185 | 119 / 141 | **0.0%** |
| exp3 f097 | 115.0 | 1230 | 120 / 142 | **0.0%** |

**Every surviving region is gas-bright — none is anywhere near the threshold.** There is
no dark population left for a better threshold to remove. Moving the cut, adapting it
locally, anchoring it to a calibrated reference, or adding contrast/texture features
would all change nothing, because the spurious regions are *not dark*.

## 2. What is actually happening: bright interiors fragment
Using the h_maxima segmentation (whose count trend is physically correct) as a reference
partition, and counting how many one-per-blob regions fall inside each h_maxima bubble:

| frame | kept regions | h_maxima ref | regions per h_maxima bubble (median / p90 / **max**) |
|---|---|---|---|
| exp3 f000 | 554 | 315 | 1.0 / 4 / 11 |
| exp3 f049 | 1185 | 223 | 2.0 / 11 / **98** |
| exp3 f097 | 1230 | 213 | 2.5 / 9 / **99** |

**A single bubble is being cut into as many as 98 regions.** As Foam C coarsens the
bubbles get larger, their interiors carry more internal shading/texture, the Sato ridge
filter reads that as film, and `interior = film < threshold` shatters into many
components. The pipeline's invariant — *one marker per interior blob* — then faithfully
turns every fragment into its own bubble. That is why the count **rises** (554 → 1112 →
1172) while an independent detector correctly **falls** (315 → 223 → 213).

This is the same mechanism previously recorded on Foam E (exp9): *"large bubbles carry
internal shading; the watershed's interior distance-maxima jitter frame-to-frame."* It
is a known failure mode of this detector on large bubbles, now quantified.

## 3. Two candidate fixes, tested and rejected as ill-conditioned
Neither is shipped. Both are knife-edge, and tuning either to match the h_maxima
reference would be fitting the answer rather than fixing the cause.

**(a) Merge blobs whose separating ridge is weak** (reusing the existing
`split_film_thresh` hysteresis at blob level):

| ridge threshold | exp3 f000 | exp3 f049 | exp3 f097 |
|---|---|---|---|
| 0.20 | 1524 | 1563 | 1456 |
| 0.30 | 298 | 601 | 308 |
| 0.40 | 11 | 39 | 10 |

A 0.1 change in threshold swings the count ~50×, and even at its best (0.30) the trend
is still non-monotonic (298 → 601 → 308). The interface-strength criterion does not
separate real films from spurious internal ridges on this data.

**(b) Morphological closing of the interior mask** (interior-blob counts, no gate):

| radius | exp3 f000 / f049 / f097 | exp1 f000 / f049 / f097 (GT 124 / 84 / 63) |
|---|---|---|
| 0 | 1193 / 1456 / 1467 | 359 / 239 / 183 |
| 2 | 1031 / 934 / 862 | 350 / 227 / 175 |
| **3** | **642 / 519 / 408** ✅ monotone | **259 / 184 / 158** ❌ ~2× over GT |
| 4 | 147 / 73 / 39 | **2 / 1 / 1** ❌ collapse |

r=3 fixes Foam C's trend but **regresses Foam A by ~2×**, and r=4 destroys Foam A
entirely (2 regions). The usable window is narrower than the difference between foams,
so there is no single radius that satisfies validation requirement 1 and 2 together.

**I therefore did not ship either.** Validation requirements 1–3 are consequently *not
met* — there is no fix to validate. Stating that plainly is the honest outcome; shipping
a hand-tuned knife-edge parameter would have produced numbers that look like a fix and
would fail on the next foam.

## 4. What I did add: the fragmentation guard
The collapse guard catches *under*-segmentation and is blind to this by construction.
Added `PropagateConfig.fragmentation_guard` (`raise` / `warn` / `off`, ratio 1.50,
patience 3): **a coarsening foam cannot gain bubbles**, so a sustained rise of the region
count above its running minimum is proof of fragmentation. This encodes exactly the
diagnostic above and would have caught this failure automatically.

**Verified on real data** (every 4th frame of the first 60):

* **exp3 (Foam C): fires at frame 11** — *"region count (911) has exceeded 1.50× the
  running minimum (554) for 3 consecutive frames."* Note how early that is: the
  fragmentation begins well before the frames where it becomes visually obvious.
* **exp1 (Foam A): does not fire** — counts fall monotonically
  122 → 119 → 106 → 102 → 94 → 94 → 92 → 92, exactly as a coarsening foam should.

**Consequence, stated explicitly:** with the default `raise`, Foam C runs now **fail
loud** from frame ~11 instead of silently producing fragmented data. That is the intended
behaviour — it stops the broken data reaching the modeling gates — but it does mean
existing Foam C pipeline runs (e.g. `dev/build_trusted_v2.py`) will now stop. Set
`fragmentation_guard="warn"` to reproduce earlier Foam C results while knowing they are
fragmented. Foam A is unaffected.

This also retroactively strengthens a caveat already recorded in
`docs/modeling_gates_v2.md`: every Foam C modeling number rests on input that this guard
now rejects from frame ~11 onward.

## 5. What would actually work
Ranked by evidence, not preference:

1. **Scale-aware seeding.** The h_maxima detector already produces the physically-correct
   trend on Foam C (315 → 223 → 213) and does not fragment, because it seeks one maximum
   per bubble rather than one marker per connected interior component. The one-per-blob
   rule was introduced to catch small bubbles h_maxima misses; the fix is a *hybrid* that
   uses h_maxima for large bubbles and one-per-blob only where no h_maxima seed exists
   **and the blob is small**. That directly targets the failure (fragmentation of *large*
   bubbles) without giving up small-bubble recall.
2. **Suppress the internal-shading response** at source — e.g. a larger Sato scale, or
   background-flattening within bubbles before the ridge filter — so large interiors stop
   producing false ridges.
3. **A learned per-frame detector** (candidate #2 in the segmentation plan), which does
   not rely on a hand-built ridge/threshold cascade at all. Foam C now has a second
   independent reason to want one.

Option 1 is the cheapest and most targeted, and is my recommendation for the next
session. None of these is a threshold change.

> **UPDATE — options 1 and 2 were subsequently built, swept, and rejected.** See
> `docs/segmentation_hybrid_seeding.md`. Option 1 fails because the fragments are
> *smaller* than the small bubbles a size cap must admit, so no cap separates them;
> option 2 fails because every Sato scale still rises on Foam C. A stronger variant
> (suppressing seeds inside shattered basins) satisfies each foam only in *disjoint*
> parameter ranges, and flips the sign of the Foam C trend on a one-unit parameter step.
> That work also **corrects the emphasis of §2 above**: the max of 98 regions per bubble
> is real but is not the binding problem — removing the catastrophic tail entirely still
> leaves Foam C rising at ~2.3× the reference, because the over-segmentation is broad
> (median ~2 regions per bubble), not concentrated. Only option 3 (a learned detector)
> remains, now with four failed cascade repairs as evidence for it.

## 6. Status of Foam C ground truth
Unchanged from `docs/foamc_labelability.md`: **exp3 f000/f001 are labelable** (554 / 525
regions, contours follow rims); **f049 onward are not**, and this document explains why.
Labeling the early pair remains worthwhile, but the mid/late sequence will not become
labelable until the fragmentation is fixed at source.

**Artifacts:** diagnostics in this document are reproducible from
`dev/assess_foamc_labelability.py` plus the inline measurements recorded here.
