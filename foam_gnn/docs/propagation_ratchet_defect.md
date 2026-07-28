# Marker-propagation RATCHET defect — confirmation, characterization, and fix proposal

**Status: defect CONFIRMED. The headline "trackable area 0.25 → 0.96 on Foam A" is
invalid and is retracted pending the fix.** This document records the root cause, the
measured drift, and a design proposal for the split mechanism (Task 2) — *no fix is
implemented yet; awaiting review.*

---

## 1. Root cause — confirmed in code

The hypothesis is correct, and the mechanism is more specific than "merge errors
accumulate". There are **three** independent contributors, and **zero** reverse paths.

### 1a. The seeding skip is the primary accumulator
`_unseeded_blob_seeds` (propagate.py:107–123) labels the connected components of
`interior` (= filmless regions = candidate bubbles) and then:
```python
seeded_blobs = {int(v) for v in np.unique(lab[seed_markers > 0]) if v > 0}
...
if sl is None or blob in seeded_blobs:      # <-- ANY blob touched by ANY seed is skipped
    continue
```
If one propagated marker's warped footprint overlaps **N** distinct interior blobs, all N
are marked "seeded", so **N−1 real bubbles get no marker at all**. The watershed then
floods all N blobs from that single marker → one label spanning N bubbles. Next frame
that label's footprint is larger, so it captures still more blobs. **Compounding and
monotone by construction.**

### 1b. No split path exists anywhere
Audited every id-assigning site (propagate.py:111–122, 253, 296, 300–301, 318–335, 339).
`remap` (line 318) is a many→one map only. There is **no** code that divides an existing
id's territory, and — unlike the original `tracking.py` — **no resurrection/dormant-id
logic was ever ported** (`grep -i "resurrect|dormant"` → 0 hits). So `propagate.py` is
strictly *more* ratchet-prone than the tracker it replaced: `TrackConfig` has
`merge_resurrect_window`/`merge_ambiguous_frac` for exactly this, and propagation ignores them.

### 1c. Merge over-triggering feeds the ratchet irreversibly
The merge rule (lines 306–312) dissolves a border when `mean_film < merge_film_thresh
(0.12)` over ≥4 px. A **mean** is fragile: a border that is mostly a true ridge but dips
through one weak stretch averages below threshold and the two ids are fused **permanently**
(no un-merge). The threshold was never validated against ground truth.

---

## 2. Measured drift — every session, monotone, severe

Propagated count vs an **independent per-frame segmentation using the identical detection
machinery** (`_seed_frame0` + watershed, propagation removed). The gap isolates propagation
as the cause. Frame 0 agrees exactly by construction (coverage 1.00); all degradation is accumulated.

| session | propagated first → last | independent first → last | **coverage last** | slope | % steps non-increasing |
|---|---|---|---|---|---|
| exp1_run0 (Foam A) | 385 → **104** | 385 → 219 | **0.49** | −1.82 /frame | **95 %** |
| exp1_run1 (Foam A) | 203 → 48 | 203 → 99 | 0.78 | −1.01 /frame | **95 %** |
| exp3 (Foam C) | 1188 → 892 | 1188 → **1447** | 0.63 | −0.80 /frame | 63 % |
| exp4 | 1208 → 625 | 1208 → 918 | 0.66 | −5.64 /frame | 76 % |
| exp5 | 952 → 436 | 952 → 670 | 0.67 | −4.65 /frame | 72 % |
| exp6 | 452 → 99 | 452 → 261 | **0.40** | −3.42 /frame | 65 % |
| exp7 | 115 → 81 | 115 → 119 | 0.60 | −0.19 /frame | 62 % |

**Reproduces the report exactly**: exp1_run0 f049 propagated = **129** (user observed 129);
f097 ≈ 104–106 (user observed 106).

