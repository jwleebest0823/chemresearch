"""
foam_gnn.tracking
=================
MODULE 2: Persistent bubble identities across frames.

Given a sequence of :class:`~foam_gnn.segmentation.SegmentationResult` objects
from Module 1, this module assigns a stable integer *bubble_id* to each bubble
across consecutive frames and detects topological events:

* **T2_disappear** — a bubble tracked in frame *t* has no match in frame *t+1*
  (area falls below threshold, absorbed by neighbour, or drifts out of view).
* **birth** — a bubble in frame *t+1* has no predecessor in frame *t*
  (film rupture creates a new cell, or a bubble enters the field of view).
* **T1_swap** — the adjacency topology changes between frames without a
  corresponding disappearance or birth, indicating a neighbour-swap event.
  Detected from adjacency-set diffs in stable-ID space; may have false
  positives near the foam boundary or when drift registration is imperfect.

Algorithm
---------
For each consecutive pair (t, t+1):

1. Estimate frame-to-frame drift via phase cross-correlation of foam masks
   (only when ``cfg.track.register_drift=True``).
2. Build an *n_t × m_{t+1}* cost matrix:
   ``cost = w_centroid * dist/max_displacement + w_area * |log(A_t/A_{t+1})|``
   Entries whose centroid distance exceeds ``max_displacement_px`` or whose
   log-area-ratio exceeds ``area_ratio_tol`` are set to ∞ (gated out).
3. Solve with :func:`scipy.optimize.linear_sum_assignment` (Hungarian).
4. Unmatched in t → T2_disappear; unmatched in t+1 → birth.
5. Diff adjacency sets (stable IDs) to find T1 candidates.

Shapes / dtypes
---------------
``TrackingResult.id_maps``  : list of ``np.ndarray[np.int32, (H, W)]``, 0 = background.
``TrackingResult.correspondence`` : ``pd.DataFrame`` with columns
    ``frame | bubble_id | label_in_frame | area_px | cx | cy``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from scipy.optimize import linear_sum_assignment

from .config import PipelineConfig, TrackConfig
from .guards import check_array
from .segmentation import SegmentationResult


# ──────────────────────────── data classes ────────────────────────────────── #

@dataclass
class TopologicalEvent:
    """A detected foam topology change between consecutive frames."""

    frame: int                   # frame index (0-based) where the event is observed
    kind: str                    # "T2_disappear" | "birth" | "T1_swap"
    bubble_ids: tuple[int, ...]  # stable IDs of involved bubbles
    meta: dict = field(default_factory=dict)


@dataclass
class TrackingResult:
    """Output of :func:`track_sequence`.

    Attributes
    ----------
    id_maps:
        Per-frame label arrays in stable-ID space.  Shape ``(H, W) int32``;
        pixel value 0 = background / unlabelled; positive value = stable bubble ID.
    events:
        Topological events sorted by frame (ascending).
    correspondence:
        Tidy DataFrame with one row per (frame, bubble) — see module docstring
        for column list.
    n_tracks:
        Total number of unique stable bubble IDs issued (including those that
        appear in only one frame).
    """

    id_maps: list[np.ndarray]
    events: list[TopologicalEvent]
    correspondence: pd.DataFrame
    n_tracks: int


# ──────────────────────────── internals ───────────────────────────────────── #

def _bubble_props(seg: SegmentationResult) -> list[dict]:
    """Extract {label, cx, cy, area} for every bubble in *seg*."""
    labels = seg.labels
    unique = np.unique(labels)
    unique = unique[unique > 0]
    rows: list[dict] = []
    for lbl in unique:
        mask = labels == lbl
        ys, xs = np.nonzero(mask)
        rows.append({
            "label": int(lbl),
            "cx": float(xs.mean()),
            "cy": float(ys.mean()),
            "area": int(mask.sum()),
        })
    return rows


def _estimate_drift(
    mask_t: np.ndarray,
    mask_t1: np.ndarray,
) -> tuple[float, float]:
    """Phase cross-correlation of two foam masks → (dy, dx) drift.

    Returns the shift such that ``mask_t1 + shift ≈ mask_t`` in pixel
    coordinates.  Specifically, a point at ``(cy, cx)`` in frame *t+1*
    corresponds to ``(cy + dy, cx + dx)`` in frame *t*.

    Parameters
    ----------
    mask_t, mask_t1 : bool or uint8 arrays, shape (H, W)
    """
    from skimage.registration import phase_cross_correlation

    shift, _, _ = phase_cross_correlation(
        mask_t.astype(np.float32),
        mask_t1.astype(np.float32),
        upsample_factor=4,
    )
    return float(shift[0]), float(shift[1])   # (dy, dx)


def _adjacency_set(labels: np.ndarray) -> set[frozenset[int]]:
    """Return the set of bubble-pair frozensets that share a pixel border.

    Uses 4-connectivity (horizontal + vertical neighbours only).
    Both labels must be > 0 (background pairs are ignored).

    Parameters
    ----------
    labels : np.ndarray[int32, (H, W)]
        Label map in **stable**-ID space (background = 0).
    """
    adj: set[frozenset[int]] = set()
    for a, b in (
        (labels[:, :-1], labels[:, 1:]),   # horizontal
        (labels[:-1, :], labels[1:, :]),   # vertical
    ):
        mask = (a > 0) & (b > 0) & (a != b)
        if not mask.any():
            continue
        pairs = np.stack([a[mask], b[mask]], axis=1)
        pairs = np.unique(pairs, axis=0)   # deduplicate in C before Python loop
        for i, j in pairs.tolist():
            adj.add(frozenset({i, j}))
    return adj


def _match_frame_pair(
    props_t: list[dict],
    props_t1: list[dict],
    drift_dy: float,
    drift_dx: float,
    cfg: TrackConfig,
) -> tuple[dict[int, int], list[int], list[int]]:
    """Hungarian matching of bubble lists between two consecutive frames.

    Parameters
    ----------
    props_t : list of {label, cx, cy, area} dicts for frame *t*.
    props_t1 : list of {label, cx, cy, area} dicts for frame *t+1*.
    drift_dy, drift_dx : drift of *t+1* relative to *t* (pixels).
        A centroid at ``(cy, cx)`` in *t+1* aligns to ``(cy+dy, cx+dx)`` in *t*.
    cfg : TrackConfig

    Returns
    -------
    label_map : dict mapping local-label-in-t → local-label-in-t+1 for matches.
    unmatched_t : local labels in *t* with no match (T2 candidates).
    unmatched_t1 : local labels in *t+1* with no match (birth candidates).
    """
    if not props_t or not props_t1:
        return {}, [p["label"] for p in props_t], [p["label"] for p in props_t1]

    n, m = len(props_t), len(props_t1)
    INF = 1e9
    cost = np.full((n, m), INF)

    for i, pi in enumerate(props_t):
        for j, pj in enumerate(props_t1):
            # Bring pj centroid into frame-t coordinate system
            cx_j = pj["cx"] + drift_dx
            cy_j = pj["cy"] + drift_dy
            dist = float(np.hypot(pi["cx"] - cx_j, pi["cy"] - cy_j))
            if dist > cfg.max_displacement_px:
                continue
            log_ratio = abs(float(np.log(pi["area"] / max(pj["area"], 1))))
            if log_ratio > cfg.area_ratio_tol:
                continue
            cost[i, j] = (
                cfg.cost_w_centroid * dist / max(cfg.max_displacement_px, 1e-9)
                + cfg.cost_w_area * log_ratio
            )

    row_ind, col_ind = linear_sum_assignment(cost)

    label_map: dict[int, int] = {}
    matched_t: set[int] = set()
    matched_t1: set[int] = set()
    for r, c in zip(row_ind.tolist(), col_ind.tolist()):
        if cost[r, c] < INF:
            label_map[props_t[r]["label"]] = props_t1[c]["label"]
            matched_t.add(r)
            matched_t1.add(c)

    unmatched_t = [props_t[i]["label"] for i in range(n) if i not in matched_t]
    unmatched_t1 = [props_t1[j]["label"] for j in range(m) if j not in matched_t1]
    return label_map, unmatched_t, unmatched_t1


def _remap(labels: np.ndarray, local_to_stable: dict[int, int]) -> np.ndarray:
    """Create a new array with local labels replaced by stable IDs (0 = background)."""
    out = np.zeros_like(labels, dtype=np.int32)
    for local, stable in local_to_stable.items():
        out[labels == local] = stable
    return out


# ──────────────────────────── public API ──────────────────────────────────── #

def track_sequence(
    results: list[SegmentationResult],
    cfg: PipelineConfig,
) -> TrackingResult:
    """Assign stable bubble IDs across all frames and detect topological events.

    Parameters
    ----------
    results :
        Ordered list of Module-1 outputs (one per frame, earliest first).
    cfg :
        Pipeline config; ``cfg.track`` fields govern matching behaviour.

    Returns
    -------
    TrackingResult
    """
    if not results:
        empty_df = pd.DataFrame(columns=["frame", "bubble_id", "label_in_frame",
                                         "area_px", "cx", "cy"])
        return TrackingResult([], [], empty_df, 0)

    tcfg = cfg.track
    corr_rows: list[dict] = []
    events: list[TopologicalEvent] = []

    # ── Frame 0: assign IDs 1..n_bubbles directly (local == stable) ───────── #
    props0 = _bubble_props(results[0])
    local_to_stable: dict[int, int] = {p["label"]: p["label"] for p in props0}
    id_next: int = results[0].n_bubbles + 1

    id_maps: list[np.ndarray] = [_remap(results[0].labels, local_to_stable)]
    for p in props0:
        corr_rows.append({
            "frame": 0, "bubble_id": local_to_stable[p["label"]],
            "label_in_frame": p["label"],
            "area_px": p["area"], "cx": p["cx"], "cy": p["cy"],
        })

    prev_adj = _adjacency_set(id_maps[0])

    # ── Frames 1..n ───────────────────────────────────────────────────────── #
    for t in range(1, len(results)):
        props_prev = _bubble_props(results[t - 1])
        props_curr = _bubble_props(results[t])

        drift_dy, drift_dx = 0.0, 0.0
        if tcfg.register_drift:
            drift_dy, drift_dx = _estimate_drift(
                results[t - 1].foam_mask,
                results[t].foam_mask,
            )

        label_map, unmatched_prev, unmatched_curr = _match_frame_pair(
            props_prev, props_curr, drift_dy, drift_dx, tcfg
        )

        # Build local_to_stable for frame t
        new_l2s: dict[int, int] = {}
        for local_prev, local_curr in label_map.items():
            stable = local_to_stable.get(local_prev)
            if stable is not None:
                new_l2s[local_curr] = stable

        # Births: unmatched in current frame get new IDs
        for local_curr in unmatched_curr:
            new_l2s[local_curr] = id_next
            events.append(TopologicalEvent(
                frame=t, kind="birth",
                bubble_ids=(id_next,),
                meta={"local_label": local_curr},
            ))
            id_next += 1

        # Disappearances: unmatched in previous frame
        for local_prev in unmatched_prev:
            stable = local_to_stable.get(local_prev, 0)
            if stable:
                events.append(TopologicalEvent(
                    frame=t, kind="T2_disappear",
                    bubble_ids=(stable,),
                    meta={"last_seen_frame": t - 1},
                ))

        local_to_stable = new_l2s

        id_map_t = _remap(results[t].labels, local_to_stable)
        id_maps.append(id_map_t)

        for p in props_curr:
            sid = local_to_stable.get(p["label"], 0)
            corr_rows.append({
                "frame": t, "bubble_id": sid,
                "label_in_frame": p["label"],
                "area_px": p["area"], "cx": p["cx"], "cy": p["cy"],
            })

        # T1 detection: adjacency change not explained by births/disappearances
        curr_adj = _adjacency_set(id_map_t)
        disappeared_ids = {
            e.bubble_ids[0] for e in events
            if e.frame == t and e.kind == "T2_disappear"
        }
        born_ids = {
            e.bubble_ids[0] for e in events
            if e.frame == t and e.kind == "birth"
        }
        changed_edges = prev_adj.symmetric_difference(curr_adj)
        t1_pairs: set[frozenset[int]] = {
            pair for pair in changed_edges
            if not (pair & disappeared_ids) and not (pair & born_ids)
        }
        if t1_pairs:
            involved = tuple(sorted({b for p in t1_pairs for b in p}))
            events.append(TopologicalEvent(
                frame=t, kind="T1_swap",
                bubble_ids=involved,
                meta={"n_changed_edges": len(t1_pairs)},
            ))

        prev_adj = curr_adj

    events.sort(key=lambda e: e.frame)
    corr_df = pd.DataFrame(corr_rows)

    return TrackingResult(
        id_maps=id_maps,
        events=events,
        correspondence=corr_df,
        n_tracks=id_next - 1,
    )


def summarize_events(result: TrackingResult) -> pd.DataFrame:
    """Return a tidy DataFrame with one row per topological event.

    Columns: ``frame | kind | bubble_ids | ...meta keys...``
    """
    if not result.events:
        return pd.DataFrame(columns=["frame", "kind", "bubble_ids"])
    rows = [
        {"frame": e.frame, "kind": e.kind, "bubble_ids": e.bubble_ids, **e.meta}
        for e in result.events
    ]
    return pd.DataFrame(rows)
