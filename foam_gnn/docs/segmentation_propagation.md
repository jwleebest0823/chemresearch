# Identity-propagating segmentation — CORRECTED results

> ## ⚠ CORRECTION NOTICE (supersedes the original version of this document)
> The original headline of this document — **"trackable area 0.25 → 0.96 on Foam A,
> 0.69 on Foam C"** — was **WRONG and is retracted**. It was produced by a segmenter
> with a one-way ratchet defect: propagated markers progressively swallowed multiple
> real bubbles, and the metric that scored them (`seg_temporal`) *rewards* exactly that
> (a blob covering 20 bubbles is large, never dies, and hides its internal merges), so
> the defect and the metric were positively coupled. The old numbers measured **blob
> stability, not bubble coverage**. Full diagnosis: `docs/propagation_ratchet_defect.md`.
> The defective numbers are retained below, labelled, so the correction is explicit and
> auditable — they are **not** silently overwritten.

## What changed in the method (v1 → v2)
v1 propagated **geometry** (seeded frame *t+1* from frame *t*'s label map). That is a
ratchet: once a marker owned two bubbles nothing could split it, so under-segmentation
compounded monotonically (Foam A 385 → 104 bubbles while an independent per-frame
segmentation of the same frames found 219; one label swallowed up to **34** bubbles by
frame 12).

v2 propagates **identity onto geometry re-derived every frame**, under one invariant:
**every interior blob gets exactly one marker**. A marker cannot span two bubbles, so
swallowing is structurally impossible and splits happen automatically. Geometry splits
are ungated; only *identity* is gated (resurrect a dormant id → probation → mint), with
a hysteresis band so borderline films cannot oscillate. Probation **W = 2, measured**
(see the defect doc). The generous foam mask is tightened at both flooding *and* blob
decomposition, so labels no longer bleed onto background.

**The ratchet is gone**: region count / independent interior-blob count now stays at
**0.86–0.98** on every session (guard floor 0.60), and the counts track physical reality
— exp1_run0 359 → 178 (independent control: 359 → 180), and exp3 **rises** 1189 → 1433
(independent: 1189 → 1448) instead of falsely falling.

## Corrected metrics — and the control that decides the question
Three arms, same `seg_temporal` harness, identical strata. The **control** is the
pre-committed comparison: the *same* per-frame detection with **no identity propagation**,
tracked by the original Hungarian tracker. It isolates the identity layer.

### Foam A (exp1, both runs)
| arm | bubbles/frame | trackable area | reorg-birth rate | small×near-edge area | small×edge birth |
|---|---|---|---|---|---|
| v1 defective — **RETRACTED** | 134 | ~~0.961~~ | ~~0.003~~ | ~~0.912~~ | ~~0.013~~ |
| **v2 fixed** | 184 | **0.650** | 0.015 | **0.481** | 0.026 |
| independent + classic tracker (control) | 186 | **0.795** | 0.014 | **0.666** | 0.036 |

### Foam C (exp3 only — the session where the control was run)
| arm | bubbles/frame | trackable area | reorg-birth rate | small×near-edge area | small×edge birth |
|---|---|---|---|---|---|
| v1 defective — **RETRACTED** | 927 | ~~0.622~~ | ~~0.070~~ | ~~0.085~~ | ~~0.173~~ |
| **v2 fixed** | 1205 | **0.104** | **0.058** | 0.026 | **0.081** |
| independent + classic tracker (control) | 1294 | 0.110 | 0.226 | 0.018 | 0.381 |

(All five Foam C sessions pooled, v2: trackable area **0.053**, birth rate 0.057 — vs the
retracted 0.686.)

## Verdict — the pre-commitment fires
**Corrected propagation does NOT beat independent per-frame segmentation at matched
bubble counts. Stated plainly, as promised:**

* **Foam A — propagation LOSES.** At matched counts (184 vs 186), the control is better on
  trackable area (**0.795 vs 0.650**) and on the small×near-edge cell (**0.666 vs 0.481**),
  and the birth rates tie (0.014 vs 0.015). Propagation adds nothing here.
* **Foam C — propagation ties on coverage and wins only on churn.** Trackable area is a tie
  (0.104 vs 0.110), but the reorg-birth rate is **4× lower** (0.058 vs 0.226) and the
  small×near-edge birth rate **4.7× lower** (0.081 vs 0.381). So identity propagation does
  genuinely suppress churn on the dense foam — it just **does not convert that into more
  trackable bubbles**.

**Interpretation.** The identity layer was never the binding constraint; **detection is**.
Once geometry is re-derived honestly every frame, how you assign identities barely moves
the trackable-area number. This is the same conclusion the modeling gates reached from the
other direction, and it points squarely at candidate #2 in
`docs/segmentation_candidate_plan.md` — a **learned per-frame detector** (Cellpose /
StarDist) — rather than more tracking machinery.

**The project's bottleneck is unchanged and now honestly measured:** the small×near-edge
population is still largely untrackable — 0.48–0.67 on Foam A and **0.02–0.03 on the dense
Foam C**, nowhere near the ~0.96 the retracted numbers claimed.

## Knock-on effects on other results
* **`docs/exp10_10s_vonneumann.md` — the von Neumann conclusion is UNAFFECTED in
  direction.** That experiment compared 10 s vs 30 s-subsampled using the *same* method on
  both arms, so the sampling contrast was internally controlled; and its conclusion was a
  null (K wrong-signed at every horizon), which the ratchet does not manufacture. Its
  *trackability* numbers share the v1 defect and should be read as retracted.
* The Gate 1–3 modeling results used the **classic** tracker, not propagation, so they are
  untouched.

## Regression guard (so this cannot recur silently)
The interior-blob count is an independent per-frame bubble estimate already computed every
frame at zero cost. `segment_track_propagated` now tracks `n_regions / n_blobs_eligible`
each frame and **raises** when it stays below `collapse_guard_ratio` (0.60) for
`collapse_guard_patience` (3) frames. On the v1 defect this would have fired at frame ~12
on Foam A instead of being found by eye weeks later. Tests in `tests/test_propagate.py`
pin the invariant (no count collapse on a static sequence, ratio ≈ 1, guard fires).

**Artifacts:** `qc/seg_eval/{prop2,ctrl}_*.csv`, `v1_vs_v2_vs_independent.json`,
`qc/ratchet/*`. Drivers: `dev/seg_propagate_eval2.py`, `dev/ratchet_diagnose.py`,
`dev/measure_probation_w.py`.