Two further findings from the figure (`qc/ratchet/ratchet_drift.png`):
- **exp3: the independent count *rises* (1188 → 1447) while propagated *falls* (→892).** The
  foam is being resolved into *more* bubbles over time, and propagation reports the opposite
  trend. This is not coarsening — it is the ratchet inverting the sign of a physical trend.
- **exp1_run0: propagated (104) decays to ≈ the classic h_maxima watershed (95)** — propagation
  ends up tracking no more bubbles than the *under-detecting* baseline it was built to beat,
  i.e. it discards precisely the small-bubble detection advantage that justified it.

### Label-level evidence (the smoking gun)
Re-propagating exp1 frames 0–49 and counting, per propagated label, how many independent
regions have ≥50 % of their area inside it:

| frame | propagated | independent | **max bubbles swallowed by ONE label** | labels swallowing ≥2 |
|---|---|---|---|---|
| f000 | 385 | 385 | 1 | 0 |
| f012 | 222 | 334 | **32** | 44 |
| f024 | 183 | 301 | 33 | 42 |
| f036 | 156 | 277 | **34** | 36 |
| f049 | 129 | 254 | 28 | 32 |

By **frame 12** a single label already covers **32 distinct bubbles** — worse than the
visual estimate of 15–20. The damage is immediate, not a slow late-run drift.

### Why the 0.96 metric was not merely noisy but *inflated*
`seg_temporal` scores an id as trusted when it persists with a continuous area and no merge.
A blob swallowing 20 bubbles is **maximally** favoured by that definition: it is large (so
relative area change is small), it never dies, and its constituent bubbles' merges happen
*inside* it, invisibly. **The defect and the metric are positively coupled** — the worse the
swallowing, the better the score. So "trackable area 0.96" measured blob stability, exactly as
suspected. It must be re-reported, not adjusted.

---

## 3. Boundary bleed — real, but modest and precisely bounded
Markers are already constrained to the foam (`raw_seed = where(interior, Lw, 0)`;
`interior ⊆ foam`). The bleed comes from the **flooding mask**: `watershed(..., mask=layers.foam)`
assigns *every* pixel of a foam mask that `compute_foam_mask` documents as "slightly generous".

Measured on exp1 f049: the foam mask extends **at most 11.2 px** beyond the outermost filled
interior; only 0.2 % of foam area lies beyond a 4 px margin. So it is a **thin rim, not large
regions** — visually obvious in napari but a small *area* effect. It matters because it
inflates **edge-bubble** areas and distorts `distance_to_evap_edge` — i.e. it corrupts exactly
the near-edge stratum this project depends on. (My first proxy reported 0.000 only because its
12 px dilation was calibrated just past an ≤11.2 px effect; corrected here rather than trusted.)

**Fix:** flood on `foam ∩ fill_holes(dilate(interior, r))` with `r ≈ 4–6 px` (a film half-width),
and drop label pixels outside it. Cheap, no new parameters of consequence.

---

## 4. PROPOSAL — the split mechanism (for review)

### 4.1 The invariant that removes the ratchet at the root
> **After seeding frame *t*, every interior blob contains exactly one marker.**

This is the *inverse* of the bug (which lets one marker own many blobs) and it makes the
ratchet structurally impossible rather than patched. Splitting then falls out for free: if
previous id *X* spans blobs B1 and B2, each is seeded separately, so the territory splits.
Per-blob id assignment by overlap with the warped previous labels:

| blob's overlap with warped previous ids | assignment |
|---|---|
| exactly one dominant id | that id — **identity preserved** (the whole point of propagation) |
| ≥2 ids overlap substantially | genuine **merge** → `keep_larger` + merge event; losers → dormant pool |
| none | **birth** — or **resurrection** if a dormant id matches (see 4.3) |
| one id spans ≥2 blobs | id keeps its best-overlap blob; **the others split off** (resurrect/new) |

Cost: essentially free — `interior` and its labeling are already computed each frame.

### 4.2 THE TRADEOFF: real split vs. flicker (the hard constraint)
Propagation exists to suppress spurious splits (~10–20 reorg-births/bubble). Splitting on a
*momentary* internal film — noise, illumination, a partially-formed film — reintroduces exactly
that failure. The asymmetry:

