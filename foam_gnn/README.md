# foam_gnn

Physics-informed **Graph Neural Network** pipeline for modelling the evolution of
a **quasi-2D evaporating soap foam** (brightfield microscopy, ~30 s/frame).

> This project is **self-contained**: it has its own dependencies, tests and
> packaging and can be copied out into a standalone repository with no changes.

---

## Results — start here

The pipeline has been run end to end and the findings are written up for review. Read
these before the sections below, which are reference material on how the pipeline works.

| Document | Covers |
|---|---|
| [`results_package/SUMMARY.md`](results_package/SUMMARY.md) | Main results: von Neumann's law across three foams, the five measurement artifacts, ground-truth validation, limitations |
| [`results_package/METHODS_BRIEF.md`](results_package/METHODS_BRIEF.md) | Methods behind those numbers |
| [`results_package_extra/T1_ADDENDUM.md`](results_package_extra/T1_ADDENDUM.md) | Neighbour-swap (T1) detection and its hand-validation |

**Headline.** Von Neumann's law (`dA/dt = K(n − 6)`) **holds on all three usable foams
under a single detector**: K is positive with its 95% CI clear of zero in all nine
foam × horizon cells, and on Foam A K varies by only 1.02× across a twentyfold change in
prediction horizon.

**The part worth publishing is why it looked like it failed.** Five measurement artifacts
each faked a failure — a propagation ratchet, Plateau borders counted as bubbles, a
foam-mask threshold cliff, leverage (1.2% of measurements carrying 48% of the fit weight
and flipping K's sign), and a model trained on data that had since been rejected. One of
them produced K = −1.74. All five were caught by checks that did not depend on the answer
coming out right. See `docs/correctness_audit.md` and `results_package/SUMMARY.md` §2.

**Detector accuracy against 14 hand-labelled Foam A frames (~1,000 bubbles):** Cellpose
F1 **0.966** (precision 0.989, recall 0.945) vs. the tuned watershed's **0.903**. Cellpose
reproduces the hand-labelled mean neighbour count to within 0.03; the watershed
over-counts by 0.60, all of it at the raft edge. The ground truth's own population mean is
**⟨n⟩ = 5.08** — so the familiar `⟨n⟩ → 6` (Euler's theorem for an *infinite* tiling) is
the wrong success criterion for a finite raft with a free perimeter, and an earlier claim
of ours that used it has been retracted.

**Neighbour swaps (T1).** The pipeline was finding 1 swap in 198 frames — implausible.
Cause was an internal inconsistency (the swap search used a neighbour graph without the
gap-bridging repair applied everywhere else); fixing it raised detection 24×. All 22
shipped events were then **hand-scored one at a time against four-panel figures: 0 flicker,
0 unclear, 22 confirmed, false-positive rate 0/22, 95% CI [0%, 14.9%]**.

**The neural network does not beat physics.** Across nine held-out-foam cells the graph
network never beat the best simple baseline and was significantly worse in seven; the von
Neumann law was the best model in eight of nine. Reading: for this target `n` appears to
be a sufficient statistic for the graph structure, so topology is redundant by
construction.

**A methodological warning that generalises.** A clean count curve does not imply a clean
identity stream: all three foams lose bubbles smoothly (ρ = −0.995 to −0.9993) and pass
the fragmentation guard, yet Foam F creates **271 new identities from 62 starting
bubbles**. Count-based checks verify how many objects exist, never whether they are the
same objects.

---

## Scientific context

A soap foam confined between two glass slides loses liquid **only by evaporation
at the open circumference** (no drainage). The working hypothesis is that
depletion is **non-uniform** — drier at the edge, wetter at the centre — so
coarsening and film-rupture should vary monotonically with **distance from the
foam edge**.

The pipeline is built to compute and test against the relevant physics:

- **von Neumann's law** (dry-foam baseline): `dA/dt = K(n − 6)`.
- **Plateau's laws**: films meet 3-at-a-time at ~120° (used as a segmentation /
  graph sanity check).
- **Coarsening scaling**: `⟨R⟩ ∝ t^β` (β fit globally and vs. distance-to-edge).
- **Topological events**: T1 (neighbour swap), T2 / coalescence (bubble lost).

### What this model does **not** claim
- No film **thickness** (brightfield B/W → no interferometry → not measurable).
- No **absolute surfactant concentration** (no ground truth). The validatable
  target is **film-rupture risk / coarsening dynamics**, treated as a proxy.

---

## Dataset structure — 5 independent foams, not 9 experiments

The on-disk folders `exp1`…`exp9` are **5 physically independent foams**. This is
authoritative in [`foam_gnn.dataset`](src/foam_gnn/dataset.py) (`FOAM_SESSIONS`,
`EXPERIMENTS`), the single source of truth for both CV folds and tracking segments.
Each foam is its own leave-one-foam-out fold.

| Foam | Folders | Frames | Image | Mag | Notes |
|---|---|---|---|---|---|
| **A** | `exp1` | 198 | 1024×1280 JPG | M1 | B/W; two 99-frame runs split by a 2.5-min gap |
| **B** | `exp2` | 103 | **1536×2048 TIF** | ≠M1 | different USB camera; non-physical colour → grayscale |
| **C** | `exp3`–`exp7` | 5×99 | 1024×1280 JPG | ≈M1 | **ONE raft**, 5 sessions over ~10.7 h on 2026-06-16 |
| **D** | `exp8` | 99 | 1024×1280 JPG | low | foam fills only ~6% of frame → few px/bubble → *more* churn; see `docs/exp8_diagnostic.md` |
| **E** | `exp9` | 99 | 1024×1280 JPG | high | foam fills ~50% but **coarse** (~34 large bubbles); needs `h_maxima≈8`; worst churn/bubble, 0 near-edge trusted; see `docs/exp9_diagnostic.md` |

**Two invariants enforced by `foam_gnn.dataset`:**
- **CV unit = foam.** Leave-one-foam-out = 3 folds (A, B, C) via
  `leave_one_foam_out()`. Foam C's five folders must **never** split across
  train/test — same raft re-imaged ⇒ leakage by construction.
- **Tracking unit = session.** Each folder is tracked internally only; bubbles
  are never matched across an inter-session gap (the raft fully reorganizes).
  Sessions share a common real-time axis from parsed filename timestamps so
  long-timescale coarsening across C stays measurable.

Filename timestamps: `YYMMDDHHMMSS`+3 (15-digit; A, C) or `YYYYMMDDHHMMSS`+3
(17-digit; B). Parsed by `dataset.parse_timestamp`.

Other invariants: stored 3-ch but **effectively grayscale** (colour = non-physical
cast, discarded); low contrast with a periodic **~18.3 px grid** suppressed before
segmentation (Foam A/C only); **no µm/px** (areas in px², rates in px²/frame).

> **Per-foam segmentation does not transfer for free.** Module-1 params (tuned on
> Foam A) carry to Foam C (same M1, foam-on-background) but **break on Foam B**:
> at B's magnification the foam fills the frame (no background → distance-to-edge
> boundary is undefined) and the thick films shatter. See the Module-2 session
> notes; Foam B needs its own segmentation regime.

