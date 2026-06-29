# foam_gnn

Physics-informed **Graph Neural Network** pipeline for modelling the evolution of
a **quasi-2D evaporating soap foam** (brightfield microscopy, ~30 s/frame).

> This project is **self-contained**: it has its own dependencies, tests and
> packaging and can be copied out into a standalone repository with no changes.

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

## Dataset structure — 3 independent foams, not 7 experiments

The on-disk folders `exp1`…`exp7` are **3 physically independent foams** imaged
across **7 acquisition sessions**. This is authoritative in
[`foam_gnn.dataset`](src/foam_gnn/dataset.py) (`FOAM_SESSIONS`, `EXPERIMENTS`),
the single source of truth for both CV folds and tracking segments.

| Foam | Folders | Frames | Image | Mag | Notes |
|---|---|---|---|---|---|
| **A** | `exp1` | 198 | 1024×1280 JPG | M1 | B/W; two 99-frame runs split by a 2.5-min gap |
| **B** | `exp2` | 103 | **1536×2048 TIF** | ≠M1 | different USB camera; non-physical colour → grayscale |
| **C** | `exp3`–`exp7` | 5×99 | 1024×1280 JPG | ≈M1 | **ONE raft**, 5 sessions over ~10.7 h on 2026-06-16 |

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
│   ├── config.py        # all tunables (single source of truth)
│   ├── guards.py        # shape/dtype/NaN validators (fail loud)
│   ├── io_utils.py      # frame discovery + loading
│   ├── segmentation.py  # MODULE 1 (implemented)
│   └── models/          # MODULE 4 (planned)
├── tests/
│   ├── fixtures/samples/ # 5 representative frames (committed for smoke tests)
│   └── test_segmentation.py
├── notebooks/           # thin Colab runner (planned)
├── scripts/             # CLI entry points (planned)
├── pyproject.toml  requirements.txt  requirements-colab.txt
```

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

**Implemented (Module 3 — graph construction + CSV export).** Per-frame NetworkX
graphs (nodes = bubbles, edges = shared films) with node features (area, n_sides,
registered centroid, circularity, perimeter, distance-to-evap-edge) and the three
mentor-spec edge features (`contact_line_length`, `squeezing_strain`,
`distance_to_evap_edge`); lazy/optional PyTorch-Geometric `Data` conversion (no
torch needed for the base path). Long-format `nodes.csv` / `edges.csv` export
(`foam_gnn.export_csv`) per foam (Foam C per session; Foam B excluded) with a
disappear/coalesce classifier, a `event_confidence` flag, and a `README_csv.md`
that carries the **preliminary-event** caveat with the data.

**Tested** (74 passing, 1 skipped without the PyG extra): Module-1 smoke tests;
dataset logic (LOFO, timestamp parsing, run-splitting); tracking contract +
deterministic T1 unit tests; **graph feature math on synthetic maps**
(contact-length, n_sides, circularity, strain, dist sampling, registered coords);
**export long-format invariants** (right-censored disappearance, event on final
frame only) + a real-frames Foam-A smoke. Real-data tests skip when `data/` is
absent (it is gitignored).

**Validated on real data this session** (see
[`docs/module2_session_notes.md`](docs/module2_session_notes.md)): Foam C is one
continuous coarsening foam (Spearman(time,count) = −0.97); segmentation transfers
to A & C but **breaks on Foam B**; large bubbles keep stable IDs across consecutive
frames.

**NOT yet validated / known to be weak:**
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

This project deliberately **fails loud**: bad shapes/dtypes/NaNs raise immediately
rather than silently producing garbage.

### Design decisions flagged for review
Search the code for `# DECISION`. The most consequential:
- **rupture-risk proxy** = bubble disappears via T2 within `H` frames (Module 4);
- **grid suppression** = FFT notch at ~18.3 px;
- **tracking `max_displacement_px`** = placeholder, untunable until full data;
- **neighbour definition** = shared border ≥ `min_shared_border_px`;
- units in **px²/frame** (β is scale-free).
