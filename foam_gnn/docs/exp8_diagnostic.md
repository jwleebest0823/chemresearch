# exp8 (Foam D) diagnostic — does clearer rendering reduce segmentation churn?

**Answer: No.** exp8's rendering *is* clearer (clean boundaries, Plateau 100 %),
but it is imaged at **lower effective magnification** — the foam fills only ~6 % of
the frame vs ~22 % for Foam A — so each bubble spans few pixels and the watershed
churns *more*, not less. Better rendering was not enough; the limiting factor is
**pixels-per-bubble (magnification/scale)**, not rendering clarity.

## Segmentation transfer (Foam-A params → exp8)
QC overlays (`qc/exp8/seg_exp8_{early,mid,late}.png`): the foam-boundary mask is
correct, and the bubbles that ARE segmented are clean (**Plateau 3-way = 1.00** at
all three frames). BUT the foam is a small blob and **small bubbles are
under-segmented** — the early frame shows ~40–50 visible bubbles, only 26 outlined.
Bubble counts (26 → 7) therefore *undercount* the population. Params **partially
transfer**: boundary + large bubbles yes; small bubbles need re-tuning for scale
(or higher-magnification imaging). A stray false-boundary line appears late.

## THE CHURN COMPARISON (the number that matters)
Full 99-frame runs, current tracker (keep_larger + dedup):

| metric | Foam A (exp1) | **Foam D (exp8)** | verdict |
|---|---|---|---|
| frame-0 bubbles | 142 | 26 | exp8 far fewer (small in frame) |
| reorganization-births | 1384 | 496 | |
| **reorg-births per real bubble** | **9.75** | **19.08** | **exp8 WORSE (≈2×)** |
| merges | 791 | 181 | |
| trusted bubbles / eligible | 80 / 142 | 6 / 26 | |
| **trusted fraction of eligible** | **0.56** | **0.23** | **exp8 WORSE** |
| **trackable area fraction (per-frame mean)** | **0.29** | **0.02** | **exp8 WORSE (≈14×)** |
| **near-edge trusted-bubble count** | **11** | **0** | **exp8 WORSE (none)** |
| stability gate | proceed | confounded | |

exp8 is worse on **every** trackability metric. Per-bubble churn is ~2× Foam A's,
only 2 % of foam area is reliably trackable, and there are **zero** trusted bubbles
near the edge. Radial-bin occupancy — Foam A `{0:11,1:47,2:29,3:20,4:17,5:19,6:3,7:3}`
vs Foam D `{3:2,4:3,7:1}` (6 trusted bubbles total).

## Conditional radial test on exp8 — NOT run
Per the pre-registered rule, the radial test is run only if exp8 is materially
cleaner. It is not (worse on all metrics; gate = confounded; 0 near-edge bubbles).
Forcing it would report a guaranteed-underpowered null as if it were physics.
**Finding: better rendering alone did not resolve the churn** — the radial
hypothesis remains untestable on this data.

## Side finding — Option 3 (keep_larger) meaningfully improved Foam A
Dr. Oh's confirmed merge rule (survivor = larger-AREA parent's ID) preserves the
big bubble's identity through merges, so large-bubble tracks stop breaking. On Foam
A this improved trackability vs the old `max` rule:

| Foam A | old `max` (prev session) | new `keep_larger` |
|---|---|---|
| trusted bubbles | 73 | **80** |
| near-edge bin | 3 | **11** |
| trackable area fraction | 0.15 | **0.29** |
| stability gate | underpowered | **proceed** |

**But even improved, Foam A's radial test is still a NULL:** Spearman
ρ(dA/dt, distance) = **+0.096**, 95 % CI **[−0.06, +0.24]** (covers 0); near−far
effect −0.34, CI [−0.75, +0.12] (covers 0); |ρ| < 0.22 undetectable at 95 %. No
radial gradient is detectable on Foam A, and it is still marginally underpowered.

## What this means for the radial hypothesis
Neither clearer rendering (exp8) nor the merge-ID fix (Foam A) makes the radial
gradient detectable. The bottleneck is **spatial resolution per bubble**: too few
pixels per bubble → watershed reorganization churn → the small/edge bubbles that
carry the signal are un-trackable (Foam A) or under-segmented (exp8). A powered
radial test needs **higher-magnification imaging** (more pixels per bubble) or a
segmentation method robust to small-pixel bubbles — not just a clearer render.
