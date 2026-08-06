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

    ``data_root`` holds one subfolder per experiment (images may nest one level
    deeper; :mod:`foam_gnn.io_utils` resolves that).

    PHYSICAL STRUCTURE LIVES ELSEWHERE. The foam->session grouping (CV unit =
    foam; tracking unit = session) and the **per-experiment image shape /
    extension** are authoritative in :mod:`foam_gnn.dataset` (``EXPERIMENTS``,
    ``FOAM_SESSIONS``), NOT here. There is no single global frame size — Foam B
    is 1536x2048 vs 1024x1280 for A/C — so prefer
    :func:`foam_gnn.io_utils.load_experiment_frames`, which shape-checks against
    the correct per-experiment size.

    The fields below are a *fallback* for ad-hoc / fixture loading via
    :func:`foam_gnn.io_utils.load_frame` when no per-experiment shape is supplied.
    """

    data_root: Path = Path("data/raw")
    # DECISION: experiments listed here are for ad-hoc runs; CV folds are built
    # from foam groups via foam_gnn.dataset.leave_one_foam_out(), never from this
    # flat tuple (which cannot express that Foam C's 5 sessions must not split).
    experiments: tuple[str, ...] = ("exp1",)
    frame_glob: str = "*.jpg"
    interval_seconds: float = 30.0
    # Fallback global shape (used only when load_frame is called without an
    # explicit per-experiment expected_hw). Authoritative shapes: dataset.EXPERIMENTS.
    expected_hw: tuple[int, int] = (1024, 1280)  # (H, W)
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
    # DECISION: Li's minimum-cross-entropy threshold, NOT the legacy ``mean + thresh_k*std``.
    # The legacy rule takes its statistics over the WHOLE image, in which the foam is
    # itself the high-density class, so the threshold RISES with the foam's area fraction
    # — a frame that is mostly foam gets a STRICTER foam threshold. Measured on exp3 f000
    # (foam ~54% of frame): legacy threshold 151.6 while large-bubble regions sit at ~107
    # and true background at ~50, cutting 15.5% of the visible foam away.
    #
    # Li rather than Otsu: the density histogram is a narrow background spike plus a broad
    # foam spread, i.e. very unequal variances, which is exactly where Otsu's equal-variance
    # assumption misplaces the cut. MEASURED on the 14 Foam A GT frames (pooled F1):
    # legacy 0.8958, Otsu 0.8488 (regresses every frame), Li 0.9030. Li also raises exp3
    # f000 coverage 84.5% -> 99.4%. Neither has a free parameter.
    # See docs/foam_mask_coverage.md.
    thresh_mode: str = "li"                        # {"li", "otsu", "mean_k_std"}
    thresh_k: float = 0.4                          # LEGACY only (thresh_mode="mean_k_std")
    density_close_ksize: int = 41
    mask_close_ksize: int = 61
    # Fraction of the image border the foam may cover before dist_to_edge stops being a
    # true distance-to-evaporation-edge (the foam is clipped by the field of view).
    clip_border_warn_frac: float = 0.10
    # DECISION: pick the threshold by LOCAL STABILITY, not by value. Measured: on late
    # Foam A frames the mask area is a step function of the threshold (exp1 f175 jumps
    # 20.2% -> 30.2% of the frame for a 5% threshold change) and the cliff moves between
    # frames, so Li's k~0.94 flickers and the tracker re-mints ids. See
    # docs/exp1_churn_bisection.md. "off" restores the raw thresh_mode value.
    thresh_stability: str = "on"                   # {"on", "off"}
    thresh_stability_eps: float = 0.03             # relative threshold step
    thresh_stability_tol: float = 0.05             # max mask-area loss per step on a plateau
    thresh_stability_max_steps: int = 8
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
    # DECISION (B2): tuned on the 40-frame consecutive exp1 run. Genuine matched
    # per-bubble drift (after foam-mask drift registration) is median ~2.6 px,
    # p95 ~15.6 px; inter-bubble centre spacing is ~50 px. 20 px ≈ p95+margin and
    # < half the spacing, so matches capture real motion without jumping to a
    # neighbour. Looser gates (≥40) inflate T1 by admitting cross-neighbour
    # matches (T1: 28@20 → 153@64). Foam A units (px); RE-TUNE per foam/mag.
    max_displacement_px: float = 20.0
    area_ratio_tol: float = 0.5                    # gate on |log(A_t / A_{t+1})|
    cost_w_centroid: float = 1.0                   # DECISION: matching-cost weights
    cost_w_area: float = 0.5
    # ── T1 (neighbour-swap) detection (B1) ──────────────────────────────────
    # DECISION: a film edge is only "real" once its shared border exceeds this;
    # used to gate both the lost (P-Q) and gained (R-S) edge of a candidate swap,
    # rejecting 1-2 px adjacency flicker from watershed jitter.
    t1_min_border_px: int = 5
    # DECISION: require the newly-formed R-S edge to survive this many additional
    # frames before accepting the T1 (0 disables). Rejects single-frame flicker.
    t1_confirm_frames: int = 1
    # ── Merge handling (mentor's rule: bubbles never appear; a merge inherits an
    #    existing ID, never a new one) ─────────────────────────────────────────
    # DECISION (D3, CONFIRMED by Dr. Oh — "Option 3"): a merged region inherits the
    # ID of the parent with the LARGER AREA (physical continuity of the big bubble),
    # NOT the larger ID number.
    #   "keep_larger"-> largest-area parent's ID (default; tie-broken by highest ID).
    #   "max"        -> highest bubble_id among parents (old rule; kept for ablation;
    #                   can relabel a large continuous bubble to a small absorbed
    #                   bubble's higher ID).
    # Both mint no new ID (the merge invariant is preserved either way).
    merge_id_rule: str = "keep_larger"             # {"keep_larger", "max"}
    # DECISION: a frame-t bubble is a "parent" of a frame-(t+1) region when at
    # least this fraction of the PARENT's footprint flows into that region. On the
    # parent's fraction (not the region's) so incidental boundary overlap from a
    # neighbour does not manufacture a spurious parent. >=2 parents => merge.
    merge_overlap_frac: float = 0.5
    # DECISION (D2a): resurrection window for MERGE-flicker (a thin film that
    # momentarily fails to segment, faking a merge that then re-splits). A merged
    # cluster stays reconcilable for this many frames; on re-split its members
    # reclaim their EXISTING IDs instead of minting new ones. TUNED on real Foam-A
    # merge-flicker durations (dev/equiv_check-style measurement): observed with a
    # wide window, durations are 44% at 1 frame, 69% ≤2, with a thin tail to ~8.
    # The 1-frame film failure is the physical mechanism; durations ≥3 are more
    # likely late genuine re-splits than momentary flicker, so W=2 covers the
    # flicker peak without reconciling long-lived merges (raw p95≈7 deliberately
    # NOT used — those long events risk undoing real merges).
    merge_resurrect_window: int = 2
    # DECISION (D2b): a resurrection is flagged AMBIGUOUS (silent-corruption risk)
    # when the 2nd-best dormant candidate's overlap is within this fraction of the
    # best (i.e. best is not clearly best). Counted and reported, not silently used.
    merge_ambiguous_frac: float = 0.2


# --------------------------------------------------------------------------- #
# Graph (Module 3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GraphConfig:
    # Node/edge feature names == the CSV column names (single source of naming).
    node_features: tuple[str, ...] = (
        "area", "n_sides", "centroid_x", "centroid_y",
        "circularity", "perimeter", "distance_to_evap_edge",
    )
    edge_features: tuple[str, ...] = (
        "contact_line_length", "squeezing_strain", "distance_to_evap_edge",
    )
    min_shared_border_px: int = 3                  # DECISION: below this two regions are not "neighbours"
    # ── disappear-vs-coalesce classification + event confidence (Module 3) ───
    # DECISION: a T2 death is "coalesce" (vs "disappear") when one surviving,
    # previously-adjacent neighbour absorbs at least this fraction of the vanished
    # bubble's last footprint AND grows by ~its area. Overlap is in native pixels
    # (drift between consecutive frames is small, ~2.6 px median).
    coalesce_min_overlap_frac: float = 0.5
    # DECISION: event_confidence is a transparent heuristic, NOT calibrated. A death
    # is "low" confidence (likely segmentation flicker) when the bubble was seen for
    # <= this many frames or its last area was below the flicker-area floor; else
    # "medium". ALL event labels remain PRELIMINARY (see README_csv.md).
    event_low_conf_max_lifetime: int = 2
    event_low_conf_area_px: int = 30


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
    # DECISION (modeling): a trusted segment is "dynamic" (vs "quiescent") when its
    # total fractional area change |A_end-A_start|/A_start over the segment is >=
    # this. Baselines/models are reported split on this so a "predict no change"
    # model is not credited for the quiescent majority (dA/dt~0 by construction).
    dynamic_frac_thresh: float = 0.10


# --------------------------------------------------------------------------- #
# Stable-bubble analysis (trusted-identity subset + radial hypothesis test)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StabilityConfig:
    """Select bubbles whose IDENTITY we can trust — NOT the big bubbles.

    A trusted track segment is a maximal run of consecutive frames for one stable
    ``bubble_id`` that (a) has a real origin, (b) persists, (c) has a continuous
    area trajectory, and (d) contains no merge. We never threshold on instantaneous
    size, so small trusted bubbles are kept; but persistence introduces
    survivorship selection — reported, not hidden (see ``foam_gnn.stability``).
    """

    # DECISION (D1, confirmed): only bubbles present in the initial segmentation
    # (bubble_id <= frame0_max_id) are eligible. Every later ID is a
    # reorganization-birth artifact ("bubbles never appear").
    origin_rule: str = "frame0"                    # {"frame0"}
    # DECISION (D3): a trusted segment needs at least this many consecutive frames
    # (an N-frame sweep is run around this default).
    min_persist_frames: int = 5
    # DECISION (D3): |Δ log area| above this between consecutive frames signals a
    # segmentation relabel / boundary theft → the track is split there.
    area_jump_tol: float = 0.5
    # ── gates (analysis is HALTED / flagged, not silently continued) ──────────
    # DECISION (D1 gate): below this many trusted bubbles the radial test is
    # declared underpowered and the finding is "too few stably-tracked bubbles".
    min_trusted_bubbles: int = 20
    # DECISION: a radial bin with fewer trusted bubbles than this is excluded from
    # per-bin K fits (kept for occupancy reporting).
    min_bubbles_per_bin: int = 5
    # DECISION (Condition 1): if |Spearman(survived-filter, distance-to-edge)|
    # exceeds this, near-edge bubbles are systematically under-retained → the
    # radial test is CONFOUNDED (a null is not "no gradient"). Reported as a gate.
    survival_confound_rho: float = 0.3
    # DECISION (Condition 2): if a stationary trusted bubble's frame-to-frame
    # distance-to-edge jitter (std) exceeds this fraction of its mean distance, the
    # x-axis is deemed noisy and reported as such.
    distance_jitter_frac: float = 0.15


# --------------------------------------------------------------------------- #
# Temporal marker-propagation segmentation (attacks temporal identity stability)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PropagateConfig:
    """Temporally-coupled watershed: frame t+1 is seeded from frame t's stable-ID
    labels (warped by the measured drift), so a persistent bubble keeps ONE marker
    and therefore ONE identity by construction. This structurally SUPPRESSES the two
    spurious events (a bubble splitting into two ids, or being re-minted) while
    still ALLOWING the two genuine ones (a bubble merging, or disappearing).
    """

    # DECISION: erode a warped previous bubble to a safe interior "seed core" before
    # re-seeding, so small drift/shape change doesn't leak the marker across a film.
    erode_seed_px: int = 2
    # DECISION: if a bubble's eroded seed core (∩ current interior) falls below this,
    # the bubble has collapsed -> treat as a genuine disappearance (T2), don't re-seed.
    min_seed_area_px: int = 5
    # DECISION: a genuine MERGE is detected post-watershed when the shared boundary
    # between two PRE-EXISTING bubbles carries film ridge below this (normalized [0,1])
    # -> the film is gone, so dissolve the boundary (keep_larger id). Above it the two
    # are kept apart (a real film -> NOT a merge, and the single-marker seeding already
    # forbids a spurious split).
    merge_film_thresh: float = 0.12
    merge_min_border_px: int = 4          # ignore 1-2px adjacency flicker when judging a merge
    # DECISION: adaptive new-bubble markers — small bubbles get seeds at their LOCAL
    # scale instead of one global h_maxima. peak_local_max on the distance transform
    # with a small min separation catches small bubbles; a small dt floor rejects noise.
    new_seed_min_distance_px: int = 4
    new_seed_min_dt: float = 2.0
    new_seed_min_area_px: int = 8         # a new basin below this is absorbed, not born
    # DECISION: drift is estimated by phase cross-correlation of consecutive foam masks
    # (sub-pixel), the same translation model Module 2 uses; clipped if implausibly large.
    drift_upsample: int = 10
    drift_max_px: float = 40.0

    # ── RATCHET FIX (see docs/propagation_ratchet_defect.md) ──────────────────
    # The v1 segmenter inherited GEOMETRY from the previous frame, so one marker could
    # come to own many bubbles and nothing could ever split it back apart -> monotone
    # count collapse. The fix enforces an invariant and decouples geometry from identity.
    #
    # DECISION (INVARIANT): every interior blob receives EXACTLY ONE marker. Geometry is
    # therefore re-derived from the current frame every frame (a marker cannot span two
    # blobs, so it cannot swallow bubbles); only IDENTITY is propagated.
    #
    # DECISION: geometry splits are UNGATED (two blobs separated by film in this frame
    # ARE two regions; forcing them together is never more faithful). Only the decision
    # "does the split-off region get its own bubble id?" is gated, because only that can
    # manufacture churn. Gating order: resurrect a dormant id (costs ZERO churn) ->
    # else probation -> else mint a new id.
    #
    # DECISION (hysteresis): a blob boundary means film >= SegConfig.interior_thresh
    # (0.12) -- the SAME value used to accept a merge. With one threshold a borderline
    # film would merge and split alternately forever, so a split is COMMITTED
    # immediately only when the separating ridge is clearly stronger than that
    # (>= split_film_thresh); a fainter separation must serve probation instead.
    split_film_thresh: float = 0.20
    # DECISION: probation length W (frames a faint separation / a merge must persist
    # before it is committed as an identity change). MEASURED, not assumed
    # (dev/measure_probation_w.py, Foam A exp1, 99 frames, probation disabled so
    # nothing commits): 526 candidate separations -> 430 collapsed back (spurious),
    # 96 persisted (real, 18%). Durations of the spurious ones are BIMODAL: a flicker
    # spike at 1-2 frames (33% last exactly 1, 43.7% <= 2) plus a long tail
    # (median 5, p90 38, max 92) of transient-but-real bubbles that merge away later.
    # W=2 captures the flicker spike; the tail cannot be rejected by probation without
    # deferring real splits for tens of frames, and returns collapse beyond it
    # (W=3 -> 47%, W=5 -> 50%, W=8 -> 55%). The tail is handled instead by the
    # merge/resurrection machinery. W=2 also matches TrackConfig.merge_resurrect_window,
    # which was measured the same way (44% of merge-flickers last 1 frame, 69% <= 2).
    probation_frames: int = 2
    # DECISION: a merged-away id stays reclaimable for this many frames; on re-separation
    # it RECLAIMS its old id instead of minting a new one, which is what keeps the split
    # mechanism from reintroducing reorganization-birth churn.
    resurrect_window: int = 8
    resurrect_min_overlap_frac: float = 0.30       # of the candidate blob's area
    claim_min_px: int = 5                          # min overlap for a prev id to claim a blob
    # DECISION (bleed fix): compute_foam_mask is deliberately generous (documented: it
    # sits just outside the outermost films; measured <= 11.2 px past the outermost
    # interior on exp1 f049). Watershed assigns EVERY masked pixel to some label, so that
    # rim became label territory on background -- inflating edge-bubble area and
    # distorting distance_to_evap_edge, i.e. corrupting the near-edge stratum. Flood
    # instead on foam AND a tight hull of the detected interiors.
    tight_mask_dilate_px: int = 5
    # DECISION (PLATEAU-BORDER REJECTION -- measured against ground truth): the Sato
    # ridge filter responds to thin FILMS but not to the fat triangular interstices where
    # three bubbles meet (Plateau borders). Their interiors therefore pass
    # `film < interior_thresh` and were emitted as "bubbles" -- ~2 spurious regions per
    # real bubble. Measured on the 14 hand-labeled Foam A frames: precision 0.347,
    # F1 0.515, with recall ~1.0 (every real bubble WAS found; the error is purely
    # spurious extra regions).
    # Physical discriminator: a bubble interior is GAS (bright, median raw intensity
    # ~142-149) while a Plateau border is LIQUID (dark, ~93-99). Gating the *interior
    # mask* fails (it only shrinks blobs, so they still get seeded, and it costs recall);
    # the fix is to drop whole REGIONS whose mean raw intensity is too low.
    # Threshold is per-frame adaptive (Otsu within the foam, ~126-128 here) scaled by
    # `intensity_gate_frac`. Measured sweep over the GT frames (precision/recall/F1):
    #   off 0.347/0.998/0.515 | 105 0.786/0.903/0.841 | 115 0.899/0.879/0.889
    #   | 120 0.928/0.864/0.895 | 125 0.942/0.838/0.887
    # F1 plateaus ~0.89 across 115-125; 0.92*Otsu lands in that plateau and favours
    # recall slightly, which matters because losing real bubbles is the failure this
    # project is most sensitive to. Set to 0.0 to disable the gate entirely.
    intensity_gate_frac: float = 0.92
    # DECISION (regression guard): the interior-blob count is an INDEPENDENT per-frame
    # bubble estimate that is already computed every frame at zero cost. Under the
    # invariant n_regions ~= n_blobs, so a sustained drop of that ratio is exactly the
    # ratchet signature and is caught immediately instead of by eye weeks later.
    collapse_guard: str = "raise"                  # {"raise", "warn", "off"}
    collapse_guard_ratio: float = 0.60
    collapse_guard_patience: int = 3               # consecutive frames below the floor
    # DECISION (FRAGMENTATION guard): the collapse guard above catches UNDER-segmentation
    # (the ratchet) and is blind to the opposite failure by construction. Foam C exhibits
    # exactly that opposite failure: as it drains, large bubbles' interiors break into many
    # blobs (measured: up to 98 one-per-blob regions inside a single h_maxima bubble), so
    # the region count RISES 554 -> 1112 -> 1172 through a coarsening sequence while an
    # independent detector correctly falls 315 -> 223 -> 213.
    # A coarsening foam cannot gain bubbles ("bubbles never appear"), so a sustained rise
    # above the running minimum is proof of fragmentation. Ratio 1.5 tolerates
    # detection noise while catching the ~2x growth actually observed; patience 3 avoids
    # firing on a single bad frame.
    fragmentation_guard: str = "raise"             # {"raise", "warn", "off"}
    fragmentation_guard_ratio: float = 1.50        # count vs the running minimum
    fragmentation_guard_patience: int = 3


# --------------------------------------------------------------------------- #
# Segmentation evaluation (ground-truth harness + stratification)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SegEvalConfig:
    """Config for the ground-truth + temporal segmentation-evaluation harnesses.

    The whole point is STRATIFICATION: a method that is accurate on large interior
    bubbles and fails on small near-edge ones must be exposed, not averaged. So both
    harnesses bin every metric by bubble size and by distance-to-evaporation-edge.
    """

    # DECISION: per-bubble detection is scored by one-to-one Hungarian matching on
    # the IoU matrix; a matched pair is a true positive only if IoU >= the threshold.
    # Report at several thresholds (loose detection -> strict boundary agreement).
    iou_thresholds: tuple[float, ...] = (0.5, 0.75, 0.9)
    iou_primary: float = 0.5                       # threshold used for stratified tables
    # DECISION: size bins are GT-area TERCILES (small/medium/large) computed on the
    # pooled labeled set, so "small" is data-relative, not an absolute px cutoff.
    n_size_bins: int = 3
    size_bin_labels: tuple[str, ...] = ("small", "medium", "large")
    # DECISION: distance-to-edge bins are fixed fractional shells of the max GT
    # distance (near-edge .. interior); near-edge is bin 0 (the population the project
    # needs and current segmentation loses).
    n_dist_bins: int = 4
    # DECISION: a predicted region "covers" a GT bubble (for split/merge counting)
    # when it takes at least this fraction of the GT bubble's area (and vice versa).
    cover_frac: float = 0.20
    # Ground-truth validation thresholds.
    gt_min_bubble_area_px: int = 8                 # warn: labels below this may be annotation noise
    gt_root: str = "groundtruth"                   # dir holding <exp>/f<idx>.png + manifest.csv


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
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    seg_eval: SegEvalConfig = field(default_factory=SegEvalConfig)
    propagate: PropagateConfig = field(default_factory=PropagateConfig)
