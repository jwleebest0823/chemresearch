"""
foam_gnn.config
===============
Central, pure-Python configuration objects for the foam-GNN pipeline.

There are **no hardcoded paths or magic numbers** elsewhere in the codebase:
every tunable lives here as a frozen dataclass field. A single
:class:`PipelineConfig` instance is threaded through every module.

Assumptions baked in (from Step-0 reconnaissance on experiment 1)
-----------------------------------------------------------------
* Frames are 8-bit, 1280x1024 (W x H), JPEG. Stored 3-channel but the colour
  is a non-physical sensor / illumination cast (brightfield, light from below);
  it is discarded -> grayscale. NO film thickness is inferable from intensity.
* A periodic ~18.3 px "graph-paper" grid is present and is suppressed in
  preprocessing (FFT notch) *before* segmentation, or the watershed shatters.
* No EXIF timestamps and no pixel scale: ``microns_per_px`` is unknown, so areas
  are reported in px**2 and rates in px**2 / frame. The coarsening exponent
  ``beta`` is scale-free and unaffected.
* Acquisition interval 30 s/frame; ~198 frames/experiment; up to 3 experiments
  -> small-data regime (leave-one-experiment-out CV, heavy regularization).

This module imports nothing heavy (no torch / cv2) so it is cheap to import.
Fields encoding a research-relevant choice are marked ``# DECISION``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DataConfig:
    """Where frames live and what shape they must be.

    ``data_root`` is expected to contain one subfolder per experiment, so that
    dropping in experiments 2 and 3 later is purely additive (no refactor):
    ``data_root/exp1/*.jpg``, ``data_root/exp2/*.jpg``, ...
    """

    data_root: Path = Path("data/raw")
    experiments: tuple[str, ...] = ("exp1",)   # DECISION: each entry = one LOEO CV fold
    frame_glob: str = "*.jpg"
    interval_seconds: float = 30.0
    expected_hw: tuple[int, int] = (1024, 1280)  # (H, W); asserted on load (fail loud)
    enforce_shape: bool = True
    microns_per_px: float | None = None          # DECISION: None -> areas in px**2 (no scale in data)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", Path(self.data_root))


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PreprocConfig:
    """Grayscale -> grid-suppress -> contrast-normalize -> denoise."""

    clahe_clip: float = 3.0
    clahe_grid: tuple[int, int] = (8, 8)
    # DECISION: Step-0 found a strong periodic grid at ~18.3 px. "fft_notch"
    # removes the discrete spectral peaks while preserving (aperiodic) bubbles.
    grid_suppression: str = "fft_notch"           # {"none", "fft_notch"}
    notch_exclude_r: int = 28                      # keep low-freq core (bubble structure) untouched
    notch_peak_rel: float = 0.30                   # peak must exceed this fraction of max to be notched
    notch_radius: int = 4                          # radius (px) of each spectral notch
    denoise: str = "bilateral"                     # {"none", "bilateral"}
    bilateral_d: int = 5
    bilateral_sigma: float = 30.0


# --------------------------------------------------------------------------- #
# Foam boundary (for distance-to-edge / radial-gradient hypothesis)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BoundaryConfig:
    """Detect the outer foam boundary via film/edge density, then distance-transform."""

    clahe_clip: float = 2.0
    edge_sigma: float = 15.0                       # blur scale for edge-density map
    thresh_k: float = 0.4                          # mask = density > mean + thresh_k * std
    density_close_ksize: int = 41
    mask_close_ksize: int = 61
    # DECISION: Step-0 mask is slightly generous (sits just outside outermost films).
    # boundary_erode_px>0 tightens it; a principled snap-to-film is a future refinement.
    boundary_erode_px: int = 0


# --------------------------------------------------------------------------- #
# Segmentation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SegConfig:
    """Marker-controlled watershed (default). Backend is swappable."""

    # DECISION: classical watershed default; "sam"/"foamquant" are stubs for the
    # likely upgrade given the low contrast (see Segmenter subclasses).
    backend: str = "watershed"                     # {"watershed", "sam", "foamquant"}
    # DECISION: h_maxima is THE over/under-segmentation knob. Tuned to 4.0 on the
    # exp1 samples (counts 142->56, ~99% three-way junctions). A single h cannot
    # be optimal across the whole time series (small early bubbles have shallow
    # distance peaks); revisit per-experiment on the full set.
    h_maxima: float = 4.0
    sato_sigmas: tuple[int, ...] = (1, 2, 3)       # ridge-filter scales for film detection
    interior_thresh: float = 0.12                  # film-prob below this = bubble interior (seed region)
    dt_smooth_sigma: float = 1.0                   # smoothing of distance transform before seeding
    min_bubble_area_px: int = 15                   # drop watershed regions smaller than this
    max_bubble_area_frac: float = 0.25             # flag/clip regions larger than this fraction of foam


# --------------------------------------------------------------------------- #
# Tracking (Module 2 — fields defined now so the contract is stable)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TrackConfig:
    register_drift: bool = True                    # DECISION: foam translates between frames (Step-0)
    max_displacement_px: float = 25.0              # DECISION: PLACEHOLDER — untunable from 5 sparse frames
    area_ratio_tol: float = 0.5                    # gate on |log(A_t / A_{t+1})|
    cost_w_centroid: float = 1.0                   # DECISION: matching-cost weights
    cost_w_area: float = 0.5


# --------------------------------------------------------------------------- #
# Graph (Module 3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GraphConfig:
    node_features: tuple[str, ...] = (
        "area", "n_sides", "cx", "cy", "circularity", "perimeter", "dist_to_edge",
    )
    min_shared_border_px: int = 3                  # DECISION: below this two regions are not "neighbours"


# --------------------------------------------------------------------------- #
# Model / loss / training / eval (Modules 4-6 — defined now, used later)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModelConfig:
    hidden_dim: int = 64
    n_mp_layers: int = 4
    dropout: float = 0.3                           # heavy reg for small-data
    temporal_window: int = 3
    rupture_head_level: str = "node"               # DECISION: {"node", "edge"}


@dataclass(frozen=True)
class LossConfig:
    w_mse: float = 1.0
    w_von_neumann: float = 0.0                      # DECISION: lambda; OFF by default -> ablations explicit
    w_plateau: float = 0.0
    K_mode: str = "learned"                         # {"fixed", "learned"}; K in px**2 / frame
    K_value: float = 1.0
    rupture_proxy_horizon: int = 5                  # KEY DECISION: T2-disappearance within H frames = positive


@dataclass(frozen=True)
class TrainConfig:
    lr: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 200
    seed: int = 0
    checkpoint_dir: Path = Path("checkpoints")
    checkpoint_every_n: int = 10
    device: str = "auto"                            # {"auto", "cpu", "cuda"}
    cv_mode: str = "leave_one_experiment_out"

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_dir", Path(self.checkpoint_dir))


@dataclass(frozen=True)
class EvalConfig:
    rollout_horizons: tuple[int, ...] = (1, 5, 20)
    n_bootstrap: int = 1000
    radial_bins: int = 8


# --------------------------------------------------------------------------- #
# Top-level
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PipelineConfig:
    """Composes every sub-config. Construct once, pass everywhere."""

    data: DataConfig = field(default_factory=DataConfig)
    preproc: PreprocConfig = field(default_factory=PreprocConfig)
    boundary: BoundaryConfig = field(default_factory=BoundaryConfig)
    seg: SegConfig = field(default_factory=SegConfig)
    track: TrackConfig = field(default_factory=TrackConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
