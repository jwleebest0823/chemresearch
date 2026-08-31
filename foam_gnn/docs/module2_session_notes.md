# Module 2 session — dataset representation, defect fixes, validation

Scope of this session (before the Module-3 gate): (A) represent the real dataset,
(B) fix three known defects, (C) validate on real consecutive frames. **No
modeling/graph code.** Everything below is reproducible from `dev/*.py` (scratch,
gitignored) against the real `data/` folders.

## A. Dataset structure — 3 foams, 7 sessions (`src/foam_gnn/dataset.py`)

`exp1..exp7` are **3 physically independent foams**:

| Foam | Folders | Frames | Image | Mag | Notes |
|---|---|---|---|---|---|
| A | exp1 | 198 | 1024×1280 JPG | M1 | two 99-frame runs split by a 2.5-min gap |
| B | exp2 | 103 | 1536×2048 TIF | ≠M1 | different USB camera; colour → grayscale |
| C | exp3–exp7 | 5×99 | 1024×1280 JPG | ≈M1 | ONE raft, 5 sessions over 10.7 h (2026-06-16) |

Foam C inter-session gaps: exp3→4 **39 min**, exp4→5 **9 min**, exp5→6 **51 min**,
exp6→7 **299 min**. Invariants (`FOAM_SESSIONS`, `leave_one_foam_out()`): CV unit =
foam (3 folds, C never split); tracking unit = session (never bridge a gap).

## B. Defects fixed

- **B3 — config can't represent the structure / crashes on exp2.** Per-experiment
  shape + extension now live in `dataset.EXPERIMENTS`; `io_utils.load_experiment_frames`
  shape-checks against the *correct* per-foam size. All 7 folders load, incl. exp2
  TIF → grayscale (1536×2048). *(Also fixed a blocking prerequisite: `cv2.imread`
  returns `None` on this repo's non-ASCII path `…\문서\…`; decoding now uses
  `np.fromfile` + `cv2.imdecode`.)*
- **B2 — `max_displacement_px` was a placeholder (25).** Measured the genuine
  frame-to-frame bubble drift on the 40-frame consecutive exp1 run (mutual-NN,
  drift-registered): **median 2.6 px, p90 11, p95 16, p99 49 (contaminated tail),
  inter-bubble spacing ~50 px.** Set **`max_displacement_px = 20`** (≈p95+margin,
  < ½ spacing). Sweep shows looser gates inflate T1 by admitting neighbour-jumps
  (T1: 28@20 → 153@64) while only marginally raising survival.
- **B1 — T1 detection rewritten.** Old code lumped all adjacency changes into one
  `T1_swap` via set symmetric-difference. New detector finds **individual,
  localized** swaps: a lost edge `{P,Q}` whose two common neighbours `{R,S}` form a
  gained edge, all four persisting; gated by `t1_min_border_px=5` and confirmed for
  `t1_confirm_frames=1`. One event per swap with the 4-bubble cluster centroid.
  `overlay_ids` / `overlay_events` provide visual audit. Deterministic unit tests
  on a synthetic canonical swap.

## C. Validation results (real consecutive exp1, 40 frames)

- **Coarsening (Foam C, Task 2):** count 315→35 across sessions, Spearman(time,
  count) = **−0.97**, Spearman(time, median-area) = **+0.76**; each session resumes
  near the previous session's end count → **one continuous foam** (not 5 fresh
  rafts).
- **Segmentation transfer (Task 4):** params transfer to **A & C**
  (Plateau-3way ≥94.5 %, `foam_frac` std 0.025 / 0.106, smooth counts) but **break
  on B** (`foam_frac` 0.10–0.88, count 33↔491; foam fills frame → no boundary;
  thick films shatter).
- **Tracking ID persistence (B2):** at md=20, **~80 %/frame** survival, surviving-
  bubble drift median 2.6 px / p95 15.6 px. Visual crops confirm **large bubbles
  keep stable IDs across consecutive frames**; churn is concentrated in small
  peripheral bubbles.

## What is validated vs NOT (read before Module 3)

**Validated**
- Temporal structure & 3-foam grouping (timestamps parse, gaps located).
- All 7 folders load with correct per-foam shape (incl. exp2 TIF).
- Genuine per-bubble displacement is small and well-characterized; `max_displacement_px`
  is now data-driven for Foam A.
- T1 detector identifies the canonical localized swap (unit-tested) and produces
  spatially-sensible, sparse T1s on real frames.
- Large/well-segmented bubbles track correctly frame-to-frame.

**NOT validated / most likely to break on the full set**
- **T2/birth rates are flicker-limited, not yet scientific.** Across all
  thresholds T2 ≈ birth (e.g. 934 ≈ 899 at md=20) — the signature of Module-1
  segmentation flicker (a small bubble blinking = 1 death + 1 birth), not real
  coarsening. ~20 %/frame churn is dominated by small-bubble (un)merging, not by
  the displacement gate. **Do not interpret raw T2 counts as T2/coalescence rates
  until segmentation is stabilized** (or deaths are filtered for non-reappearance).
- **T1 absolute rate** is a conservative lower bound; sensitive to segmentation
  stability and to `max_displacement_px`. Locations are trustworthy; the rate is not
  yet calibrated.
- **Foam B has no working segmentation** — needs its own regime (rescaled params
  and/or a learned backend); the distance-to-edge concept may not apply at B's
  magnification.
- `max_displacement_px=20` is **Foam-A-specific** (px, mag M1). Re-tune for B; C is
  same mag as A but unverified on consecutive C frames.
- Tracking validated on a 40-frame slice of exp1's first run only — not the full
  198 frames, not across exp1's internal gap, not on B/C consecutive runs.

## Hypothesis flags (recorded, NOT acted on)

- **Evaporation caveat.** Foam C may have low evaporation (small slide gap) → its
  radial depletion gradient may be **weak/absent** vs Foam A. Treat radial-gradient
  strength as a **per-foam hypothesis variable** in evaluation; do not pool A and C
  as sharing the same edge-depletion physics.
- **exp4→exp5 gap is only 9 min** (vs the ~75-min "full reorganization"
  assumption). Tracking stays per-session by construction, but this is the one C
  boundary where the raft may not have fully reorganized.
- **Foam B edge.** B may lack a usable foam edge entirely (foam fills the frame),
  so the radial hypothesis may be untestable on B.
