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

## Data assumptions (from Step-0 reconnaissance, experiment 1)

| Property | Value |
|---|---|
| Frame size | 1280×1024 (W×H), 8-bit |
| Channels | stored 3-ch JPEG, **effectively grayscale** (colour = non-physical cast, discarded) |
| Contrast | low (data in ~[12, 210]); a periodic **~18.3 px grid** is suppressed in preprocessing |
| Scale / time | **no µm/px** (areas in px², rates in px²/frame); 30 s/frame |
| Dataset | ≤3 experiments × ~198 frames → **small-data**: leave-one-experiment-out CV |

Adding experiments 2 and 3 is **additive**: drop `data/raw/exp2/`, `exp3/` and
list them in `DataConfig.experiments`. No code change.

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

**Tested** (smoke tests on the 5 committed exp1 frames): the module runs
end-to-end and produces a sane `SegmentationResult` (shapes/dtypes/no-NaN,
plausible bubble counts ~50–200, foam-area fraction ~20–30 %, ~99 % three-way
junctions); input guards raise on bad data; backend stubs raise `NotImplementedError`.

**NOT yet tested / known to be weak:**
- The smallest bubbles in dense early frames are **merged/missed** (classical-
  watershed ceiling on low-contrast brightfield) — motivates the SAM/FoamQuant
  backend hook.
- A **single `h_maxima`** value is not optimal across the whole coarsening series.
- The foam-boundary mask is **slightly generous**; `boundary_erode_px` is a blunt
  tightening knob.
- Behaviour on **experiments 2–3** and on **full 198-frame** folders (only 5
  sparse frames were available during development).

This project deliberately **fails loud**: bad shapes/dtypes/NaNs raise immediately
rather than silently producing garbage.

### Design decisions flagged for review
Search the code for `# DECISION`. The most consequential:
- **rupture-risk proxy** = bubble disappears via T2 within `H` frames (Module 4);
- **grid suppression** = FFT notch at ~18.3 px;
- **tracking `max_displacement_px`** = placeholder, untunable until full data;
- **neighbour definition** = shared border ≥ `min_shared_border_px`;
- units in **px²/frame** (β is scale-free).
