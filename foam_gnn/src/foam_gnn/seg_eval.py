"""
foam_gnn.seg_eval
=================
Ground-truth **segmentation-evaluation harness**. Given a hand-labeled ground-truth
label mask and a predicted segmentation of the SAME raw frame, it measures per-bubble
detection accuracy, boundary quality, Plateau-junction consistency, and
over/under-segmentation — **every metric stratified by bubble size and by
distance-to-evaporation-edge**, because the project's failure is specifically on
small, near-edge bubbles and a foam-averaged number would hide it.

Ground-truth label format (# DECISION)
--------------------------------------
* One **integer label per bubble**, ``0`` = background/film. Stored as a lossless
  **16-bit PNG** (supports the ~100-300 labels of a dense frame; 8-bit would clip),
  one file per labeled frame at ``<gt_root>/<exp>/f<abs_frame_idx:03d>.png``.
  (TIFF is also accepted.) Labeled on the **raw frame**, so GT and prediction share
  native pixel coordinates and match by pixel overlap directly.
* A ``<gt_root>/manifest.csv`` lists provenance: ``exp, frame_index, path, labeler,
  date, notes``. :func:`load_gt_manifest` reads it; :func:`load_gt_frame` loads and
  validates one mask (dtype/shape/labels), relabeling to contiguous ``1..K``.

Matching criterion (# DECISION)
-------------------------------
Per-bubble detection uses **one-to-one Hungarian matching** on the GT×pred IoU
matrix (maximizing total IoU). A matched pair is a **true positive only if its IoU
≥ threshold**; unmatched GT = false negative (miss), unmatched pred = false positive
(spurious). Reported at several thresholds (0.5 loose detection → 0.9 strict
boundary). One-to-one is deliberate: splits/merges are then *visible* as FN+FP pairs
and are also counted explicitly by :func:`split_merge_diagnostics` (which is
many-to-one/one-to-many by design).

Shapes/dtypes: label maps are ``int (H, W)``, 0 = background. Distances in px, areas
in px². This module is torch-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from scipy.optimize import linear_sum_assignment

from .config import PipelineConfig, SegEvalConfig
from .guards import check_array

__all__ = [
    "load_gt_frame",
    "load_gt_manifest",
    "relabel_sequential",
    "bubble_table",
    "gt_foam_distance",
    "iou_contingency",
    "match_hungarian",
    "detection_metrics",
    "assign_strata",
    "stratified_detection",
    "split_merge_diagnostics",
    "plateau_fraction",
    "evaluate_frame",
    "FrameEval",
]


# --------------------------------------------------------------------------- #
# Ground-truth IO + validation
# --------------------------------------------------------------------------- #
def _imread_unicode(path: Path) -> np.ndarray:
    """Read an image from a possibly non-ASCII path (cv2.imread fails on 문서).

    Uses ``np.fromfile`` + ``cv2.imdecode`` with UNCHANGED|ANYDEPTH so 16-bit label
    PNGs load without clipping.
    """
    buf = np.fromfile(str(path), dtype=np.uint8)
    if buf.size == 0:
        raise FileNotFoundError(f"empty or missing GT file: {path}")
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH)
    if img is None:
        raise ValueError(f"could not decode GT image: {path}")
    return img


def relabel_sequential(labels: np.ndarray) -> np.ndarray:
    """Relabel a label map to contiguous ``1..K`` (0 stays background). int32."""
    out = np.zeros(labels.shape, dtype=np.int32)
    uniq = [int(v) for v in np.unique(labels) if v > 0]
    for k, v in enumerate(uniq, start=1):
        out[labels == v] = k
    return out


def load_gt_frame(
    path: str | Path,
    *,
    expected_hw: tuple[int, int] | None = None,
    min_bubble_area_px: int = 8,
) -> tuple[np.ndarray, dict]:
    """Load + validate one ground-truth label mask. Fail loud on structural errors.

    Returns ``(labels int32 (H,W) relabeled 1..K, info)``. ``info`` reports
    ``n_labels`` and ``n_tiny`` (labels below ``min_bubble_area_px`` — a WARNING,
    not an error, since near-limit bubbles are the point; the caller decides).

    Raises on: non-2D, non-integer, negative labels, or shape ≠ ``expected_hw``.
    """
    raw = _imread_unicode(Path(path))
    if raw.ndim == 3:                       # a colour export → collapse if single-channel-like
        if raw.shape[2] in (3, 4) and np.all(raw[..., 0] == raw[..., 1]) and np.all(raw[..., 1] == raw[..., 2]):
            raw = raw[..., 0]
        else:
            raise ValueError(f"GT {path} is multi-channel colour; expected a single-channel label mask")
    if raw.ndim != 2:
        raise ValueError(f"GT {path}: expected 2D label mask, got shape {raw.shape}")
    if not np.issubdtype(raw.dtype, np.integer):
        # napari sometimes writes float labels; accept only if integer-valued
        if not np.all(raw == np.round(raw)):
            raise ValueError(f"GT {path}: non-integer labels (dtype {raw.dtype})")
        raw = raw.astype(np.int64)
    if raw.min() < 0:
        raise ValueError(f"GT {path}: negative labels present")
    if expected_hw is not None and raw.shape != tuple(expected_hw):
        raise ValueError(f"GT {path}: shape {raw.shape} != expected {tuple(expected_hw)}")
    labels = relabel_sequential(raw)
    areas = np.bincount(labels.ravel())[1:] if labels.max() > 0 else np.array([], dtype=int)
    info = {"path": str(path), "n_labels": int(labels.max()),
            "n_tiny": int(np.sum(areas < min_bubble_area_px)),
            "min_area_px": int(areas.min()) if areas.size else 0}
    return check_array("gt.labels", labels, ndim=2, nonneg=True), info


def load_gt_manifest(gt_root: str | Path, *, usable_only: bool = True) -> pd.DataFrame:
    """Load ``<gt_root>/manifest.csv`` (provenance of the labeled frames).

    Expected columns: ``exp, frame_index, path`` (+ optional ``labeler, date, notes,
    seed_method, preseed_source, status``). ``path`` is resolved relative to
    ``gt_root`` if not absolute.

    ``usable_only`` (default True) DROPS rows whose ``status`` marks them as not
    ground truth — currently ``inspected_not_corrected`` / ``abandoned``. A frame that
    was only opened still holds the raw automatic pre-seed, so scoring the segmenter
    against it would compare the method to its own output and report a perfect score.
    Excluding them by default makes that mistake impossible; pass ``usable_only=False``
    to see every row (e.g. for auditing).
    """
    root = Path(gt_root)
    man = root / "manifest.csv"
    if not man.is_file():
        raise FileNotFoundError(
            f"GT manifest not found: {man}. Expected columns exp,frame_index,path "
            "(one row per labeled frame).")
    df = pd.read_csv(man, keep_default_na=False)
    for c in ("exp", "frame_index", "path"):
        if c not in df.columns:
            raise ValueError(f"{man}: missing required column {c!r}")
    if usable_only and "status" in df.columns:
        from .gt_preseed import UNUSABLE_STATUSES
        df = df[~df["status"].astype(str).str.strip().isin(UNUSABLE_STATUSES)].reset_index(drop=True)
    df["path"] = [p if Path(p).is_absolute() else str(root / p) for p in df["path"]]
    return df


# --------------------------------------------------------------------------- #
# Region tables + stratification geometry
# --------------------------------------------------------------------------- #
def bubble_table(labels: np.ndarray, dist_map: np.ndarray | None = None) -> pd.DataFrame:
    """Per-label ``label | area | cx | cy | dist`` for a label map (0 = background).

    ``dist`` = ``dist_map`` sampled at the (rounded) centroid, or NaN if no map.
    """
    check_array("bubble_table.labels", labels, ndim=2, nonneg=True)
    rows: list[dict] = []
    if labels.max() == 0:
        return pd.DataFrame(columns=["label", "area", "cx", "cy", "dist"])
    objs = ndi.find_objects(labels)
    for lab, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sub = labels[sl] == lab
        area = int(sub.sum())
        ys, xs = np.nonzero(sub)
        cy = float(ys.mean() + sl[0].start)
        cx = float(xs.mean() + sl[1].start)
        d = float("nan")
        if dist_map is not None:
            yi = int(min(max(round(cy), 0), dist_map.shape[0] - 1))
            xi = int(min(max(round(cx), 0), dist_map.shape[1] - 1))
            d = float(dist_map[yi, xi])
        rows.append({"label": lab, "area": area, "cx": cx, "cy": cy, "dist": d})
    return pd.DataFrame(rows)


def gt_foam_distance(gt_labels: np.ndarray) -> np.ndarray:
    """Distance-to-evaporation-edge map from the GT foam aggregate (GT-defined).

    The foam aggregate = filled union of all GT bubbles; its EDT gives each interior
    pixel's distance to the outer foam boundary. GT-based (independent of the
    predicted foam mask) so stratification does not depend on the method under test.
    float32 (H, W).
    """
    foam = ndi.binary_fill_holes(gt_labels > 0)
    return ndi.distance_transform_edt(foam).astype(np.float32)


# --------------------------------------------------------------------------- #
# IoU + Hungarian matching
# --------------------------------------------------------------------------- #
def iou_contingency(gt: np.ndarray, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """IoU matrix between GT labels (rows) and predicted labels (cols).

    Both must be relabeled ``1..K`` (call :func:`relabel_sequential` first). Returns
    ``(iou (n_gt, n_pred), area_gt (n_gt,), area_pred (n_pred,))``. Background (0) is
    excluded. Uses a pixel contingency table (no per-pair masking).
    """
    if gt.shape != pred.shape:
        raise ValueError(f"gt {gt.shape} != pred {pred.shape}")
    n_gt, n_pred = int(gt.max()), int(pred.max())
    area_gt = np.bincount(gt.ravel(), minlength=n_gt + 1)[1:].astype(np.int64)
    area_pred = np.bincount(pred.ravel(), minlength=n_pred + 1)[1:].astype(np.int64)
    if n_gt == 0 or n_pred == 0:
        return np.zeros((n_gt, n_pred), float), area_gt, area_pred
    # contingency of overlapping foreground pixels
    fg = (gt > 0) & (pred > 0)
    pair = (gt[fg].astype(np.int64) - 1) * n_pred + (pred[fg].astype(np.int64) - 1)
    inter = np.bincount(pair, minlength=n_gt * n_pred).reshape(n_gt, n_pred).astype(np.int64)
    union = area_gt[:, None] + area_pred[None, :] - inter
    iou = np.where(union > 0, inter / union, 0.0)
    return iou, area_gt, area_pred


def match_hungarian(iou: np.ndarray, threshold: float) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """One-to-one Hungarian match maximizing total IoU; keep pairs with IoU ≥ threshold.

    Returns ``(matches [(gt_idx, pred_idx, iou), ...], unmatched_gt_idx,
    unmatched_pred_idx)`` with 0-based indices into the IoU matrix.
    """
    n_gt, n_pred = iou.shape
    matches: list[tuple[int, int, float]] = []
    matched_g, matched_p = set(), set()
    if n_gt and n_pred:
        gi, pj = linear_sum_assignment(-iou)          # maximize IoU
        for g, p in zip(gi, pj):
            if iou[g, p] >= threshold:
                matches.append((int(g), int(p), float(iou[g, p])))
                matched_g.add(int(g))
                matched_p.add(int(p))
    unmatched_gt = [g for g in range(n_gt) if g not in matched_g]
    unmatched_pred = [p for p in range(n_pred) if p not in matched_p]
    return matches, unmatched_gt, unmatched_pred


def detection_metrics(iou: np.ndarray, thresholds: tuple[float, ...]) -> pd.DataFrame:
    """Precision/recall/F1 (+ TP/FP/FN and mean matched IoU) per IoU threshold."""
    n_gt, n_pred = iou.shape
    rows: list[dict] = []
    for tau in thresholds:
        matches, un_gt, un_pred = match_hungarian(iou, tau)
        tp = len(matches)
        fn, fp = len(un_gt), len(un_pred)
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        rec = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if prec and rec and np.isfinite(prec) and np.isfinite(rec) and (prec + rec) > 0 else 0.0
        rows.append({"iou_threshold": tau, "n_gt": n_gt, "n_pred": n_pred,
                     "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec,
                     "f1": f1, "mean_matched_iou": float(np.mean([m[2] for m in matches])) if matches else float("nan")})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Stratification
# --------------------------------------------------------------------------- #
def assign_strata(
    gt_tab: pd.DataFrame,
    cfg: SegEvalConfig,
    *,
    size_edges: np.ndarray | None = None,
    dist_max: float | None = None,
) -> pd.DataFrame:
    """Attach ``size_bin`` (small/medium/large by area) + ``dist_bin`` to GT bubbles.

    ``size_edges`` are area-tercile edges (pooled across frames when given, else
    computed from this frame). ``dist_bin`` splits ``[0, dist_max]`` into
    ``n_dist_bins`` equal shells (bin 0 = near-edge). Returns a copy of ``gt_tab``
    with ``size_bin`` (str) and ``dist_bin`` (int) columns.
    """
    tab = gt_tab.copy()
    if tab.empty:
        tab["size_bin"] = pd.Series(dtype=str)
        tab["dist_bin"] = pd.Series(dtype=int)
        return tab
    area = tab["area"].to_numpy(dtype=float)
    if size_edges is None:
        qs = np.linspace(0, 1, cfg.n_size_bins + 1)[1:-1]
        size_edges = np.quantile(area, qs)
    idx = np.digitize(area, size_edges)
    labels = np.array(cfg.size_bin_labels)
    tab["size_bin"] = labels[np.clip(idx, 0, len(labels) - 1)]
    dmax = float(dist_max if dist_max is not None else np.nanmax(tab["dist"].to_numpy()))
    if not np.isfinite(dmax) or dmax <= 0:
        tab["dist_bin"] = 0
    else:
        edges = np.linspace(0.0, dmax + 1e-9, cfg.n_dist_bins + 1)
        tab["dist_bin"] = np.clip(np.digitize(tab["dist"].to_numpy(dtype=float), edges) - 1,
                                  0, cfg.n_dist_bins - 1)
    return tab


def stratified_detection(
    gt_tab: pd.DataFrame,
    matches: list[tuple[int, int, float]],
    cfg: SegEvalConfig,
) -> pd.DataFrame:
    """Recall per (size_bin, dist_bin): fraction of GT bubbles that were matched.

    ``gt_tab`` must carry ``size_bin``/``dist_bin`` (from :func:`assign_strata`) and
    be indexed so row order == GT-label-1 == IoU-matrix row. Recall (not precision)
    is stratified because a GT-defined stratum is only meaningful for GT bubbles;
    precision/FP are reported globally in :func:`detection_metrics`.
    """
    matched_g = {g for g, _p, _i in matches}
    tab = gt_tab.reset_index(drop=True).copy()
    tab["matched"] = [i in matched_g for i in range(len(tab))]
    rows: list[dict] = []
    for (sb, db), g in tab.groupby(["size_bin", "dist_bin"]):
        rows.append({"size_bin": sb, "dist_bin": int(db), "n_gt": int(len(g)),
                     "n_matched": int(g["matched"].sum()),
                     "recall": float(g["matched"].mean())})
    return pd.DataFrame(rows).sort_values(["size_bin", "dist_bin"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Over / under-segmentation
# --------------------------------------------------------------------------- #
def split_merge_diagnostics(
    gt: np.ndarray,
    pred: np.ndarray,
    gt_tab: pd.DataFrame,
    cfg: SegEvalConfig,
) -> tuple[pd.DataFrame, dict]:
    """Per-GT-bubble split/merge flags, stratified.

    * **split** = one GT bubble covered (≥ ``cover_frac`` of its area) by ≥2 predicted
      regions (over-segmentation).
    * **merge** = a predicted region covers (≥ ``cover_frac`` of ITS OWN area) ≥2 GT
      bubbles; each such GT bubble is flagged merged (under-segmentation).

    Returns ``(per_stratum_df, totals)``. ``gt_tab`` must carry size/dist bins and be
    row-ordered by GT label.
    """
    iou, area_gt, area_pred = iou_contingency(gt, pred)   # reuse for intersection
    n_gt, n_pred = iou.shape
    # recompute raw intersection (iou lost it); cheap contingency again
    fg = (gt > 0) & (pred > 0)
    if n_gt and n_pred and fg.any():
        pair = (gt[fg].astype(np.int64) - 1) * n_pred + (pred[fg].astype(np.int64) - 1)
        inter = np.bincount(pair, minlength=n_gt * n_pred).reshape(n_gt, n_pred).astype(np.int64)
    else:
        inter = np.zeros((n_gt, n_pred), dtype=np.int64)
    cover = cfg.cover_frac
    # split: for each GT row, # pred cols taking >= cover of GT area
    gt_covered_by = (inter >= (cover * area_gt[:, None])) if n_gt and n_pred else np.zeros((n_gt, 0), bool)
    n_pred_per_gt = gt_covered_by.sum(axis=1) if n_gt else np.array([], dtype=int)
    is_split = n_pred_per_gt >= 2
    # merge: for each pred col, GT rows where pred takes >= cover of PRED area
    pred_covers = (inter >= (cover * area_pred[None, :])) if n_gt and n_pred else np.zeros((0, n_pred), bool)
    gt_in_merged_pred = np.zeros(n_gt, dtype=bool)
    for p in range(n_pred):
        gts = np.nonzero(pred_covers[:, p])[0]
        if len(gts) >= 2:
            gt_in_merged_pred[gts] = True

    tab = gt_tab.reset_index(drop=True).copy()
    tab = tab.iloc[:n_gt].copy() if len(tab) >= n_gt else tab
    tab["split"] = is_split[:len(tab)]
    tab["merged"] = gt_in_merged_pred[:len(tab)]
    rows: list[dict] = []
    for (sb, db), g in tab.groupby(["size_bin", "dist_bin"]):
        rows.append({"size_bin": sb, "dist_bin": int(db), "n_gt": int(len(g)),
                     "split_rate": float(g["split"].mean()),
                     "merge_rate": float(g["merged"].mean())})
    totals = {"n_gt": int(n_gt), "n_pred": int(n_pred),
              "split_rate": float(np.mean(is_split)) if n_gt else float("nan"),
              "merge_rate": float(np.mean(gt_in_merged_pred)) if n_gt else float("nan")}
    return pd.DataFrame(rows).sort_values(["size_bin", "dist_bin"]).reset_index(drop=True), totals


def plateau_fraction(labels: np.ndarray) -> float:
    """Fraction of film junctions that are Plateau-consistent (3-way order).

    Reuses :func:`foam_gnn.segmentation.flag_suspicious_vertices` (order-based flag).
    NaN if no junctions are found.
    """
    from .segmentation import flag_suspicious_vertices
    verts = flag_suspicious_vertices(labels)
    if not verts:
        return float("nan")
    return float(np.mean([v["order"] == 3 for v in verts]))


# --------------------------------------------------------------------------- #
# Whole-frame evaluation
# --------------------------------------------------------------------------- #
@dataclass
class FrameEval:
    exp: str
    frame_index: int
    detection: pd.DataFrame              # per IoU threshold (global)
    stratified_recall: pd.DataFrame      # recall per (size,dist) @ primary tau
    split_merge: pd.DataFrame            # split/merge rate per (size,dist)
    matched_iou: np.ndarray              # IoUs of matched pairs @ primary tau
    plateau_gt: float
    plateau_pred: float
    totals: dict = field(default_factory=dict)


def evaluate_frame(
    gt_labels: np.ndarray,
    pred_labels: np.ndarray,
    cfg: PipelineConfig,
    *,
    exp: str = "?",
    frame_index: int = -1,
    size_edges: np.ndarray | None = None,
    dist_max: float | None = None,
) -> FrameEval:
    """Evaluate one predicted frame against its GT (see module docstring).

    ``size_edges``/``dist_max`` let a caller impose POOLED strata edges across frames
    (recommended); if None they are computed from this frame.
    """
    ecfg = cfg.seg_eval
    gt = relabel_sequential(gt_labels)
    pred = relabel_sequential(pred_labels)
    dist_map = gt_foam_distance(gt)
    gt_tab = bubble_table(gt, dist_map)
    gt_tab = assign_strata(gt_tab, ecfg, size_edges=size_edges, dist_max=dist_max)

    iou, _ag, _ap = iou_contingency(gt, pred)
    det = detection_metrics(iou, ecfg.iou_thresholds)
    matches, _ug, _up = match_hungarian(iou, ecfg.iou_primary)
    strat = stratified_detection(gt_tab, matches, ecfg)
    sm, totals = split_merge_diagnostics(gt, pred, gt_tab, ecfg)
    matched_iou = np.array([m[2] for m in matches], dtype=float)
    totals.update({"n_gt": int(gt.max()), "n_pred": int(pred.max()),
                   "primary_tau": ecfg.iou_primary})
    return FrameEval(exp=exp, frame_index=frame_index, detection=det,
                     stratified_recall=strat, split_merge=sm, matched_iou=matched_iou,
                     plateau_gt=plateau_fraction(gt), plateau_pred=plateau_fraction(pred),
                     totals=totals)
