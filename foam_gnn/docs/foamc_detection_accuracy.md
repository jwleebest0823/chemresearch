# Foam C detection accuracy — the h_maxima "2.3× over-segmentation" claim is REFUTED

First truth reference on Foam C (`exp3` f000/f001, hand-labeled). It answers the
question it was built to answer, and it also **invalidates a comparison I would
otherwise have made**: the headline F1 is not comparable to Foam A's.

**Verdict: the segmenter is NOT over-segmenting Foam C by 2.3×. It over-segments by
6–12%. The dominant Foam C failure is UNDER-detection — large fused regions of
unresolved microbubbles — and this ground truth can demonstrate that it exists but
cannot size it.** Tasks 3 and 4 are consequently **not legitimate to run** (§5).

## 1. The measurement, and why its headline number is not what it looks like
Pooled over exp3 f000+f001, propagated segmenter, IoU 0.5, bubble-cluster bootstrap:

| | precision | recall | **F1** | 95% CI | n_gt | n_pred |
|---|---|---|---|---|---|---|
| propagated | 0.9148 | 0.9990 | **0.9550** | [0.9459, 0.9636] | 1042 | 1138 |
| independent | 0.9140 | 0.9990 | 0.9546 | [0.9454, 0.9632] | 1042 | 1139 |

Per frame and per IoU threshold:

| method | frame | τ | n_gt | n_pred | tp | fp | fn | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| propagated | 0 | 0.50 / 0.75 / 0.90 | 537 | 574 | 537 | 37 | 0 | 0.936 | 1.000 | 0.967 |
| propagated | 1 | 0.50 | 505 | 564 | 504 | 60 | 1 | 0.894 | 0.998 | 0.943 |
| propagated | 1 | 0.75 | 505 | 564 | 499 | 65 | 6 | 0.885 | 0.988 | 0.934 |
| propagated | 1 | 0.90 | 505 | 564 | 497 | 67 | 8 | 0.881 | 0.984 | 0.930 |

**Do not compare F1 0.955 to Foam A's 0.903.** Two tells give it away: recall is
0.999, and f000's numbers are *identical at IoU 0.5 and 0.9*. Both follow from how the
GT was made.

### The labeling was deletion-only — measured, not assumed
IoU of each GT bubble against its best-matching **pre-seed** region:

| frame | n_GT | n_preseed | IoU = 1.000 | IoU ≥ 0.9 | **IoU < 0.9** |
|---|---|---|---|---|---|
| exp1 f000 | 124 | 122 | 95 | 107 | **17** |
| exp1 f049 | 84 | 79 | 71 | 71 | **13** |
| exp1 f097 | 63 | 61 | 55 | 56 | **7** |
| **exp3 f000** | 537 | 574 | **537** | 537 | **0** |
| **exp3 f001** | 505 | 564 | 496 | 497 | **8** |

**Every one of the 537 GT bubbles at exp3 f000 is pixel-identical to a pre-seed region.**
The Foam C labeling pass deleted regions and redrew essentially nothing. Foam A's GT, by
contrast, contains 17 / 13 / 7 genuinely redrawn bubbles per frame.

Two consequences, both recorded in `manifest.csv`:

1. **Recall is 1.0 by construction and carries zero information.** A bubble the
   segmenter never detected cannot enter a GT built by deleting from the segmenter's own
   output. "Recall 0.999" is a tautology, not a measurement.
2. **Only precision is informative**, and it means something narrower than usual:
   *the fraction of pre-seed regions the labeler judged to be real bubbles.*

This is exactly the correction-based-labeling hazard `docs/groundtruth_labeling.md`
warns about, in its strongest form. It is not a criticism of the labeling — deleting
spurious regions is the right first pass on a 574-region frame — but it bounds what can
be concluded.

## 2. What IS established: over-segmentation is 6–12%, not 2.3×
Precision 0.936 (f000) and 0.894 (f001) means the labeler rejected **37 / 574 = 6.4%**
and **68 / 564 = 12.1%** of pre-seed regions. The h_maxima reference implied the
segmenter produced **~2.3× too many regions** (`docs/foamc_fragmentation.md` §3.2).

**That claim is refuted.** With truth in hand, the excess is 6–12%, not 130%. The error
was in the reference, not the segmenter: **h_maxima was under-detecting Foam C**, which
is precisely the ambiguity this ground truth was commissioned to resolve. Every Foam C
conclusion phrased as "N× the h_maxima reference" — including in
`docs/foamc_fragmentation.md` and `docs/segmentation_hybrid_seeding.md` — should be read
as an upper bound on over-segmentation that is now known to be far too loose.

