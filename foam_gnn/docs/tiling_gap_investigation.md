# The tiling gap is not a defect — Cellpose's ⟨n⟩ already matches ground truth

**Result up front: there is nothing to repair, and the repair would do harm.** Measured
against the 14 hand-labelled GT frames, Cellpose's neighbour count is correct to within
+0.03; the *watershed* is the one that disagrees with truth, by +0.60. The requested
expansion was implemented and put through the dual constraint anyway — it fails both
arms decisively.

## The ⟨n⟩ table across three foams, before and after — the criterion asked for

| foam | ⟨n⟩ before | ⟨n⟩ after | n₀ before | n₀ after | unlabelled before | after |
|---|---|---|---|---|---|---|
| A | 5.03 | *not applied* | 5.56 / 5.62 / 5.81 | *not applied* | 22.3% | *not applied* |
| C | 5.41 | *not applied* | 4.86 / 4.97 / 5.39 | *not applied* | 21.6% | *not applied* |
| F | 4.27 | *not applied* | 3.28 / 3.31 / 2.68 | *not applied* | 48.2% | *not applied* |

**The "after" column is deliberately empty: the fix was rejected at validation and not
shipped, so re-running the three-foam K analysis would report a change that should not
be made.** The evidence follows.

## 1. What "correctly tiled" actually looks like — the GT itself

The premise was that Cellpose's 22.3% unlabelled interior is too high because the
watershed manages 12.4%. That assumed the watershed is the reference. It is not — the
hand-labelled masks are, and they say:

| source | unlabelled foam interior (14 frames) |
|---|---|
| **hand-labelled GT** | **25.3%** |
| Cellpose | 20.9% |
| Cellpose, expanded | 12.6% |
| watershed | 12.4% |

**A quarter of the foam interior genuinely is not bubble** — it is film and Plateau
border, and a human labeller marks it as such. Cellpose at 20.9% is already slightly
*over*-labelled relative to truth. **The watershed's 12.4% is the anomaly**: it floods
the whole foam mask, so every region absorbs half the film beside it.

## 2. ⟨n⟩ measured on ground truth, identical frames, identical adjacency

Per-frame scale-adaptive bridging (`bridge_distance_px`), `min_shared_border_px = 3`,
bubbles split into interior (whole bubble further than one median radius from the raft
perimeter) and edge:

| source | ⟨n⟩ all | ⟨n⟩ interior | ⟨n⟩ edge | vs GT (all / interior) |
|---|---|---|---|---|
| **GT** | **5.08** | **5.66** | 4.05 | — |
| **Cellpose** | **5.11** | **5.76** | 4.00 | **+0.03 / +0.10** |
| Cellpose, expanded | 5.32 | 5.82 | 4.49 | +0.24 / +0.16 |
| watershed | 5.67 | 5.71 | — | **+0.60** / +0.09 |

**Cellpose reproduces the ground-truth neighbour count to +0.03.** There is no
under-count. The watershed's +0.60 population excess is concentrated entirely in **edge
bubbles** — flooding the foam mask extends perimeter regions outward until their rims
touch each other, manufacturing neighbours the labeller does not see. Expansion moves
Cellpose *away* from truth (+0.03 → +0.24), in the same direction and for the same
reason.

### Why ⟨n⟩ = 6 was the wrong target

Euler's ⟨n⟩ → 6 holds for an **infinite or periodic** 2D tiling. These foams are finite
rafts with a free perimeter, and **~32% of bubbles sit on that perimeter with ⟨n⟩ ≈ 4**.
The ground truth's own population value is 5.08, and its interior value 5.66. A
detector that reported ⟨n⟩ = 6 on this data would be wrong.

`# DECISION` — **the validation target for ⟨n⟩ should be the ground-truth value
(5.08 population / 5.66 interior), not 6.** Every previous use of "⟨n⟩ → 6" as a
success criterion on Foam A, including D2's, was measuring against a value this data
cannot attain.

## 3. The dual constraint — the expansion fails both arms

`cellpose_backend.expand_to_foam_mask` uses Cellpose instances as watershed markers and
floods the unlabelled interior over the Sato film ridge, confined to a tight hull of the
instances. It is structurally safe in the sense the brief required (a marker's basin
always separates two non-neighbours, no tuned distance anywhere) — and it still fails:

| | F1@0.5 | F1@0.75 | **F1@0.9** | median area ratio vs GT |
|---|---|---|---|---|
| Cellpose | **0.9664** | 0.8580 | **0.5393** | 1.082 |
| Cellpose, expanded | **0.8503** | 0.5998 | **0.2111** | 1.186 |
| change | **−0.1161** | −0.2582 | **−0.3282** | worse |

* **Arm 1 — detection accuracy must not regress: FAILS.** F1@0.5 drops 0.116, far
  outside anything attributable to noise.
* **Arm 2 — ⟨n⟩ and n₀ must move toward truth together: FAILS.** ⟨n⟩ moves *away* from
  the GT value.
* F1@0.9 collapses by 0.33 and the median area ratio rises from 1.082 to 1.186 —
  exactly the area inflation the brief predicted would show up at high IoU. **Areas
  feed dA/dt directly**, so this alone disqualifies it.

No parameter sweep is reported because none is warranted: the method is directionally
wrong, not mis-tuned. Sweeping it would be looking for a window in which a fix that
moves away from ground truth happens to look acceptable.

## 4. What this retracts, and what it means for K

**Retracted from `docs/cellpose_replication_v2.md`:**

> "every Cellpose K in this document is biased *downward* by an unquantified amount"
> — and the framing of the ⟨n⟩ difference as a Cellpose "under-count" or "deficit".

**The correction runs the other way.** Since Cellpose matches GT on ⟨n⟩ (+0.03) while
the watershed exceeds it (+0.60), and D2 established that raising ⟨n⟩ raises K by ~40%,
**the watershed's Foam A K of +0.483 is the number more likely inflated, and Cellpose's
+0.367 is the better-grounded estimate.** The "detector effect" of 0.736 should be read
as the watershed being *high*, not Cellpose being *low*.

This also puts a caveat on D2: its ⟨n⟩ 4.48 → 5.93 was validated as movement toward 6,
but GT-interior is 5.66, so D2's bridging appears to over-shoot modestly on interior
bubbles and substantially at the population level. D2's other repairs (robust estimator,
dropout filter, out-of-sample testing) are untouched by this.

**Foam F is a different problem, not this one.** Its 48.2% unlabelled interior is roughly
double the GT figure, so unlike Foams A and C it plausibly *does* have missing detections
— but that is **under-detection, not under-tiling**, and flooding its voids would inflate
neighbouring areas rather than find the missing bubbles. Foam F's n₀ of 2.7–3.3 remains
unexplained and it remains the least trustworthy foam.

## 5. Scope

* GT exists only for Foam A. The ⟨n⟩ calibration above is measured there and *assumed*
  to carry to Foams C and F, which have no ground truth. Foam C's only labels are
  deletion-derived and cannot score a non-watershed detector.
* Four GT frames were used for the watershed arm (it must be re-segmented per frame);
  all 14 for the GT/Cellpose/expanded arms.
* `expand_to_foam_mask` is kept in the codebase, unused by the pipeline and documented
  as rejected, so the measurement that rejected it can be reproduced.

## Reproducing

`python dev/tiling_gap_validate.py` → `qc/tiling/`.

**GT masks untouched — SHA-256 verified.**
