# Segmentation baseline — the bottleneck, finally measured (Task 3)

The first **quantified, stratified** measurement of how badly the current watershed
segmentation tracks bubbles, by size × distance-to-edge, across Foam A and Foam C.
Computed with `foam_gnn.seg_temporal` on all frames (no ground truth needed). This is
the number every future method must beat.

## Headline (foam-level)
| | Foam A (exp1×2 runs) | Foam C (exp3–exp7) |
|---|---|---|
| trackable **area** fraction | **0.25** | **0.024** |
| trusted fraction (count) | 0.30 | 0.029 |
| reorganization-birth rate (per bubble-frame) | 0.16 | 0.36 |
| **reorg-origin fraction** (bubble-frames that are churn artifacts) | **0.67** | **0.94** |

On Foam C — the dense foam — **97.6% of bubble area is untrackable** and **94% of all
bubble-frames are reorganization artifacts**. On Foam A a quarter of the area is
trackable. These are brutal and they have never been measured before.

## Stratified — reorganization-birth rate (per bubble-frame; higher = worse)
Rows = size (area terciles), cols = distance bin (0 = near-edge → 3 = interior).

**Foam A**
| size | near-edge | 1 | 2 | interior |
|---|---|---|---|---|
| small | **0.27** | 0.27 | 0.23 | 0.23 |
| medium | 0.18 | 0.13 | 0.16 | 0.10 |
| large | 0.065 | 0.034 | 0.058 | 0.04 |

**Foam C**
| size | near-edge | 1 | 2 | interior |
|---|---|---|---|---|
| small | **0.58** | 0.63 | 0.63 | 0.63 |
| medium | 0.32 | 0.31 | 0.32 | 0.24 |
| large | 0.19 | 0.15 | 0.13 | 0.10 |

The dominant axis is **size**: small-bubble identity churns ~5× faster than large on
Foam A (0.27 vs 0.05) and **~0.6 births per bubble-frame on Foam C** — i.e. a small
Foam-C bubble is re-minted as a *new id* in the majority of frames it appears. Small
bubbles are essentially untrackable, catastrophically so on the dense foam.

## Stratified — trackable area fraction (higher = better)
**Foam A**
| size | near-edge | 1 | 2 | interior |
|---|---|---|---|---|
| small | 0.27 | 0.37 | 0.38 | **0.67** |
| medium | 0.35 | 0.34 | 0.33 | **0.83** |
| large | 0.16 | 0.20 | 0.27 | 0.13 |

**Foam C**: 0.01–0.06 in *every* cell — nothing is reliably trackable.

Two gradients on Foam A: (1) within each size, coverage **collapses toward the edge**
(small 0.67 interior → 0.27 near-edge; medium 0.83 → 0.35); (2) **large bubbles are
poorly tracked everywhere** (0.13–0.27) — they are the actively-coalescing coarsened
bubbles the no-merge/area-continuity filter excludes.

## What the trackable slice actually is (the key insight)
The ~25% of Foam A (and ~2% of Foam C) that *is* trackable is the **small/medium
INTERIOR, quiescent** population. Both physics-bearing populations are lost:
- **large, coalescing** bubbles → excluded (merges break identity), and
- **small, near-edge** bubbles → churned into reorganization births (rate 0.27 on A,
  0.58 on C).

This is exactly why Gates 1–3 found no signal: coarsening lives in the large-coalescing
and small-near-edge bubbles, and current segmentation can follow neither. The bottleneck
is now measured, stratified, and unambiguous.

## Ground-truth (per-frame) metrics — harness ready, awaiting labels
`foam_gnn.seg_eval` (Hungarian per-bubble precision/recall/F1 at IoU 0.5/0.75/0.9,
IoU distribution, Plateau-vs-GT, split/merge — all stratified by size × edge-distance)
is implemented and unit-tested on synthetic GT with known errors, but **no per-frame
accuracy number is reported yet because no ground truth exists**. Once the ~16 labeled
frames land (see `docs/groundtruth_labeling.md`), the GT metrics validate that the churn
above is real detection failure (splits/merges on small near-edge bubbles) rather than a
tracking artifact. Until then, per-frame accuracy remains **unvalidated** — as it always
has been; that gap is now closable, not hidden.

## The target for any new method
Raise the **`(small, near-edge)` trackable-area fraction** and drive down its
**reorg-birth rate**, on **both** foams, measured on this exact harness under
leave-one-foam-out — without sacrificing the interior. Current baseline to beat:
- Foam A `(small, near-edge)`: trackable-area **0.27**, birth-rate **0.27**;
- Foam C `(small, near-edge)`: trackable-area **0.03**, birth-rate **0.58**.

**Figure:** `qc/seg_eval/seg_baseline.png`. **Artifacts:** `qc/seg_eval/coverage_*.csv`,
`birth_*.csv`, `frame0_coverage_*.csv`, `seg_baseline_summary.json`.
