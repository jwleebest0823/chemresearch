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
gates); T2/birth detection; `dataset.py` as the source of truth for the 3-foam /
7-session structure (CV-by-foam, track-by-session) with per-experiment shapes.

**Tested** (62 passing): Module-1 smoke tests on the 5 committed frames; dataset
logic (LOFO folds, C-never-split, timestamp parsing, run-splitting); tracking
contract + **deterministic T1 unit tests** on a synthetic canonical swap; overlay
contracts. Real-data tests skip when `data/` is absent (it is gitignored).

**Validated on real data this session** (see
[`docs/module2_session_notes.md`](docs/module2_session_notes.md)): Foam C is one
continuous coarsening foam (Spearman(time,count) = −0.97); segmentation transfers
to A & C but **breaks on Foam B**; large bubbles keep stable IDs across consecutive
frames.

**NOT yet validated / known to be weak:**
- **T2/birth rates are flicker-limited** — across thresholds T2 ≈ birth, the
  signature of Module-1 small-bubble flicker, not real coarsening. Raw T2 counts
  are not yet a scientific T2 rate.
- **Foam B has no working segmentation** (different magnification → foam fills the
  frame, films shatter); needs its own regime.
- Smallest bubbles in dense early frames are **merged/missed**; a single
  `h_maxima` is not optimal across the series; the foam-boundary mask is slightly
  generous.
- Tracking validated on a 40-frame slice of exp1 only — not the full series, not
  on B/C consecutive runs.

This project deliberately **fails loud**: bad shapes/dtypes/NaNs raise immediately
rather than silently producing garbage.

### Design decisions flagged for review
Search the code for `# DECISION`. The most consequential:
- **rupture-risk proxy** = bubble disappears via T2 within `H` frames (Module 4);
- **grid suppression** = FFT notch at ~18.3 px;
- **tracking `max_displacement_px`** = placeholder, untunable until full data;
- **neighbour definition** = shared border ≥ `min_shared_border_px`;
- units in **px²/frame** (β is scale-free).
