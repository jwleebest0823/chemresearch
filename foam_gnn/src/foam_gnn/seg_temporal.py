"""
foam_gnn.seg_temporal
=====================
The **temporal-stability harness** — the metric that actually decides the project.
Per-frame boundary quality (measured in :mod:`foam_gnn.seg_eval`) is necessary but
NOT sufficient: the failure is *temporal identity stability* of small, near-edge
bubbles. These metrics measure that directly and — critically — need **no ground
truth**, so they run on every frame, not just the ~20 hand-labeled ones. The GT
harness validates that they track something real (split/merge vs churn on the
labeled frames).

Two metrics, both stratified by bubble size and distance-to-evaporation-edge
-------------------------------------------------------------------------------
1. **Temporal identity stability** — the reorganization-birth rate: fraction of
   bubble-frames at which the tracker is forced to mint a NEW id because a region
   could not be matched to any existing bubble (segmentation split/relabel). Each
   such event is attributed to the size and edge-distance of the region it created,
   so we see *where* identities break.
2. **Trackable-population coverage (HEADLINE)** — the fraction of bubbles that
   survive the stability filter and become usable for analysis, by count and by
   AREA, stratified by size and edge-distance. This is the number the whole project
   rides on: today it is ~15% of area and that 15% is the quiescent interior.

Assumptions / reuse
-------------------
* Built on the existing Module-2 tracker (:func:`foam_gnn.tracking.track_sequence`)
  and the trusted-track filter (:func:`foam_gnn.stability.select_stable_tracks`), so
  "trusted" here == the exact set the analysis uses. ``bubble_id > frame0_max_id`` is
  a reorganization artifact ("bubbles never appear"); a ``birth`` event marks the
  frame such an id is first minted.
* Distances/areas are per-frame native px (as sampled by :mod:`foam_gnn.graph`).
* Strata edges are pooled within a foam so "small"/"near-edge" are data-relative.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PipelineConfig, SegEvalConfig
from .segmentation import SegmentationResult
from .stability import build_node_table, select_stable_tracks
from .tracking import TrackingResult

__all__ = [
    "BUBBLE_FRAME_COLUMNS",
    "build_bubble_frame_table",
    "add_strata",
    "coverage_by_stratum",
    "reorg_birth_by_stratum",
    "frame0_coverage_by_stratum",
    "headline_summary",
]

BUBBLE_FRAME_COLUMNS = ["foam", "session", "frame", "bubble_id", "area",
                        "distance_to_evap_edge", "is_reorg_origin", "is_birth_frame",
                        "is_trusted"]


def build_bubble_frame_table(
    results: list[SegmentationResult],
    tracking: TrackingResult,
    cfg: PipelineConfig,
    *,
    foam: str,
    session: str,
    times_seconds: list[float] | None = None,
) -> pd.DataFrame:
    """One row per (frame, bubble) with area/edge-distance + stability flags.

    Reuses :func:`build_node_table` (area, edge-distance) and
    :func:`select_stable_tracks` (trusted set). Flags per row:
    ``is_reorg_origin`` (id above the frame-0 max), ``is_birth_frame`` (a ``birth``
    event minted this id at this frame — the spurious split/relabel moment),
    ``is_trusted`` (row belongs to a trusted segment).
    """
    nt = build_node_table(results, tracking, cfg, times_seconds=times_seconds)
    sel = select_stable_tracks(nt, tracking, cfg)
    frame0_max = int(tracking.diagnostics.get("frame0_max_id", 0))
    trusted_pairs = set(zip(sel.trusted_rows["frame"].astype(int),
                            sel.trusted_rows["bubble_id"].astype(int))) if len(sel.trusted_rows) else set()
    birth_pairs = {(int(e.frame), int(e.bubble_ids[0])) for e in tracking.events if e.kind == "birth"}

    tab = nt[["frame", "bubble_id", "area", "distance_to_evap_edge"]].copy()
    tab["foam"] = foam
    tab["session"] = session
    fb = list(zip(tab["frame"].astype(int), tab["bubble_id"].astype(int)))
    tab["is_reorg_origin"] = tab["bubble_id"].astype(int) > frame0_max
    tab["is_birth_frame"] = [p in birth_pairs for p in fb]
    tab["is_trusted"] = [p in trusted_pairs for p in fb]
    return tab[BUBBLE_FRAME_COLUMNS]


def add_strata(
    table: pd.DataFrame,
    cfg: SegEvalConfig,
    *,
    size_edges: np.ndarray | None = None,
    dist_max: float | None = None,
) -> pd.DataFrame:
    """Attach ``size_bin`` (area terciles) + ``dist_bin`` (edge-distance shells).

    Edges are pooled over the whole ``table`` (all sessions of a foam) unless passed
    in, so "small"/"near-edge" are data-relative and comparable across methods.
    ``dist_bin`` 0 = near-edge.
    """
    tab = table.copy()
    if tab.empty:
        tab["size_bin"] = pd.Series(dtype=str)
        tab["dist_bin"] = pd.Series(dtype=int)
        return tab
    area = tab["area"].to_numpy(dtype=float)
    if size_edges is None:
        qs = np.linspace(0, 1, cfg.n_size_bins + 1)[1:-1]
        size_edges = np.quantile(area, qs)
    labels = np.array(cfg.size_bin_labels)
    tab["size_bin"] = labels[np.clip(np.digitize(area, size_edges), 0, len(labels) - 1)]
    d = tab["distance_to_evap_edge"].to_numpy(dtype=float)
    dmax = float(dist_max if dist_max is not None else np.nanmax(d))
    if not np.isfinite(dmax) or dmax <= 0:
        tab["dist_bin"] = 0
    else:
        edges = np.linspace(0.0, dmax + 1e-9, cfg.n_dist_bins + 1)
        tab["dist_bin"] = np.clip(np.digitize(d, edges) - 1, 0, cfg.n_dist_bins - 1)
    return tab


def coverage_by_stratum(table: pd.DataFrame) -> pd.DataFrame:
    """HEADLINE: trackable coverage per (size_bin, dist_bin), by count and by area.

    Over all bubble-frames in each stratum: ``trusted_frac`` = fraction that belong
    to a trusted segment; ``trusted_area_frac`` = trusted area / total area. These
    are the numbers a new segmentation method must raise, especially in the
    (small, near-edge) cell.
    """
    rows: list[dict] = []
    for (sb, db), g in table.groupby(["size_bin", "dist_bin"]):
        tot_area = float(g["area"].sum())
        tru_area = float(g.loc[g["is_trusted"], "area"].sum())
        rows.append({"size_bin": sb, "dist_bin": int(db),
                     "n_bubble_frames": int(len(g)),
                     "trusted_frac": float(g["is_trusted"].mean()),
                     "trusted_area_frac": tru_area / tot_area if tot_area else 0.0})
    return pd.DataFrame(rows).sort_values(["size_bin", "dist_bin"]).reset_index(drop=True)


def reorg_birth_by_stratum(table: pd.DataFrame) -> pd.DataFrame:
    """Reorganization-birth rate per (size_bin, dist_bin).

    ``birth_rate`` = fraction of bubble-frames in the stratum that are a spurious
    reorganization birth; ``reorg_origin_frac`` = fraction whose entire identity is a
    reorganization artifact. High rates mark where the tracker cannot hold identity.
    """
    rows: list[dict] = []
    for (sb, db), g in table.groupby(["size_bin", "dist_bin"]):
        rows.append({"size_bin": sb, "dist_bin": int(db), "n_bubble_frames": int(len(g)),
                     "birth_rate": float(g["is_birth_frame"].mean()),
                     "reorg_origin_frac": float(g["is_reorg_origin"].mean())})
    return pd.DataFrame(rows).sort_values(["size_bin", "dist_bin"]).reset_index(drop=True)


def frame0_coverage_by_stratum(table: pd.DataFrame, cfg: SegEvalConfig,
                               *, size_edges: np.ndarray | None = None) -> pd.DataFrame:
    """Fraction of the REAL (frame-0-origin) bubbles that ever become trusted, by
    their frame-0 size and frame-0 edge-distance.

    Denominator = real bubbles present at frame 0 (``not is_reorg_origin``, seen at
    ``frame == 0``); numerator = those with ≥1 trusted frame. This is the honest
    "what fraction of real bubbles are usable" count, stratified at birth.
    """
    real0 = table[(table["frame"] == 0) & (~table["is_reorg_origin"])].copy()
    if real0.empty:
        return pd.DataFrame(columns=["size_bin", "dist_bin", "n_real", "n_trusted", "coverage"])
    ever_trusted = set(table.loc[table["is_trusted"], "bubble_id"].astype(int))
    real0 = add_strata(real0, cfg, size_edges=size_edges)
    real0["ever_trusted"] = real0["bubble_id"].astype(int).isin(ever_trusted)
    rows: list[dict] = []
    for (sb, db), g in real0.groupby(["size_bin", "dist_bin"]):
        rows.append({"size_bin": sb, "dist_bin": int(db), "n_real": int(len(g)),
                     "n_trusted": int(g["ever_trusted"].sum()),
                     "coverage": float(g["ever_trusted"].mean())})
    return pd.DataFrame(rows).sort_values(["size_bin", "dist_bin"]).reset_index(drop=True)


def headline_summary(table: pd.DataFrame) -> dict:
    """Foam-level headline numbers (unstratified) for quick reporting."""
    n_bf = int(len(table))
    tot_area = float(table["area"].sum())
    return {
        "n_bubble_frames": n_bf,
        "trusted_frac": float(table["is_trusted"].mean()) if n_bf else float("nan"),
        "trusted_area_frac": (float(table.loc[table["is_trusted"], "area"].sum()) / tot_area)
        if tot_area else float("nan"),
        "birth_rate": float(table["is_birth_frame"].mean()) if n_bf else float("nan"),
        "reorg_origin_frac": float(table["is_reorg_origin"].mean()) if n_bf else float("nan"),
    }
