# Temporal marker-propagation watershed — result vs the Task-3 baseline

Candidate method #1 from `docs/segmentation_candidate_plan.md`, built in
`foam_gnn.propagate` and evaluated on the **same** `seg_temporal` harness as the
baseline, stratified by size × edge-distance. Predicts nothing new per-frame; it
makes segmentation **temporally coupled** so a bubble's identity persists by
construction.

## Headline (foam-level, before → after)
| metric | Foam A | Foam C |
|---|---|---|
| trackable **area** fraction | 0.25 → **0.96** | 0.024 → **0.69** |
| trusted fraction (count) | 0.30 → 0.93 | 0.029 → 0.37 |
| reorg-origin fraction | 0.67 → **0.03** | 0.94 → 0.55 |
| reorg-birth rate (per bubble-frame) | 0.16 → **0.003** | 0.36 → **0.057** |

## The number that mattered — the (small, near-edge) cell
| | Foam A | Foam C |
|---|---|---|
| trackable area  (small, near-edge) | 0.27 → **0.96** | 0.03 → **0.45** |
| reorg-birth rate (small, near-edge) | 0.27 → **0.006** | 0.58 → **0.067** |

The target stratum — small bubbles at the evaporation edge, previously all but
untrackable — improves ~3.5× on Foam A (now essentially fully trackable) and ~15× on
Foam C. The reorganization-birth rate there falls ~45× (A) and ~9× (C): small
near-edge bubbles are no longer re-minted as new ids in most frames.

## Stratified trackable-area fraction (after; rows=size, cols=dist, 0=near-edge)
**Foam A** — near-complete everywhere:
| size | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| small | 0.96 | 0.94 | 0.92 | 0.93 |
| medium | 0.97 | 0.96 | 0.94 | 0.95 |
| large | 0.95 | 0.99 | 0.94 | 0.98 |

**Foam C** — large gains, but small bubbles lag:
| size | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| small | 0.45 | 0.45 | 0.43 | 0.45 |
| medium | 0.84 | 0.92 | 0.92 | 0.92 |
| large | 0.87 | 0.83 | 0.63 | 0.61 |

## Why it works (mechanism)
Each persistent bubble contributes **one marker carrying its own id** (seeded from the
previous frame's stable-ID map, warped by the measured drift), so it **cannot split**
into two ids or **be re-minted** — the two spurious events that produced the churn. The
two genuine changes are still allowed: a **merge** is detected post-watershed when the
shared boundary between two established bubbles loses its film ridge (dissolve, keep the
larger id); a **disappearance** is a bubble whose interior collapses below the seed
floor. **Adaptive blob seeding** (one seed per interior connected-component lacking a
seed) detects the small bubbles a single global `h_maxima` misses — verified visually on
Foam A frame 0: the propagated segmentation traces nearly every visible bubble (385 vs
the baseline's 142) while preserving the large bubbles (max area 8876 vs 9086).

## Honest caveats — what this does and does NOT establish
1. **Temporal stability ≠ per-frame correctness.** Propagation makes ids persist *by
   construction*, so the stability filter now passes most bubbles — that is the intended
   mechanism, but "stably tracked" can include "stably *mis*-tracked" (an id slowly
   bleeding onto a neighbour would not be caught by the churn metric). The Foam-A frame-0
   QC confirms real small-bubble **detection**, and the topology counts are physical
   (Foam A coarsens: 385 → ~222 bubbles over the run). But **per-frame accuracy is not
   yet GT-validated** — that is exactly what `seg_eval` + the ~30 labeled frames are for.
   These coverage gains are "trackable-by-the-filter," strongly suggestive, not
   GT-confirmed. **Do not yet rebuild the physics analysis on these tracks.**
2. **Foam C is improved but not solved.** 69% of area is now trackable (from 2.4%), but
   small bubbles there still flicker: `exp3` shows ~6390 births and ~4600 disappearances
   over 99 frames (small bubbles blinking in/out of interior detection → birth+death
   pairs, not id splits). Small-bubble coverage is 0.45 vs 0.9+ for medium/large, and
   reorg-origin fraction is still 0.55. The dense, fast-coarsening foam needs more —
   likely the learned per-frame detector (candidate #2, Cellpose/StarDist) feeding the
   same propagation loop.
3. **Cost:** ~5–8 s/frame (re-segments from images), comparable to the baseline
   segmentation; sequential by construction.

## Verdict & next step
Marker propagation **decisively attacks the measured failure**: on Foam A it nearly
eliminates the temporal churn and makes the small near-edge population trackable for the
first time (0.27 → 0.96 area, birth rate 0.27 → 0.006); on Foam C it is a large but
partial win. This clears candidate #1 with a real, stratified improvement — *pending GT
validation* that the newly-trackable small near-edge bubbles are physically correct.
Recommended next: (a) once the labeled frames land, run `seg_eval` to confirm per-frame
precision/recall on the small near-edge stratum and quantify any stable mis-tracking;
(b) address Foam C small-bubble detection flicker (candidate #2).

**Figure/artifacts:** `qc/seg_eval/prop_coverage_*.csv`, `prop_birth_*.csv`,
`prop_vs_baseline.json`, `frame0_{baseline,propagated}.png`. Driver:
`dev/seg_propagate_eval.py`.