Split/merge diagnostics agree: pooled split rate **0.000 (f000) / 0.014 (f001)**, merge
rate **0.000** everywhere, and predicted-regions-per-GT-bubble is **median 1.0, p90 1,
max 3**, with 99.3% of GT bubbles covered by exactly one region. Nothing like the
"up to 98 regions per bubble" the h_maxima reference reported.

Stratified recall is uninformative here (it is 1.0 by construction), but the stratum
counts document the population: of 1042 GT bubbles, 332 small / 336 medium / 100 large
sit in the near-edge shell.

## 3. What is NOT established: under-detection, which is the real failure
The GT cannot measure it, but it does *witness* it. Of the regions the labeler deleted,
two populations:

| frame | deleted | area median | **largest deleted regions (× median bubble)** |
|---|---|---|---|
| exp3 f000 | 37 | 118 px | **27,083 (55×)**, **21,813 (45×)**, 1057 (2×), … |
| exp3 f001 | 68 | 123 px | **52,240 (95×)**, 2063 (4×), 2053 (4×), … |

Most deletions are small slivers — real but minor over-segmentation. But one or two per
frame are **enormous fused blobs spanning 45–95 median bubbles**: exactly the
"bubbles fused to large regions of unresolved microbubbles" you reported. The labeler
deleted them rather than resolving them, so they leave the GT as *absence*.

Where the foam area actually goes:

| frame | inside a GT bubble | inside a deleted region | film / unassigned |
|---|---|---|---|
| exp1 f000 | **76.9%** | 10.0% | **13.1%** |
| exp3 f000 | **60.4%** | 7.9% | **31.7%** |
| exp3 f001 | **61.3%** | 9.4% | **29.3%** |

**Only ~60% of Foam C's foam area carries a validated bubble, against 77% on Foam A, and
the unassigned fraction is ~2.4× higher.** That gap is the under-detection. It is not
captured by any precision/recall number computed against this GT, because the GT simply
does not claim those pixels.

## 4. Fragmentation is still unfixed — the Li mask fix did not address it
Region counts on exp3 after the mask fix (every 4th frame):

| frame | 0 | 4 | 8 | 12 | 16 | 20 | 24 | 28 | 32 | 36 | 40 | 44 | 48 | 52 | 56 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| regions | 574 | 584 | 604 | 602 | 620 | 678 | 666 | 725 | 745 | 953 | 998 | 893 | 1095 | 1168 | 1193 |

A coarsening foam cannot gain bubbles, yet the count **more than doubles (574 → 1193,
2.08×)**. The mask fix *delayed* the failure — the guard used to trip at frame 11, and
the count at f012 is now 602 where it was ~911 — but did not prevent it. The
**fragmentation guard still fires** (2.08× ≫ the 1.50× threshold) and correctly rejects
exp3 from frame ~36–44 onward at this sampling.

**So the GT validates exactly the two frames that were never in doubt.** f000/f001 are
the early, dense, well-behaved frames; the modeling data spans all 99 frames, and the
frames that break are the ones with no ground truth.

## 5. Tasks 3 and 4: not legitimate to run — guard stays active
Your instruction was to run the gates only if detection is "acceptable (comparable to
Foam A)", and otherwise to say so plainly rather than force gates on bad data. The
honest answer is a third case:

* Detection at f000/f001 is **not measured as bad** — over-segmentation is only 6–12%.
* But it is **not validly measured as good** either: the headline F1 is inflated by
  deletion-only labeling, and recall — the half that would detect the actual failure —
  is structurally uninformative.
* And **the frames that carry the modeling signal are still rejected by the guard.**

Running Gates 1–3 on Foam C would fit von Neumann's law to tracks drawn from a sequence
whose bubble count doubles through coarsening. **I did not run them.** The
fragmentation guard remains active at `raise`. **Foam C modeling numbers, including the
Foam C von Neumann failure, remain unsupported** — unchanged from
`docs/modeling_gates_v2.md`, and now for a measured rather than an inferred reason.

**Task 4 (GNN replication on a second foam) is blocked by the same fact.** The t+20 Foam
A result still rests on one cell of six, and Foam C cannot currently serve as the
independent replication foam. That is a real limitation of the present evidence, not
something to work around.

### What would unblock it
1. **Label with additions, not just deletions** — even 2 frames where missed bubbles are
   *drawn in* would make recall meaningful and size the under-detection.