> **Unicode paths:** this repo lives under a non-ASCII path; `cv2.imread` cannot
> open such files (returns `None`). `io_utils` decodes via `np.fromfile` +
> `cv2.imdecode`, which is unicode-safe and also reads the Foam B TIFs.

---

## Install

```bash
# base data pipeline (Modules 1–3) — no deep-learning stack needed
pip install -e .

# model + training stack (Modules 4–6)
pip install -e ".[ml]"      # local
# on Colab, install torch/PyG from CUDA-matched wheels — see requirements-colab.txt
```

## Quickstart

```python
from foam_gnn.config import PipelineConfig, DataConfig
from foam_gnn.io_utils import load_frame
from foam_gnn.segmentation import build_segmenter, qc_overlay, flag_suspicious_vertices

cfg = PipelineConfig(data=DataConfig(data_root="data/raw", experiments=("exp1",)))
img = load_frame("foam_gnn/tests/fixtures/samples/frame_000.jpg", cfg.data)

seg = build_segmenter(cfg)                 # WatershedSegmenter (default backend)
result = seg.segment(img)
print(result.n_bubbles, result.meta["foam_area_frac"])

overlay = qc_overlay(img, result)          # RGB array for visual QC
bad = [v for v in flag_suspicious_vertices(result.labels) if v["suspicious"]]
```

