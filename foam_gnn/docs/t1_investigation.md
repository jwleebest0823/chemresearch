# The T1 famine was a detector artifact — a graph inconsistency, not physics

**Verdict: detector artifact.** The pipeline found **1 neighbour swap in 198 Foam A
frames**, which foam physics says is implausible. The cause is a specific inconsistency
introduced when the D2 repair landed, and fixing it yields **22** swaps from the same
frames with no threshold changed.

## The cause

`graph.py` was updated by D2 to use **gap-bridged** adjacency — each unlabelled pixel
within a per-frame scale-adaptive distance is assigned to its nearest label before
adjacency is measured, so two bubbles sharing a thin film count as neighbours. `⟨n⟩` rose
4.48 → 5.93 on the watershed as a result.

**`tracking.py`'s T1 pass was never updated.** It built its adjacency with the raw
`_adjacency_lengths`, on a graph known to under-count edges — and under Cellpose, 21–25%
of the foam interior carries no label at all, so films frequently have no pixel contact.

That matters far more for T1 than for `⟨n⟩`, because **a swap requires eight edge
conditions to resolve simultaneously**: `P–Q` present at *t* and gone at *t+1*, `R–S`
absent at *t* and present at *t+1*, plus `R` and `S` both being common neighbours of both
`P` and `Q` at *t*. A modest per-edge miss rate collapses an eight-way conjunction almost
to zero.

## Measurement (Foam A, both runs, 198 frames)

| setting | mean edges/frame | T1 swaps |
|---|---|---|
| **as shipped** (unbridged, `t1_min_border_px=5`) | 132.6 | **1** |
| **bridged, thresholds unchanged** ← now shipped | 156.3 | **22** |
| bridged, border ≥ 3 px | — | 35 |
| bridged, border ≥ 1 px | — | 60 |

**A 1.18× change in edge count produces a 22× change in swap count** — the signature of
the conjunction effect, and concentrated exactly where swaps live (the marginal-contact
regime, where a film shrinks to zero and a new one forms).

## What was shipped, and what was not

`# DECISION` — **shipped: the consistency fix only.** T1 detection now uses the same
bridged adjacency as the rest of the pipeline. This is not a threshold relaxation:
bridging is the already-validated D2 repair, structurally safe (nearest-label assignment
means an intervening bubble always blocks), and `t1_min_border_px` is untouched at 5.

`# DECISION` — **not shipped: the border-threshold relaxations** (35 swaps at 3 px, 60 at
1 px). They were measured and are reported above, but relaxing a flicker-rejection
threshold is exactly the kind of change this project has repeatedly rejected without
visual validation, and that validation was not achieved (below).

## The verification I did NOT achieve — stated plainly

The brief called hand-verification the decisive step, and I did not complete it.
Candidate overlays were rendered (`qc/t1/t1_candidates_exp1_run0.png`, 8 of 26 sampled,
lost pair in red and gained pair in green) but **at the rendering quality achieved the
four-bubble cluster is not separable by eye from its ~20 neighbours in the crop**, so I
could not confirm individual events or count false positives.

Consequently:

* **The recall improvement is not quantified against a hand-identified set.** "1 → 22" is
  a change in detector output, not a measured recall.
* **The false-positive rate of the 22 is unknown.** They may include segmentation flicker.
* **The T1 rate should not be published** — neither versus time nor versus bubble size —
  until it is.

What the evidence does support, and I think robustly, is the *diagnosis*: the near-total
absence was caused by searching for swaps on the wrong graph, and that is now consistent.

## Next step

Render tightly-cropped, per-cluster panels over *t−1…t+2* (a swap's signature is a
contact that persists, and a flicker's is one that does not), score 20–30 candidates by
eye, and report recall and false positives. Until then the count of 22 is a corrected
detector output, not a physical measurement.

## Blocked for Foams C and F

A swap needs four stable identities simultaneously. Foams C and F were rejected for event
analysis on identity churn (632 and 271 spurious identities;
`docs/topological_event_prediction.md`), so their T1 counts are blocked on the tracker,
not on this detector. Not forced.

---

## Verification tooling (session 2) — figures that can actually be scored

The first verification attempt failed because it showed only *t* and *t+1* on a crop
containing ~20 bystanders. **A one-frame flicker and a genuine swap are identical over two
frames**, so that figure could not answer its own question.

`dev/t1_verify_render.py` rebuilds it around that failure:

* **`t−1, t, t+1, t+2` as a strip.** The discriminating panel is the last one — a real
  swap's new contact *persists and grows*; a flicker's disappears.
* **Tight per-cluster crop**, `# DECISION` scale-adaptive: union bounding box of the four
  bubbles over all four frames, padded by 0.35 × the box diagonal, floor 25 px.
* **Colour by ROLE, not by label id** (`# DECISION`): P/Q warm (the pair that separates),
  R/S cool (the pair that joins), each a fixed colour held across all four panels so
  identity is eye-trackable. Everything else stays grey. Colouring by id would change
  between events and defeat the purpose.
* **The claimed edges drawn explicitly** between centroids — solid when the shared border
  clears `t1_min_border_px`, faint dotted when not — so the topological claim is visible
  rather than inferred.
* Border-length series for P–Q and R–S printed per panel and in the caption.

**Count correction.** The shipped tracker emits **22** T1 events on Foam A (17 in run0,
5 in run1), not the 24 quoted earlier. The 24 came from the diagnostic sweep, which did
not apply the `t1_confirm_frames` look-ahead that the shipped detector does. 22 is the
correct figure; the earlier number is superseded.

**Worked example (candidate #001, f004):** P–Q border runs `[16, 0, 0, 0]` px while R–S
runs `[0, 12, 30, 34]` px — the old contact breaks, the new one forms and then *grows*
over the following two frames. That is textbook T1 behaviour and is exactly the signature
the two-frame figure could not show.

**Also rendered: the events that exist only at looser thresholds** (`extra_mb3`,
`extra_mb1`, 16 sampled) into `looser_threshold_extras/`, clearly marked as NOT shipped.
If those score as genuine, the conservative threshold is costing real recall — a question
worth settling with evidence rather than by assuming the shipped setting is right.

**Scoring is deliberately not automated.** `qc/t1_verify/scoring.csv` carries the event
metadata and empty `verdict` / `notes` columns, with the criteria fixed in a header
comment so they cannot drift during scoring. `dev/t1_score_analyze.py` **refuses to run**
while any verdict is blank, keeps `unclear` out of the false-positive rate rather than
folding it into either bucket, and reports the rate with a Wilson interval plus — only
on verified-real shipped events — T1 rate versus time and swap-involvement versus bubble
size with cluster-bootstrap CIs.

**Until the sheet is scored, 22 remains a corrected detector output, not a physical
measurement, and the T1 rate is not publishable.**