2. **A mid-sequence Foam C frame** (f049 or later) is what the modeling actually needs;
   f000/f001 cannot validate it. `docs/foamc_fragmentation.md` §6 still holds that those
   frames are not hand-labelable in their current state.
3. **Fix fragmentation at source** — four marker/ridge repairs already failed
   (`docs/segmentation_hybrid_seeding.md`); a learned detector remains the recommendation,
   and this GT (1042 labeled bubbles) is now a usable training seed for one.

**Artifacts:** `qc/foamc_gt/{detection,stratified,splitmerge}.csv`, `pooled.json`.
Driver: `dev/foamc_gt_eval.py`.

---

# Task 2 — recomputing what the mask fix invalidated

## What was regenerated
**Foam A (`exp1_run0`, `exp1_run1`) only.** The stale pre-fix exports are preserved at
`qc/pre_maskfix_exports/` for comparison.

**Foam C exports were deliberately NOT regenerated** (`exports/foamC/STALE_DO_NOT_USE.md`).
Regenerating them requires setting `fragmentation_guard="warn"` — deliberately overriding
a guard that is firing correctly on data measured as unphysical (§4, and the ρ table in
`docs/modeling_gates_v2.md`). Producing a fresh-looking CSV from measurably broken input
would be worse than leaving it absent. They are marked stale in place instead.

**Foam C trusted sets were not rebuilt** for the same reason: `dev/build_trusted_v2.py`
halts on exp3 at the guard, by design.

## The mask fix's effect on Foam A: immaterial, as predicted
Matched per-bubble (nearest centroid within 6 px), old mask vs new mask, identical code
otherwise — so this **is** attributable to the mask fix:

| session | matched bubble-frames | Δ edge-dist mean | median | p95 abs | **changed edge-distance quartile** |
|---|---|---|---|---|---|
| exp1_run0 | 7,396 | **+2.14 px** | +1.85 | 4.0 | **342 / 7,396 = 4.6%** |
| exp1_run1 | 1,874 | **+0.48 px** | +0.25 | 1.9 | **17 / 1,874 = 0.9%** |

`# DECISION`: "material" = large enough to move a bubble between the edge-distance
quartile shells used downstream. **At most 4.6% of bubble-frames move a shell.** The
prediction in `docs/foam_mask_coverage.md` — Foam A immaterial — is confirmed on the
derived artifact, not just the pixel map.

## A caveat that kills the naive before/after comparison
The exports on disk before today were generated **2026-07-09**. They predate **three**
subsequent fixes — the propagation-ratchet fix (9f70dfe, 07-27), Plateau-border rejection
(64eb428, 08-03) and the Li mask fix (5c2a542, 08-04).

So the whole-file diff below measures the **cumulative** effect of four months of pipeline
changes, **not the mask fix**, and must not be attributed to it:

| session | | bubbles | node rows | reorg births | mean track len | frac len ≥ 5 |
|---|---|---|---|---|---|---|
| exp1_run0 | Jul-09 | 1526 | 10646 | 1384 | 6.98 | 25.2% |
| exp1_run0 | **now** | 1600 | 10621 | 1455 | 6.64 | 23.9% |
| exp1_run1 | Jul-09 | 1421 | 6552 | 1332 | 4.61 | 18.6% |
| exp1_run1 | **now** | **2114** | 7418 | **2025** | **3.51** | **12.6%** |

**`exp1_run0` is essentially unchanged** (churn per bubble 0.907 → 0.909). **`exp1_run1`
is materially churnier**: +49% unique bubbles, mean track length −24%, fraction of tracks
≥5 frames 18.6% → 12.6%. Its *edge distances* barely moved (+0.48 px), so this is a
**tracking-structure change, not an edge-distance change**, and with three fixes
confounded I cannot attribute it to any single one.

**Flagged, not resolved:** `exp1_run1` is one of the two sessions feeding the modeling
gates, and a 32% relative drop in long-track fraction there is worth a dedicated
bisection before the Gate 1–3 numbers are quoted again. I did not run that bisection —
it needs one export per intermediate commit, which is a session of its own.

## Also recorded
3 of exp1's 198 frames trip the new clipping warning (10–12% of the image border), so
`distance_to_evap_edge` on those late frames is a distance to the frame, not the
evaporation edge. Minor for Foam A; the same diagnostic is 23–25% on exp10, which is why
that dataset gets its own addendum in `docs/exp10_10s_vonneumann.md`.
