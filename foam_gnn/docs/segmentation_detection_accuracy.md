# Detection accuracy against ground truth — the first measured number

The project's **first ground-truth-validated segmentation accuracy**. Scored against 14
hand-labeled Foam A frames, Hungarian-matched per bubble, stratified by GT bubble size ×
distance-to-evaporation-edge.

## Scope — honest, and a finding in itself
**Foam A / exp1 only (14 frames).** The denser foams (exp3–exp7) could not be reliably
hand-labeled even at full zoom, so no ground truth exists for them and nothing here is
claimed about them. That limit is itself informative: **if a careful human cannot
segment those frames reliably, automated detection cannot be expected to do better
there**, and any accuracy claim at that density would be unfalsifiable. Five frames that
were opened and closed without correction are excluded (`inspected_not_corrected`) —
scoring against them would have graded the segmenter on its own output.

## What the first measurement found: Plateau borders scored as bubbles
The initial run gave **precision 0.347 / recall 1.000 / F1 0.515**. The shape of that
result was diagnostic: recall stayed ≈1.00 even at **IoU 0.9**, with split and merge
rates ≈0. So every real bubble was being found with near-exact boundaries; the entire
error was ~2 *spurious extra regions per real bubble*.

Visual inspection identified them as **Plateau borders** — the dark triangular
interstices where three bubbles meet. Mechanism: the Sato ridge filter responds to thin
*films* but not to fat interstices, so their interiors pass `film < interior_thresh` and
were emitted as bubbles. Discriminator (verified): a bubble interior is **gas — bright**
(median raw intensity 142–149); a Plateau border is **liquid — dark** (93–99). A
per-frame region-level intensity gate (`0.92 × Otsu` within the foam) rejects them.
Subtlety worth recording: gating the *interior mask* does not work (it only shrinks
blobs, which still get seeded, and costs recall), and neither does a *blob*-level test —
these regions grow from small **bright** specks, so only the post-watershed region is
liquid-dominated.

## Accuracy after the fix (pooled over the 14 frames)
| method | IoU | TP | FP | FN | precision | recall | **F1** |
|---|---|---|---|---|---|---|---|
| propagated | 0.50 | 943 | 89 | 123 | 0.914 | 0.885 | **0.899** |
| propagated | 0.75 | 941 | 91 | 125 | 0.912 | 0.883 | 0.897 |
| propagated | 0.90 | 937 | 95 | 129 | 0.908 | 0.879 | **0.893** |
| independent | 0.50 | 941 | 94 | 125 | 0.909 | 0.883 | 0.896 |
| independent | 0.90 | 937 | 98 | 129 | 0.905 | 0.879 | 0.892 |

F1 **0.515 → 0.899**. It barely degrades from IoU 0.5 to 0.9 (0.899 → 0.893), so matched
bubbles are matched *precisely* — boundary quality is not a limitation.
**Split and merge rates are 0.000 in every stratum**: the segmenter does not fragment or
fuse the bubbles it finds. Propagated ≈ independent (0.899 vs 0.896), consistent with the
earlier finding that the identity layer is not the binding constraint.

## THE NUMBER THAT MATTERS: recall by size × distance-to-edge
Recall at IoU ≥ 0.5 (rows = GT size tercile, cols = distance bin, **0 = near-edge**):

| size | near-edge | 1 | 2 | interior | n (GT bubbles) |
|---|---|---|---|---|---|
| **small** | **0.625** | 0.663 | 0.679 | 0.857 | 354 |
| medium | 1.000 | 1.000 | 1.000 | 1.000 | 356 |
| large | 1.000 | 1.000 | 1.000 | 1.000 | 356 |

**Stated plainly: detection is perfect for medium and large bubbles at every distance,
and misses ~37% of small near-edge bubbles** (recall 0.625) — rising to ~34% missed for
small bubbles overall. The failure is confined almost entirely to the *small* tercile,
and within it is worst at the evaporation edge, improving monotonically inward
(0.625 → 0.663 → 0.679 → 0.857).

This is precisely the population the project's physics depends on, and it is now
measured rather than assumed. It also bounds what the modeling stage can see: roughly a
third of small near-edge bubbles never enter the data at all, so any near-edge
conclusion inherits that censoring.

**Artifacts:** `qc/seg_eval/gt_{detection,stratified,splitmerge,frames}.csv`,
`gt_accuracy.json`, `gt_vs_fp_f000*.png`. Driver: `dev/run_seg_eval.py`.
