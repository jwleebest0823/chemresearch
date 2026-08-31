"""
foam_gnn.segmentation  (MODULE 1)
=================================
Image -> per-frame labelled bubble masks.

Pipeline (classical, default ``WatershedSegmenter``)
----------------------------------------------------
1. **Grid suppression** - FFT notch removes the ~18.3 px periodic graph-paper
   grid found in Step-0. Without this the watershed shatters (896 "bubbles" on a
   frame that has ~150).
2. **Contrast normalization** - CLAHE handles the low global contrast
   (data lives in ~[12, 210]) and the mild vertical illumination gradient.
3. **Denoise** - edge-preserving bilateral filter.
4. **Film detection** - a Sato ridge filter responds to the thin dark films.
5. **Marker-controlled watershed** - seeds are ``h_maxima`` of the distance
   transform of the bubble interiors (the ``h`` knob controls over/under
   segmentation); watershed floods the film-ridge elevation so boundaries snap
   to real films.

Design decisions (review these)
-------------------------------
* Backend is swappable (``SegConfig.backend``). The classical watershed is the
  default; ``SAMSegmenter`` / ``FoamQuantSegmenter`` are stubs for the likely
  upgrade given the low contrast. All implement the same ``Segmenter`` protocol
  and return a ``SegmentationResult``, so nothing downstream changes.
* ``h_maxima`` is the single most important knob and a *research decision*; a
  fixed value cannot be optimal across the whole coarsening series.

KNOWN LIMITATIONS (tested on the 5 exp1 samples — see README "what is tested")
* The smallest bubbles in dense early frames are merged/missed.
* The foam-boundary mask is slightly generous; ``BoundaryConfig.boundary_erode_px``
  is a blunt tightening knob, not a principled snap-to-film.
* Vertex-angle estimation in ``flag_suspicious_vertices`` is approximate.

Shapes: images are ``(H, W)`` uint8; label maps are ``(H, W)`` int32 with 0 = bg.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.measure import regionprops
from skimage.morphology import h_maxima
from skimage.segmentation import find_boundaries, watershed

from .config import BoundaryConfig, PipelineConfig, PreprocConfig, SegConfig
from .guards import check_array

__all__ = [
    "SegmentationResult",
    "preprocess",
    "compute_foam_mask",
    "foam_edge_density",
    "foam_mask_clipping",
    "Segmenter",
    "WatershedSegmenter",
    "SAMSegmenter",
    "FoamQuantSegmenter",
    "build_segmenter",
    "qc_overlay",
    "flag_suspicious_vertices",
]


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class SegmentationResult:
    """Output of segmenting one frame.

    Attributes
    ----------
    labels : np.ndarray
        ``int32 (H, W)``; 0 = background/film, 1..n_bubbles = bubbles (contiguous).
    foam_mask : np.ndarray
        ``bool (H, W)``; True inside the foam aggregate.
    dist_to_edge : np.ndarray
        ``float32 (H, W)``; Euclidean distance (px) from each foam pixel to the
        foam boundary (0 outside). Feeds the radial-gradient hypothesis test.
    n_bubbles : int
    frame_path : Path | None
    meta : dict
        Free-form provenance (params used, foam area fraction, ...).
    """

    labels: np.ndarray
    foam_mask: np.ndarray
    dist_to_edge: np.ndarray
    n_bubbles: int
    frame_path: Path | None = None
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
def _fft_notch(img: np.ndarray, cfg: PreprocConfig) -> np.ndarray:
    """Suppress the periodic grid by notching discrete spectral peaks.

    The grid is periodic -> energy concentrated at a few off-centre peaks.
    Bubbles are aperiodic -> energy spread out. Notching narrow disks around the
    peaks (while preserving the low-frequency core) removes the grid with minimal
    damage to bubble structure.

    img : uint8 (H, W) -> returns uint8 (H, W).
    """
    h, w = img.shape
    f = np.fft.fftshift(np.fft.fft2(img.astype(np.float64)))
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    rad = np.hypot(yy - cy, xx - cx)
    cand = np.abs(f).copy()
    cand[rad < cfg.notch_exclude_r] = 0.0
    if cand.max() <= 0:
        return img.copy()
    peaks = (cand == ndi.maximum_filter(cand, size=9)) & (cand > cfg.notch_peak_rel * cand.max())
    keep = np.ones((h, w), dtype=bool)
    r2 = cfg.notch_radius ** 2
    for py, px in zip(*np.where(peaks)):
        keep[(yy - py) ** 2 + (xx - px) ** 2 <= r2] = False
    out = np.real(np.fft.ifft2(np.fft.ifftshift(f * keep)))
    return np.clip(out, 0, 255).astype(np.uint8)


def preprocess(img: np.ndarray, cfg: PreprocConfig) -> np.ndarray:
    """Grayscale -> grid-suppress -> CLAHE -> denoise.

    img : uint8 (H, W) -> returns uint8 (H, W) cleaned image.
    """
    check_array("preprocess.img", img, ndim=2, dtype=np.uint8)
    g = img
    if cfg.grid_suppression == "fft_notch":
        g = _fft_notch(g, cfg)
    elif cfg.grid_suppression != "none":
        raise ValueError(f"unknown grid_suppression={cfg.grid_suppression!r}")
    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=cfg.clahe_grid)
    g = clahe.apply(g)
    if cfg.denoise == "bilateral":
        g = cv2.bilateralFilter(g, cfg.bilateral_d, cfg.bilateral_sigma, cfg.bilateral_sigma)
    elif cfg.denoise != "none":
        raise ValueError(f"unknown denoise={cfg.denoise!r}")
    return check_array("preprocess.out", g, ndim=2, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# Foam boundary
# --------------------------------------------------------------------------- #
def foam_edge_density(img: np.ndarray, cfg: BoundaryConfig) -> np.ndarray:
    """Blurred Sobel-magnitude map: high inside the foam (films), low on background.

    img : uint8 (H, W) -> float64 (H, W).
    """
    gl = cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=(8, 8)).apply(img)
    sob = cv2.magnitude(
        cv2.Sobel(gl, cv2.CV_64F, 1, 0, ksize=3),
        cv2.Sobel(gl, cv2.CV_64F, 0, 1, ksize=3),
    )
    return cv2.GaussianBlur(sob, (0, 0), cfg.edge_sigma)


def _density_threshold(dens: np.ndarray, cfg: BoundaryConfig) -> float:
    """Split the edge-density map into background / foam. float64 (H, W) -> threshold.

    See the DECISION on ``BoundaryConfig.thresh_mode``: the legacy ``mean + k*std`` rule
    scales with the foam's own area fraction and silently eats foam on frames the foam
    fills. Otsu uses the valley between the two density modes instead.
    """
    if cfg.thresh_mode == "mean_k_std":
        return float(dens.mean() + cfg.thresh_k * dens.std())
    if cfg.thresh_mode not in ("li", "otsu"):
        raise ValueError(
            f"unknown BoundaryConfig.thresh_mode={cfg.thresh_mode!r}; "
            "choose from {'li', 'otsu', 'mean_k_std'}"
        )
    if float(np.ptp(dens)) < 1e-9:
        raise RuntimeError(
            "edge-density map is constant: boundary detection cannot separate "
            "foam from background on this frame"
        )
    from skimage.filters import threshold_li, threshold_otsu
    thr = float(threshold_li(dens) if cfg.thresh_mode == "li" else threshold_otsu(dens))
    if not np.isfinite(thr):
        raise RuntimeError(f"{cfg.thresh_mode} threshold is not finite on this frame")
    return thr


def _mask_from_density(dens: np.ndarray, thr: float, cfg: BoundaryConfig) -> np.ndarray | None:
    """density (H,W) + threshold -> foam mask bool (H,W), or None if nothing survives.

    close -> largest connected component -> close -> fill holes.
    """
    m = cv2.morphologyEx(
        (dens > thr).astype(np.uint8), cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.density_close_ksize,) * 2))
    n, lab, stats, _c = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    out = cv2.morphologyEx(
        (lab == big).astype(np.uint8), cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.mask_close_ksize,) * 2))
    return ndi.binary_fill_holes(out).astype(bool)


def _stable_threshold(dens: np.ndarray, thr0: float, cfg: BoundaryConfig) -> float:
    """Move the threshold off a CLIFF onto a PLATEAU. float -> float.

    # DECISION: measured failure (docs/exp1_churn_bisection.md) — on late Foam A frames a
    # low-contrast halo makes the mask area a STEP function of the threshold: at exp1
    # f175 the mask jumps 20.2% -> 30.2% of the frame between k=1.00 and k=0.95 of the
    # legacy threshold, and the cliff MOVES between frames (f197's sits at 0.95-0.93).
    # Li lands at k~0.94, i.e. on the cliff, so the mask flickers frame to frame and the
    # tracker re-mints ids — the exp1_run1 churn. No scalar threshold is safe there, so
    # the threshold is chosen by LOCAL STABILITY instead of by value: step up while a
    # small upward perturbation would shrink the mask by more than `tol`. Frames already
    # on a plateau (all of exp3, early Foam A) are untouched, so this keeps the Li
    # coverage gain and only acts where the measurement says the choice is ill-posed.
    """
    if cfg.thresh_stability != "on":
        return thr0
    eps, tol = cfg.thresh_stability_eps, cfg.thresh_stability_tol
    if not (0.0 < eps < 1.0) or not (0.0 < tol < 1.0):
        raise ValueError(
            f"thresh_stability_eps={eps} and _tol={tol} must both lie in (0, 1)")
    thr = float(thr0)
    for _ in range(int(cfg.thresh_stability_max_steps)):
        m = _mask_from_density(dens, thr, cfg)
        if m is None:
            return thr
        a = float(m.mean())
        m2 = _mask_from_density(dens, thr * (1.0 + eps), cfg)
        a2 = 0.0 if m2 is None else float(m2.mean())
        if a <= 0.0 or (a - a2) / a <= tol:
            return thr                      # on a plateau
        thr *= 1.0 + eps                    # on a cliff: step up and re-test
    return thr


def foam_mask_clipping(mask: np.ndarray) -> float:
    """Fraction of the image border covered by foam (0 = free-floating, 1 = fills frame).

    When this is large the foam extends beyond the field of view, so ``dist_to_edge``
    measures distance to the *frame*, not to the evaporation edge, and every radial /
    edge-distance analysis on that frame is uninterpretable.

    mask : bool (H, W) -> float in [0, 1].
    """
    border = np.concatenate([mask[0, :], mask[-1, :], mask[1:-1, 0], mask[1:-1, -1]])
    return float(border.mean()) if border.size else 0.0


def compute_foam_mask(img: np.ndarray, cfg: BoundaryConfig) -> tuple[np.ndarray, np.ndarray]:
    """Detect the outer foam aggregate and its distance-to-edge map.

    The foam is distinguished from background not by being darker (interiors are
    bright too) but by *containing films* -> high local edge density. We threshold
    a blurred Sobel-magnitude map, keep the largest connected component, fill
    holes, and distance-transform the interior.

    img : uint8 (H, W) -> (foam_mask bool (H, W), dist_to_edge float32 (H, W)).
    """
    check_array("foam_mask.img", img, ndim=2, dtype=np.uint8)
    dens = foam_edge_density(img, cfg)
    thr = _stable_threshold(dens, _density_threshold(dens, cfg), cfg)
    mask = _mask_from_density(dens, thr, cfg)
    if mask is None:
        h, w = img.shape
        return np.zeros((h, w), bool), np.zeros((h, w), np.float32)
    if cfg.boundary_erode_px > 0:
        mask = ndi.binary_erosion(mask, iterations=cfg.boundary_erode_px)
    clip = foam_mask_clipping(mask)
    if clip > cfg.clip_border_warn_frac:
        warnings.warn(
            f"foam mask covers {clip:.0%} of the image border (> "
            f"{cfg.clip_border_warn_frac:.0%}): the foam extends beyond the field of "
            "view, so dist_to_edge measures distance to the FRAME, not to the "
            "evaporation edge. Radial / edge-distance results on this frame are not "
            "interpretable as distance-to-evaporation-edge.",
            RuntimeWarning,
            stacklevel=2,
        )
    dist = ndi.distance_transform_edt(mask).astype(np.float32)
    return mask, check_array("dist_to_edge", dist, ndim=2, finite=True, nonneg=True)


# --------------------------------------------------------------------------- #
# Segmenter interface + backends
# --------------------------------------------------------------------------- #
class Segmenter(Protocol):
    """Backend interface. Any implementation maps a grayscale frame to a
    ``SegmentationResult`` so the rest of the pipeline is backend-agnostic."""

    def segment(self, img: np.ndarray) -> SegmentationResult: ...


class WatershedSegmenter:
    """Classical marker-controlled watershed (default backend)."""

    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg = cfg

    def segment(self, img: np.ndarray) -> SegmentationResult:
        check_array("segment.img", img, ndim=2, dtype=np.uint8)
        seg, bnd = self.cfg.seg, self.cfg.boundary
        h, w = img.shape

        clean = preprocess(img, self.cfg.preproc)
        foam, dist = compute_foam_mask(img, bnd)
        if foam.sum() == 0:
            raise RuntimeError("foam mask empty: boundary detection failed for this frame")

        # film "ridge" probability in [0, 1]; high on dark films
        film = sato(clean.astype(np.float64), sigmas=seg.sato_sigmas, black_ridges=True)
        rng = float(np.ptp(film))
        film = (film - film.min()) / (rng + 1e-9)

        interior = ndi.binary_opening((film < seg.interior_thresh) & foam, structure=np.ones((3, 3)))
        dt = ndi.gaussian_filter(ndi.distance_transform_edt(interior), seg.dt_smooth_sigma)
        seeds = h_maxima(dt, seg.h_maxima) * foam
        markers, n_seed = ndi.label(seeds)
        if n_seed == 0:
            raise RuntimeError(
                "no watershed seeds found; lower SegConfig.h_maxima or check preprocessing"
            )
        raw = watershed(film, markers, mask=foam)

        # area filtering -> contiguous relabel
        labels = np.zeros((h, w), np.int32)
        max_area = seg.max_bubble_area_frac * float(foam.sum())
        k = 0
        n_too_big = 0
        for r in range(1, int(raw.max()) + 1):
            area = int((raw == r).sum())
            if area < seg.min_bubble_area_px:
                continue
            if area > max_area:
                n_too_big += 1  # kept but flagged (likely a merge/under-segmentation)
            k += 1
            labels[raw == r] = k

        if k == 0:
            raise RuntimeError("segmentation produced zero bubbles after area filtering")

        check_array("labels", labels, ndim=2, dtype=np.int32, nonneg=True)
        meta = {
            "backend": "watershed",
            "n_seeds": int(n_seed),
            "n_regions_too_big": int(n_too_big),
            "foam_area_px": int(foam.sum()),
            "foam_area_frac": float(foam.sum()) / (h * w),
            "h_maxima": seg.h_maxima,
        }
        return SegmentationResult(labels, foam, dist, n_bubbles=k, meta=meta)


class SAMSegmenter:
    """Stub for a Segment-Anything backend (same interface)."""

    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg = cfg

    def segment(self, img: np.ndarray) -> SegmentationResult:  # pragma: no cover - stub
        raise NotImplementedError(
            "SAMSegmenter is a placeholder for a future learned backend. "
            "Use SegConfig.backend='watershed' for now."
        )


class FoamQuantSegmenter:
    """Stub for a FoamQuant backend (same interface)."""

    def __init__(self, cfg: PipelineConfig) -> None:
        self.cfg = cfg

    def segment(self, img: np.ndarray) -> SegmentationResult:  # pragma: no cover - stub
        raise NotImplementedError(
            "FoamQuantSegmenter is a placeholder for a future backend. "
            "Use SegConfig.backend='watershed' for now."
        )


def build_segmenter(cfg: PipelineConfig) -> Segmenter:
    """Factory: instantiate the backend named in ``cfg.seg.backend``."""
    backends = {
        "watershed": WatershedSegmenter,
        "sam": SAMSegmenter,
        "foamquant": FoamQuantSegmenter,
    }
    if cfg.seg.backend not in backends:
        raise ValueError(f"unknown backend {cfg.seg.backend!r}; choose from {sorted(backends)}")
    return backends[cfg.seg.backend](cfg)


# --------------------------------------------------------------------------- #
# QC / correctness checks
# --------------------------------------------------------------------------- #
def qc_overlay(img: np.ndarray, result: SegmentationResult, *, draw_foam: bool = True) -> np.ndarray:
    """Overlay segmentation boundaries (red) and the foam outline (cyan) on the
    raw frame for visual QC.

    img : uint8 (H, W) -> returns uint8 (H, W, 3) RGB.
    """
    check_array("qc_overlay.img", img, ndim=2, dtype=np.uint8)
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    rgb[find_boundaries(result.labels, mode="outer")] = (0, 0, 255)
    if draw_foam:
        cont, _ = cv2.findContours(
            result.foam_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(rgb, cont, -1, (255, 255, 0), 2)
    return cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)


def flag_suspicious_vertices(
    labels: np.ndarray,
    *,
    ring_radius: int = 10,
    angle_tol_deg: float = 35.0,
    include_angle_in_flag: bool = False,
) -> list[dict]:
    """Find film junctions and flag those that violate Plateau's laws.

    Plateau: films meet 3-at-a-time at ~120 degrees. Two checks are returned:

    * **order** (reliable) - the number of distinct bubbles meeting at the
      junction. ``order != 3`` is a genuine topological violation and drives the
      ``suspicious`` flag by default.
    * **angle** (APPROXIMATE) - the deviation of the three film directions from
      120 degrees, estimated by sampling boundary pixels on a ring around the
      vertex. On pixelated watershed lines this is noisy at the ~20-30 deg level,
      so it is reported as ``angle_dev_deg`` / ``angle_flag`` but is *not* folded
      into ``suspicious`` unless ``include_angle_in_flag=True``. Treat it as a
      coarse diagnostic, not a metric.

    labels : int32 (H, W) -> list of dicts with keys
        {y, x, order, suspicious, reason, angle_dev_deg, angle_flag}.
    """
    check_array("flag_vertices.labels", labels, ndim=2, nonneg=True)
    bnd_thick = find_boundaries(labels, mode="thick")   # for vertex detection
    bnd_thin = find_boundaries(labels, mode="inner")    # thinner, for angle sampling
    H, W = labels.shape

    # vertex pixels: boundary pixels touching >=3 distinct bubble labels
    vmap = np.zeros(labels.shape, bool)
    ys, xs = np.where(bnd_thick)
    for y, x in zip(ys, xs):
        sub = labels[max(0, y - 1): y + 2, max(0, x - 1): x + 2]
        if len({int(v) for v in np.unique(sub) if v > 0}) >= 3:
            vmap[y, x] = True

    vlab, n = ndi.label(vmap, structure=np.ones((3, 3)))
    ry, rx = np.ogrid[:H, :W]
    out: list[dict] = []
    for i in range(1, n + 1):
        cy, cx = (float(c) for c in ndi.center_of_mass(vlab == i))
        yy, xx = np.where(vlab == i)
        order = len({int(v) for py, px in zip(yy, xx)
                     for v in np.unique(labels[max(0, py - 1): py + 2, max(0, px - 1): px + 2]) if v > 0})

        # reliable Plateau-order check
        suspicious = order != 3
        reason = "" if order == 3 else f"{order}-way junction (Plateau expects 3)"

        # approximate angle check (secondary; off by default)
        dev = float("nan")
        ring = bnd_thin & (np.abs(np.hypot(ry - cy, rx - cx) - ring_radius) <= 1.5)
        rj, ri = np.where(ring)
        if rj.size >= 3:
            ang = np.sort(np.degrees(np.arctan2(rj - cy, ri - cx)) % 360.0)
            gaps = np.diff(np.concatenate([ang, ang[:1] + 360.0]))
            cut = np.where(gaps > 25.0)[0]
            groups = np.split(ang, cut[:-1] + 1) if cut.size > 1 else [ang]
            if len(groups) == 3:
                centers = sorted(float(np.mean(g)) for g in groups)
                seps = np.diff(centers + [centers[0] + 360.0])
                dev = float(np.max(np.abs(np.asarray(seps) - 120.0)))
        angle_flag = bool(np.isfinite(dev) and dev > angle_tol_deg and order == 3)
        if include_angle_in_flag and angle_flag:
            suspicious = True
            reason = reason or f"3-way but angles deviate ~{dev:.0f} deg from 120 (approx)"

        out.append(dict(y=cy, x=cx, order=order, suspicious=suspicious,
                        reason=reason, angle_dev_deg=dev, angle_flag=angle_flag))
    return out