- **Missed split** → a blob swallows real bubbles → the current, catastrophic failure (silent,
  self-flattering in the metric).
- **Spurious split** → a new id → reorg-birth → churn (loud, visible in the existing metric).

**Key design insight — decouple geometry from identity.** These need *different* policies:

- **Geometry: split immediately, always.** Two blobs separated by film in *this* frame's image
  are two regions in this frame. Forcing them into one label is never more correct — it is what
  creates the swallowing blob. **No gating.** This alone fixes the count collapse.
- **Identity: commit conservatively.** Only the decision *"does the split-off region get its own
  bubble id?"* can generate churn, so gate only that:
  1. **Resurrection first (primary anti-churn mechanism).** A split-off region usually *had* an
     id before it was swallowed. Keep a dormant pool (id + pre-merge footprint) and reclaim by
     overlap. A reclaimed split mints **no new id at all**, so it costs **zero churn** — this is
     why I expect the churn penalty to be far smaller than the naive fear suggests. Port
     `merge_resurrect_window` / `merge_ambiguous_frac` from `tracking.py` (already tuned on this data).
  2. **Probation `W` (secondary).** When no dormant id matches, hold the split-off region on a
     *provisional* id linked to its parent for `W` frames; commit a genuinely new id only if the
     separation survives `W` frames. Flicker lasting 1 frame therefore costs nothing.
  3. **Hysteresis, not a single threshold.** Merge requires `film < θ_lo` (0.12); a split requires
     the separating ridge `> θ_hi` with `θ_hi > θ_lo`. **Without a gap, a border sitting near the
     threshold would merge and split alternately forever** — an oscillation the current
     single-threshold design would be vulnerable to the moment splitting is enabled.
  4. **Size floor** — both parts ≥ `new_seed_min_area_px` (knob already exists).

**Setting `W` from data, not assumption — MEASURED (result).**
`dev/measure_probation_w.py` runs the v2 segmenter on Foam A (exp1, 99 frames) with probation
set impossibly high, so nothing commits and every candidate separation runs until it either
collapses back (spurious) or survives to the end (real):

* **526 candidate separations** → **430 collapsed back**, **96 persisted (18 %, real)**.
* Spurious durations are **bimodal**: a flicker spike at 1–2 frames (**33 % last exactly 1
  frame, 43.7 % ≤ 2**) plus a long tail (median 5, p90 38, max 92 frames).
* Rejection vs W: **W=1 → 33 %, W=2 → 43.7 %**, W=3 → 47 %, W=5 → 50 %, W=8 → 55 %.

**W = 2** (measured). It captures the flicker spike, and returns collapse hard beyond it —
W=8 buys only 11 more points while deferring *every real split* by 8 frames. The long tail is
not flicker and probation should not try to reject it: those are transient-but-real bubbles
that merge away later, and they are handled by the merge/resurrection machinery instead.
Reassuringly this lands on the same value, by the same method, as
`TrackConfig.merge_resurrect_window = 2` (44 % of merge-flickers last 1 frame, 69 % ≤ 2).

### 4.3 Rejected / deferred alternatives
- **Reconcile against a second, independent per-frame segmentation.** Sound, and it is the
  reference I used for diagnosis — but ~2× compute, and **largely redundant**: `interior` blobs
  *are* the independent evidence (a blob is by definition a region enclosed by film). Deferred
  as a fallback if flicker proves worse than measured.