The full run on a folder is driven from a thin Colab notebook (`notebooks/`) that
just imports `foam_gnn`; all real logic lives in `src/`.

---

## Repository layout

```
foam_gnn/
├── src/foam_gnn/
│   ├── config.py            # all tunables (single source of truth)
│   ├── guards.py            # shape/dtype/NaN validators (fail loud)
│   ├── io_utils.py          # frame discovery + loading
│   ├── dataset.py           # foam/session structure; source of truth for CV folds
│   ├── segmentation.py      # MODULE 1 — watershed backend
│   ├── cellpose_backend.py  # MODULE 1 — Cellpose backend (loads Colab-GPU masks)
│   ├── seg_eval.py  seg_temporal.py  gt_preseed.py   # detector scoring vs. ground truth
│   ├── tracking.py  propagate.py                     # MODULE 2 — identities, T1/T2
│   ├── stability.py  radial.py                       # trusted subset + radial test
│   ├── graph.py  export_csv.py                       # MODULE 3 — graphs, CSV export
│   └── modeling.py  gnn.py  nn_models.py             # MODULES 4–6 — gates, baselines, GNN
├── tests/                   # 16 files, 164 test functions
│   └── fixtures/samples/    # 5 representative frames (committed for smoke tests)
├── groundtruth/             # hand-corrected labels + manifest.csv (research artifact)
├── cellpose_out/            # v1 Cellpose result CSVs (mask binaries gitignored)
├── cellpose_results_v2/     # v2 run: full exp1 + exp10 result CSVs
├── docs/                    # running lab notebook, incl. negative/retracted results
├── results_package/         # SUMMARY + METHODS_BRIEF + figures/ + tables/
├── results_package_extra/   # T1 addendum + its figures/ + tables/
├── label.py                 # ground-truth labelling helper
├── build_colab_package.py     build_colab_package_v2.py   build_results_package.py
├── pyproject.toml  requirements.txt  requirements-colab.txt
```

`docs/` is kept complete on purpose. Several documents record results that were later
**retracted or superseded** (`modeling_stage1..3_gate*.md`, `cellpose_replication.md`,
`exp10_replication_attempt.md`). They are the audit trail for the five corrections
described above and should not be deleted.

---

## Status — what is **implemented and tested** vs. **not**

**Implemented (Module 1 — segmentation).** Grid-suppressed, contrast-normalized,
marker-controlled watershed with a swappable backend, a QC overlay, and a
Plateau (vertex-order/angle) check.

**Implemented (Module 2 — tracking + dataset structure).** Hungarian+drift
tracking with a **data-driven `max_displacement_px`** (20 px for Foam A);
rewritten **localized T1 detection** (per-swap, with location and robustness
gates); T2/birth detection; per-frame cumulative-drift `frame_offsets` (common
coordinate frame); `dataset.py` as the source of truth for the 3-foam / 7-session
structure (CV-by-foam, track-by-session) with per-experiment shapes.

