"""
foam_gnn.cellpose_backend
=========================
Consume **externally computed Cellpose-SAM instance masks** as a Module-1
segmentation backend, so the existing tracking -> graph -> trusted-set -> modeling
chain runs on learned detection without any change downstream.

Why this module exists
----------------------
`docs/learned_detector_cellpose.md` measured Cellpose-SAM at ~64 min/frame on this
CPU-only machine, so inference is run on a GPU (Colab) and the resulting int32 label
maps are committed under ``cellpose_out/``. This module is the *local* half: it loads
those label maps, applies the one necessary post-processing step (below), and wraps
them in :class:`~foam_gnn.segmentation.SegmentationResult` so they are
indistinguishable from watershed output to everything downstream.

The one post-processing step, and why it is a PIPELINE step (# DECISION)
------------------------------------------------------------------------
Raw Cellpose tiles the **background plate** into ~300 px blobs of near-background
intensity — on Foam A f149, 335 of 377 "objects" are plate, not bubbles. Cellpose has
no notion of "foam"; it segments whatever texture it is given, and the plate outside
the raft is texture.

The fix is to keep only objects that lie inside the foam aggregate, and the foam
aggregate is something this project **already** detects, from the raw frame, with a
documented and tested routine: :func:`foam_gnn.segmentation.compute_foam_mask`
(edge-density -> Li threshold -> morphological close -> largest connected component ->
fill holes). So the restriction is written here as
:func:`restrict_to_foam_mask`, driven by that same function and the same
:class:`~foam_gnn.config.BoundaryConfig` the watershed pipeline uses — NOT as a
Colab-side constant or an ad-hoc intensity cut.

That choice is load-bearing for honesty in two ways:

1. **It is detector-independent.** The mask comes from the raw image, never from
   Cellpose's output, so it cannot be tuned to flatter Cellpose. The identical mask
   gates the watershed pipeline's own output (`propagate._tight_flood_mask` uses
   ``compute_foam_mask`` too).
2. **It is verifiable.** :func:`restrict_to_foam_mask` applied to the committed RAW
   masks must reproduce the committed ``_clean`` masks. ``dev/cellpose_verify.py``
   asserts exactly that, so "the same step ran on Colab" is a measurement rather than
   a claim. If the two ever diverge, that is a fail-loud discrepancy, not a warning.

``min_overlap_frac`` (default 0.5) is the fraction of an object's pixels that must
fall inside the foam mask for it to be kept. A bubble on the raft edge is mostly
inside; a plate blob is entirely outside. The criterion is a majority vote, not a
threshold on a continuum, so it is not a knife-edge parameter — this is checked by a
sweep in ``dev/cellpose_verify.py`` rather than asserted.

What this module does NOT do
----------------------------
* It does not run Cellpose. Inference is external (GPU); this is load + adapt only.
* It does not filter by area or intensity. The watershed pipeline's
  ``min_bubble_area_px`` / Plateau-border intensity gate exist to repair *its* failure
  modes; imposing them on a different detector would confound "learned detection is
  better" with "we post-processed it more". Area filtering is available via
  ``min_area_px`` but defaults to **off**, and every result reports which was used.

Shapes: label maps int32 ``(H, W)``, 0 = background, contiguous ``1..K`` on return.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

from .config import PipelineConfig
from .dataset import EXPERIMENTS
from .guards import check_array
from .io_utils import load_experiment_frames
from .seg_eval import relabel_sequential
from .segmentation import SegmentationResult, compute_foam_mask

__all__ = [
    "CELLPOSE_ROOT",
    "cellpose_mask_path",
    "available_cellpose_frames",
    "load_cellpose_labels",
    "restrict_to_foam_mask",
    "build_cellpose_results",
    "count_trend_guard",
]

CELLPOSE_ROOT = Path("cellpose_out")


# --------------------------------------------------------------------------- #
# Discovery / IO
# --------------------------------------------------------------------------- #
def cellpose_mask_path(root: str | Path, exp: str, frame_index: int,
                       *, variant: str = "clean") -> Path:
    """``<root>/masks_<exp>/f<idx:03d>[_clean].npy`` (``variant`` in {clean, raw})."""
    if variant not in ("clean", "raw"):
        raise ValueError(f"variant must be 'clean' or 'raw', got {variant!r}")
    suffix = "_clean" if variant == "clean" else ""
    return Path(root) / f"masks_{exp}" / f"f{frame_index:03d}{suffix}.npy"


def available_cellpose_frames(root: str | Path, exp: str,
                              *, variant: str = "clean") -> list[int]:
    """Sorted frame indices for which a mask of ``variant`` exists (fail loud if none).

    Foam A and Foam C are deliberately NOT symmetric in what was computed on Colab;
    callers must branch on what is actually present rather than assume a full
    sequence. See ``docs/cellpose_replication.md``.
    """
    d = Path(root) / f"masks_{exp}"
    if not d.is_dir():
        raise FileNotFoundError(f"no Cellpose mask directory: {d}")
    suffix = "_clean" if variant == "clean" else ""
    out: list[int] = []
    for p in sorted(d.glob(f"f*{suffix}.npy")):
        stem = p.stem
        if variant == "clean":
            if not stem.endswith("_clean"):
                continue
            stem = stem[: -len("_clean")]
        elif stem.endswith("_clean"):
            continue
        out.append(int(stem[1:]))
    if not out:
        raise FileNotFoundError(f"no '{variant}' Cellpose masks in {d}")
    return sorted(out)


def load_cellpose_labels(root: str | Path, exp: str, frame_index: int,
                         *, variant: str = "clean") -> np.ndarray:
    """Load one Cellpose label map as int32, relabeled contiguous ``1..K``.

    Shape is checked against the experiment's registered ``image_hw`` (fail loud —
    a shape mismatch means the masks and frames are misaligned, which would silently
    corrupt every downstream number).
    """
    p = cellpose_mask_path(root, exp, frame_index, variant=variant)
    if not p.is_file():
        raise FileNotFoundError(f"Cellpose mask not found: {p}")
    arr = np.load(p)
    if arr.ndim != 2:
        raise ValueError(f"{p}: expected a 2D label map, got shape {arr.shape}")
    if exp in EXPERIMENTS and arr.shape != EXPERIMENTS[exp].image_hw:
        raise ValueError(
            f"{p}: shape {arr.shape} != registered image_hw "
            f"{EXPERIMENTS[exp].image_hw} for {exp}")
    if arr.min() < 0:
        raise ValueError(f"{p}: negative labels present")
    return relabel_sequential(arr.astype(np.int64))


# --------------------------------------------------------------------------- #
# The documented post-processing step
# --------------------------------------------------------------------------- #
def restrict_to_foam_mask(
    labels: np.ndarray,
    foam_mask: np.ndarray,
    *,
    min_overlap_frac: float = 0.5,
    min_area_px: int = 0,
) -> tuple[np.ndarray, dict]:
    """Drop objects that do not lie inside the foam aggregate; relabel ``1..K``.

    Cellpose segments the background plate into blobs (see the module docstring).
    An object is KEPT iff at least ``min_overlap_frac`` of its pixels fall inside
    ``foam_mask`` — a majority vote, so raft-edge bubbles (mostly inside) survive and
    plate blobs (entirely outside) do not.

    ``min_area_px`` is an OPTIONAL extra area filter, default 0 = off (# DECISION:
    see the module docstring — the watershed pipeline's area filter repairs a
    watershed-specific failure and is not imposed on a different detector by default).

    Parameters
    ----------
    labels : int (H, W), 0 = background.
    foam_mask : bool (H, W) from :func:`foam_gnn.segmentation.compute_foam_mask`.
    min_overlap_frac : float in (0, 1].
    min_area_px : int, >= 0.

    Returns
    -------
    (labels_out int32 (H, W) relabeled 1..K, info dict)
        ``info`` = ``n_in``, ``n_out``, ``n_dropped_outside``, ``n_dropped_small``,
        ``kept_area_px``, ``dropped_area_px``.
    """
    check_array("cellpose.labels", labels, ndim=2, nonneg=True)
    if foam_mask.shape != labels.shape:
        raise ValueError(f"foam_mask {foam_mask.shape} != labels {labels.shape}")
    if not (0.0 < min_overlap_frac <= 1.0):
        raise ValueError(f"min_overlap_frac must be in (0, 1], got {min_overlap_frac}")
    if min_area_px < 0:
        raise ValueError(f"min_area_px must be >= 0, got {min_area_px}")

    lab = np.asarray(labels, dtype=np.int64)
    n_in = int(lab.max())
    if n_in == 0:
        return np.zeros(lab.shape, np.int32), {
            "n_in": 0, "n_out": 0, "n_dropped_outside": 0, "n_dropped_small": 0,
            "kept_area_px": 0, "dropped_area_px": 0}

    fm = np.asarray(foam_mask, dtype=bool)
    total = np.bincount(lab.ravel(), minlength=n_in + 1)
    inside = np.bincount(lab[fm].ravel(), minlength=n_in + 1) if fm.any() else np.zeros(n_in + 1, np.int64)

    ids = np.arange(1, n_in + 1)
    frac = np.divide(inside[1:], np.maximum(total[1:], 1), dtype=float)
    keep_outside = frac >= min_overlap_frac
    keep_area = total[1:] >= max(min_area_px, 1)
    keep = keep_outside & keep_area

    out = np.zeros(lab.shape, np.int32)
    remap = np.zeros(n_in + 1, np.int32)
    remap[ids[keep]] = np.arange(1, int(keep.sum()) + 1, dtype=np.int32)
    out = remap[lab]

    return out, {
        "n_in": n_in,
        "n_out": int(keep.sum()),
        "n_dropped_outside": int((~keep_outside).sum()),
        "n_dropped_small": int((keep_outside & ~keep_area).sum()),
        "kept_area_px": int(total[1:][keep].sum()),
        "dropped_area_px": int(total[1:][~keep].sum()),
    }


# --------------------------------------------------------------------------- #
# Tiling expansion — IMPLEMENTED, MEASURED, AND NOT RECOMMENDED (see the DECISION)
# --------------------------------------------------------------------------- #
def expand_to_foam_mask(
    labels: np.ndarray,
    foam_mask: np.ndarray,
    elevation: np.ndarray | None = None,
    *,
    tight_dilate_px: int = 5,
) -> tuple[np.ndarray, dict]:
    """Flood Cellpose instances outward until they tile the foam interior.

    Cellpose instances are used as watershed **markers** and the unlabelled interior is
    flooded to the nearest basin over ``elevation`` (the Sato film-ridge map when
    supplied, so boundaries snap to real films rather than expanding blindly). The
    flood is confined to a tight hull of the instances themselves, so labels are never
    pushed out into the background rim.

    **Structural safety, not a tuned distance:** watershed-from-markers assigns every
    masked pixel to exactly one marker's basin, so an intervening labelled bubble always
    separates two non-neighbours — the same guarantee `adjacency_lengths_bridged` has,
    and stronger, because the basin boundary follows the film ridge.

    # DECISION — THIS IS IMPLEMENTED BUT DELIBERATELY NOT USED BY THE PIPELINE.
    # It was built to close the apparent <n> gap between Cellpose (5.03) and the
    # watershed (5.84). Measured against the hand-labelled ground truth, that gap is
    # NOT a Cellpose defect and this expansion makes accuracy worse:
    #   * the GT itself leaves 25.1% of the foam interior unlabelled (Cellpose 21.6%,
    #     watershed 12.4%) -- real foam interior is ~1/4 film and Plateau border, and a
    #     human labeller marks it as such. The watershed's low figure is the anomaly.
    #   * <n> measured on GT is 5.06 (all) / 5.62 (interior). Cellpose gives 5.10 /
    #     5.77 -- within +0.03 / +0.15 of truth. The watershed gives 5.67 / 5.71, i.e.
    #     it OVER-counts by +0.60 at the population level, all of it from edge bubbles
    #     whose flooded rims touch spuriously.
    #   * Cellpose bubbles are already 1.069x the area of their matched GT bubbles, so
    #     expanding them further moves areas away from truth -- and area feeds dA/dt.
    # See docs/tiling_gap_investigation.md. Kept in the codebase because the
    # measurement that rejected it is worth being able to reproduce.

    Returns ``(labels_out int32 (H, W), info)``.
    """
    check_array("expand.labels", labels, ndim=2, nonneg=True)
    if foam_mask.shape != labels.shape:
        raise ValueError(f"foam_mask {foam_mask.shape} != labels {labels.shape}")
    from skimage.segmentation import watershed

    lab = np.asarray(labels, dtype=np.int32)
    if lab.max() == 0:
        return lab.copy(), {"n_in": 0, "n_out": 0, "area_before": 0, "area_after": 0}

    hull = ndi.binary_fill_holes(
        ndi.binary_dilation(lab > 0, iterations=int(tight_dilate_px)))
    mask = np.asarray(foam_mask, dtype=bool) & hull
    elev = np.zeros(lab.shape, dtype=np.float32) if elevation is None \
        else np.asarray(elevation, dtype=np.float32)
    out = watershed(elev, markers=lab, mask=mask).astype(np.int32)

    inside = mask
    return out, {
        "n_in": int(lab.max()), "n_out": int(out.max()),
        "area_before": int((lab > 0).sum()), "area_after": int((out > 0).sum()),
        "unlabelled_before": float(((lab == 0) & inside).sum() / max(inside.sum(), 1)),
        "unlabelled_after": float(((out == 0) & inside).sum() / max(inside.sum(), 1)),
    }


# --------------------------------------------------------------------------- #
# Adapter to the Module-1 contract
# --------------------------------------------------------------------------- #
def build_cellpose_results(
    data_root: str | Path,
    exp: str,
    cfg: PipelineConfig,
    *,
    frame_indices: list[int] | None = None,
    cellpose_root: str | Path = CELLPOSE_ROOT,
    variant: str = "clean",
    apply_restriction: bool = False,
    min_overlap_frac: float = 0.5,
    min_area_px: int = 0,
) -> tuple[list[SegmentationResult], list[int], list[dict]]:
    """Load Cellpose masks for ``exp`` as Module-1 results, with the project's own
    foam mask and distance-to-edge map computed from the RAW frames.

    ``foam_mask`` / ``dist_to_edge`` always come from
    :func:`~foam_gnn.segmentation.compute_foam_mask` on the raw frame, so
    ``distance_to_evap_edge`` is measured identically to every previous result and is
    comparable across detectors.

    ``apply_restriction`` controls whether :func:`restrict_to_foam_mask` runs here.
    Default **False** because ``variant="clean"`` masks already had it applied on
    Colab; set ``variant="raw", apply_restriction=True`` to reproduce that locally
    (this is what ``dev/cellpose_verify.py`` does to prove the two agree).

    Returns ``(results, frame_indices, infos)``.
    """
    if exp not in EXPERIMENTS:
        raise KeyError(f"unknown experiment {exp!r}")
    idx = list(frame_indices) if frame_indices is not None \
        else available_cellpose_frames(cellpose_root, exp, variant=variant)
    _paths, images = load_experiment_frames(data_root, exp, indices=idx)

    results: list[SegmentationResult] = []
    infos: list[dict] = []
    for img, fi in zip(images, idx):
        labels = load_cellpose_labels(cellpose_root, exp, fi, variant=variant)
        foam, dist = compute_foam_mask(img, cfg.boundary)
        if foam.sum() == 0:
            raise RuntimeError(f"{exp} f{fi:03d}: foam mask empty — boundary detection failed")
        if apply_restriction:
            labels, info = restrict_to_foam_mask(
                labels, foam, min_overlap_frac=min_overlap_frac, min_area_px=min_area_px)
        else:
            info = {"n_in": int(labels.max()), "n_out": int(labels.max()),
                    "n_dropped_outside": 0, "n_dropped_small": 0}
        info["frame_index"] = int(fi)
        info["foam_area_frac"] = float(foam.mean())
        results.append(SegmentationResult(
            labels.astype(np.int32), foam, dist, n_bubbles=int(labels.max()),
            meta={"backend": "cellpose", "variant": variant, "frame_index": int(fi),
                  "restriction_applied": bool(apply_restriction),
                  "min_overlap_frac": float(min_overlap_frac),
                  "min_area_px": int(min_area_px)}))
        infos.append(info)
    return results, idx, infos


# --------------------------------------------------------------------------- #
# Detector-agnostic physical guard
# --------------------------------------------------------------------------- #
def count_trend_guard(
    counts: list[int] | np.ndarray,
    *,
    ratio: float = 1.50,
    patience: int = 3,
) -> dict:
    """Detector-agnostic fragmentation guard on a region-count series.

    Identical criterion to ``propagate.segment_track_propagated``'s inline
    FRAGMENTATION GUARD — a coarsening foam cannot gain bubbles, so a sustained rise
    of the count above its running minimum means interiors are fragmenting — but
    usable on ANY detector's counts, not only the propagating watershed. Extracted so
    that a learned detector faces exactly the test that rejected Foam C, rather than
    a differently-calibrated one.

    Returns ``{fires, first_fire_frame, worst_ratio, worst_frame, n_min, first, last,
    spearman_rho, spearman_p}``.
    """
    from scipy.stats import spearmanr

    c = np.asarray(counts, dtype=float)
    if c.size == 0:
        raise ValueError("empty count series")
    if ratio <= 1.0:
        raise ValueError(f"ratio must exceed 1.0, got {ratio}")

    run_min = c[0]
    above = 0
    first_fire = None
    worst_ratio, worst_frame = 1.0, 0
    for i, v in enumerate(c):
        r = v / max(run_min, 1.0)
        if r > worst_ratio:
            worst_ratio, worst_frame = float(r), int(i)
        above = above + 1 if v > ratio * max(run_min, 1.0) else 0
        if above >= patience and first_fire is None:
            first_fire = int(i)
        run_min = min(run_min, v)

    rho = p = float("nan")
    if c.size >= 3 and np.ptp(c) > 0:
        s = spearmanr(np.arange(c.size), c)
        rho, p = float(s.correlation), float(s.pvalue)
    return {
        "fires": first_fire is not None, "first_fire_frame": first_fire,
        "worst_ratio": float(worst_ratio), "worst_frame": int(worst_frame),
        "n_min": int(c.min()), "first": int(c[0]), "last": int(c[-1]),
        "spearman_rho": rho, "spearman_p": p, "n_frames": int(c.size),
        "guard_ratio": float(ratio), "guard_patience": int(patience),
    }