- **Detect internal film ridges within a region.** This is the same signal as 4.1 but measured
  less robustly (a partial ridge that doesn't span would split falsely). The blob decomposition
  already encodes "is there a film all the way across?" correctly.
- **Fix only the merge threshold.** Would slow the ratchet but not remove it — 1a operates even
  with merging disabled entirely.

### 4.4 Recommendation
Implement **4.1 (one-marker-per-blob invariant) + resurrection + probation `W`=2 (measured) +
hysteresis + size floor**, plus the **tight flood mask** (§3). This removes the ratchet
structurally, keeps identity persistence (the reason propagation exists), and bounds the churn
reintroduction by making most splits *reclaim* rather than *mint* ids.

**Honest expectation, pre-committed:** the corrected trackable-area number **will fall
substantially** from 0.96 — that headline was measuring blobs. Churn will rise somewhat. The
decisive question then becomes whether corrected propagation still beats the **independent
per-frame** segmentation on temporal stability at *matched* bubble counts. **If it does not, the
honest conclusion is that marker propagation is not the answer and candidate #2 (a learned
per-frame detector) becomes the path.** I will report whichever holds; I will not tune toward a
favourable number.

---

## 5. Regression guard (Task 5) — free and always-on
The interior-blob count is an **independent per-frame bubble estimate that is already computed
every frame at zero extra cost**. Guard: track `n_prop / n_interior_blobs` per frame and fail
loud when it falls below a floor (e.g. 0.6) or declines monotonically over a window. This exact
check would have caught the defect at frame ~12 on Foam A instead of by eye weeks later. It
belongs inside `segment_track_propagated` (raising/warning) and as a reported diagnostic.

---

## 6. What happens to affected results
- `docs/segmentation_propagation.md` — the 0.96 / 0.69 trackability numbers are **retracted**;
  the document will be updated in place with the defect, cause, fix, and corrected metrics
  side-by-side with the old ones (not silently overwritten).
- `docs/exp10_10s_vonneumann.md` — the **von Neumann conclusion is unaffected in direction**: it
  compared 10 s vs 30 s-subsampled using the *same* (defective) method on both arms, so the
  sampling contrast is internally controlled. But its Task-2 trackability numbers share the
  defect and will be re-reported. I will re-run the K-fit on corrected tracks to confirm.
- Ground-truth preseeds will be regenerated **after** the fix (`eval/exp1/f000`, `f001` already
  hand-corrected — those masks will **not** be touched).

---

## 7. OUTCOME (implemented and measured — §4 was approved)
The fix is implemented in `foam_gnn.propagate` (v2). **The ratchet is gone**: the region /
independent-blob ratio now holds at **0.86–0.98** on every session (guard floor 0.60), and
counts track physical reality (exp3 now *rises* 1189 → 1433, matching the independent
1189 → 1448, instead of falsely collapsing).

Three findings worth recording, two of them surfaced only by testing:

1. **Frame 0 had to obey the invariant too.** Seeding frame 0 differently (h_maxima +
   unseeded blobs) left it under-segmented relative to its own blobs, and the invariant
   then correctly but noisily split that apart over the following frames — a transient
   storm of "births" that was an artifact of the inconsistent frame-0 rule.
2. **`interior` had to be tightened, not just the flood mask.** `interior = (film < θ) &
   foam` and the generous foam mask's flat background rim is film-free, so it registered as
   an interior blob and was seeded as a fresh "bubble" every frame. Masking at blob
   decomposition fixes the bleed at its source.
3. **Disappearance had to become reversible.** Originally only merge-losers went dormant, so
   a bubble that momentarily failed to resolve died permanently and had to mint a new id on
   return — churn of exactly the kind this design exists to avoid. Vanished ids now go
   dormant and their death is committed only after `resurrect_window`.

**And the pre-commitment fired: corrected propagation does NOT beat independent per-frame
segmentation at matched bubble counts.** On Foam A it loses (trackable area 0.650 vs
**0.795**; small×near-edge 0.481 vs **0.666**); on Foam C it ties on coverage (0.104 vs
0.110) and wins only on churn (birth rate 0.058 vs 0.226). **The identity layer was not the
binding constraint — detection is.** Full corrected tables and the interpretation are in
`docs/segmentation_propagation.md`; the next move is candidate #2 (a learned per-frame
detector), not more tracking machinery.