**Implemented (Module 2 — merge rule: bubbles never appear).** A merge (a frame-t+1
region with ≥2 genealogy parents) now **inherits an existing bubble ID**
(`merge_id_rule`, **default `"keep_larger"`** = the larger-AREA parent's ID, Dr.
Oh's confirmed "Option 3"; `"max"` retained for ablation) instead of minting a new
one — the old birth-on-merge behaviour is gone. A survivor ID is claimed by at most
one region per frame (a `~50/50` split falls back to the next parent, then a
final dedup guard), so per-frame IDs are always unique. `keep_larger` preserves the
big bubble's identity through merges, which measurably improved Foam-A trackability
(trusted bubbles 73→80, near-edge 3→11, trackable area 15%→29%; see
`docs/exp8_diagnostic.md`). A merge-flicker (a film that
briefly fails to segment, faking a merge that re-splits) is reconciled within a
data-tuned window (`merge_resurrect_window=2`, from the Foam-A flicker
distribution) so the re-split reclaims the existing IDs, not new ones.
`TrackingResult.diagnostics` reports merge/flicker/birth counts, ambiguous
resurrections, and the invariant-B check. **Honest scope:** this fixes
*merge-induced* new IDs only. On Foam A the merge mechanism is provably fixed (0 of
346 merges mint a new ID; a real 261+262→262 coalescence is confirmed by eye), but
**invariant B — max ID ≤ frame-0 max — still does NOT hold**, because ~600 new IDs
come from **segmentation reorganization** births (a region overlapping many
predecessors at <50% each; 15/20 frame-1 births have no ≥50% parent), which is a
segmentation-stability problem this fix does not address. See the session notes.

**Implemented (stable-bubble analysis + radial hypothesis test).**
`foam_gnn.stability` selects the **trusted-identity** subset (frame-0-origin IDs
that persist ≥N frames with continuous area and no merge — *not* a size cut) and
runs **pre-condition gates** (survival-vs-distance confound, distance-jitter
reliability, near-edge occupancy/power). `foam_gnn.radial` tests dA/dt vs
distance-to-edge with **cluster-bootstrap CIs**, a von Neumann K-per-bin fit, an
explicit power/MDE statement, and a **pre-registered** decision rule.
**Result on Foam A (`docs/stability_radial_analysis.md`):** the trusted subset is
only ~5% of tracks / ~15% of foam area with just 3 bubbles in the near-edge bin, so
the radial test is **underpowered** — reported (per plan) as *"too few
stably-tracked bubbles, especially near the edge, to test the hypothesis"*, NOT as
evidence about the physics. Points to the small/edge/coalescing population that
needs a segmentation-quality investment.

**Implemented (Module 3 — graph construction + CSV export).** Per-frame NetworkX
graphs (nodes = bubbles, edges = shared films) with node features (area, n_sides,
registered centroid, circularity, perimeter, distance-to-evap-edge) and the three
mentor-spec edge features (`contact_line_length`, `squeezing_strain`,
`distance_to_evap_edge`); lazy/optional PyTorch-Geometric `Data` conversion (no
torch needed for the base path). Long-format `nodes.csv` / `edges.csv` export
(`foam_gnn.export_csv`) per foam (Foam C per session; Foam B excluded) with a
disappear/coalesce classifier, a `event_confidence` flag, and a `README_csv.md`
that carries the **preliminary-event** caveat with the data.

**Implemented (Module 1 — second detector: Cellpose).** `cellpose_backend.py` loads
Cellpose-SAM label maps produced on Colab GPU (CPU inference measures ~64 min/frame, so
it is not run locally) behind the same segmenter interface as the watershed.
`seg_eval.py` / `gt_preseed.py` score any detector against the hand labels. Cellpose is
the detector all headline numbers use — it removed the detection bottleneck that had
rejected Foam C and made a same-detector cross-foam comparison possible for the first
time. See `docs/learned_detector_cellpose.md`, `docs/cellpose_replication_v2.md`.

**Implemented (Modules 4–6 — modelling and the gated model ladder).** `modeling.py` runs
the pre-registered gate sequence (target + trivial baselines → von Neumann fit → MLP
precondition → GNN), `nn_models.py` the no-graph baselines and `gnn.py` the graph network,
all under leave-one-foam-out with cluster-bootstrap CIs. **The gates were re-run twice
after the correctness audit** (`docs/modeling_gates_v2.md`, `gates_v3_stability.md`,
`gates_v4_repairs.md`); the earlier `docs/modeling_stage1..3_gate*.md` conclusions —
including a "GNN beats physics at long horizon" result — are **retracted**. Current
outcome: von Neumann is the best model in eight of nine cells and the GNN never wins.

**Tested** (16 files, 164 test functions; real-data tests skip when `data/` is absent,
and the PyG-dependent test skips without the `ml` extra): Module-1 smoke tests;
dataset logic (LOFO for 4 foams, timestamp parsing, run-splitting, exp2-removal
tolerance); tracking contract + deterministic T1 **and merge** unit tests
(keep_larger survivor, no-birth, per-frame ID uniqueness on a 50/50 split, max-rule
ablation); **graph feature math**; **export long-format invariants** + real-frames
smoke; **stability filter** and **radial test** (implanted-gradient recovery,
flat-data null, von Neumann K recovery, cluster bootstrap). Real-data tests skip
when `data/` is absent.

**Validated on real data this session** (see
[`docs/module2_session_notes.md`](docs/module2_session_notes.md)): Foam C is one
continuous coarsening foam (Spearman(time,count) = −0.97); segmentation transfers
to A & C but **breaks on Foam B**; large bubbles keep stable IDs across consecutive
frames.

**NOT yet validated / known to be weak:**
- **Invariant B (max ID ≤ frame-0 max) does NOT hold on Foam A** — but the cause is
  **segmentation reorganization**, not merges. The merge fix eliminates
  merge-induced new IDs (verified: 0 merges mint one); the residual ~600 new IDs are
  reorganization/flicker births the merge guard is explicitly not designed to catch.
  Making invariant B hold requires **segmentation-stability** work (fewer spurious
  splits/reappearances), not more tracker logic.
- **Some detected merges are edge artifacts** — merges near the foam boundary are
  contaminated by the (known) unstable boundary mask; interior merges are reliable.
  Treat merge/coalesce counts as preliminary; audit by eye near the edge.
- **Event labels (disappear/coalesce) are PRELIMINARY** — flicker-limited (T2 ≈
  birth across thresholds), so raw event counts are not a scientific rate. The
  `event_confidence` flag is a transparent heuristic, not calibrated. This caveat
  ships in `README_csv.md` next to the data.
- **`squeezing_strain` / `circularity` degrade for irregular bubbles** — the
  effective-circular radius √(A/π) and the Crofton perimeter are poor for ragged or
  elongated watershed regions (large-magnitude negative strain, low circularity
  correlate with these). Geometric features (area, contact-length) are unaffected.
- **Foam B has no working segmentation** (different magnification → foam fills the
  frame, films shatter); excluded from the export.
- Smallest bubbles in dense early frames are **merged/missed**; a single
  `h_maxima` is not optimal across the series; the foam-boundary mask is slightly
  generous.
- Tracking validated on a 40-frame slice of exp1; the export is demonstrated on
  Foam A (40 frames) + one Foam C session. **`track_sequence` is slow on dense
  full sessions** (recomputes per-bubble masks each frame, O(labels·pixels)) — fine
  for the demo, but the full multi-session batch needs a vectorized rewrite.

**Resolved since the list above was written:**
- **T1 swaps are no longer unverified.** All 22 shipped events were hand-scored:
  0 flicker, 0 unclear, **false-positive rate 0/22, 95% CI [0%, 14.9%]**
  (`results_package_extra/T1_ADDENDUM.md`). The earlier two-panel verification attempt
  was inconclusive because a real swap and a one-frame glitch are indistinguishable over
  two frames; four panels separate them.
- **Detection accuracy is now measured**, not assumed — and the measurement reversed our
  prior belief that the watershed's higher ⟨n⟩ was the accurate one (§ Results).

**Open, as of the latest results package:**
- **Only Foam A has usable ground truth.** Foam C's labels were made by deleting from the
  watershed's own output, so they cannot fairly score a different detector; Foam C and F
  detection accuracy is unmeasured.
- **Foam F is weak** — 56 bubbles, wide CIs, ~48% of its interior unlabelled, and its
  distance-to-edge measure is uninterpretable because the foam extends past the field of
  view. Reported, not weighted equally.
- **Event labels remain usable on Foam A only.** Coalescence and swap analysis on Foams C
  and F is blocked on the tracker, not the detector.
- **The shipped T1 contact-length threshold may be too strict.** The 16 events that appear
  only when it is relaxed scored 0/16 flicker, suggesting lost recall. Deliberately *not*
  changed yet — flagged as an open question, and no reported swap rate uses them.

This project deliberately **fails loud**: bad shapes/dtypes/NaNs raise immediately
rather than silently producing garbage.

### Design decisions flagged for review
Search the code for `# DECISION`. The most consequential:
- **rupture-risk proxy** = bubble disappears via T2 within `H` frames (Module 4);
- **grid suppression** = FFT notch at ~18.3 px;
- **tracking `max_displacement_px`** = placeholder, untunable until full data;
- **neighbour definition** = shared border ≥ `min_shared_border_px`;
- units in **px²/frame** (β is scale-free).
