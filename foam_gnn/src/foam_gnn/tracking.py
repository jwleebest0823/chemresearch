"""
foam_gnn.tracking
=================
MODULE 2: Persistent bubble identities across frames + topological events.

Given a sequence of :class:`~foam_gnn.segmentation.SegmentationResult` objects
from Module 1 *within a single tracking session* (never across an inter-session
gap — see :mod:`foam_gnn.dataset`), this module assigns a stable integer
*bubble_id* to each bubble across consecutive frames and detects topological
events:

* **T2_disappear** — a bubble tracked in frame *t* has no match in frame *t+1*
  (shrinks below threshold, absorbed by a neighbour, or leaves the field).
* **birth** — a bubble in frame *t+1* has no predecessor in frame *t*.
* **T1_swap** — a localized neighbour swap: a specific bubble pair ``{P, Q}``
  loses its shared film while their two common neighbours ``{R, S}`` gain one,
  with all four bubbles persisting across the frame. **One event per swap**, each
  carrying the 4-bubble cluster and a location.

T1 detection (rewritten — see B1)
---------------------------------
The previous implementation lumped *all* adjacency changes between two frames
into a single ``T1_swap`` via symmetric-difference of adjacency sets. That (a)
merged independent events, (b) could not separate a true swap from segmentation
flicker/drift, and (c) had no per-event location.

The current detector encodes the actual T1 topology. For each consecutive pair
``(t, t+1)`` in stable-ID space, restricted to bubbles present in **both** frames:

1. A candidate **lost** edge ``{P, Q}`` is one whose shared border in *t* exceeds
   ``t1_min_border_px`` but is gone (border < ``t1_min_border_px``) in *t+1*.
2. Its partner is sought among the **common neighbours** of ``P`` and ``Q`` in
   *t*: the new edge of a genuine swap forms between exactly two of them,
   ``{R, S}``, which were **not** adjacent in *t* but **are** adjacent (border ≥
   ``t1_min_border_px``) in *t+1*.
3. Robustness: the new ``R-S`` edge must persist for ``t1_confirm_frames`` further
   frames (when available) to reject single-frame flicker.

Each accepted swap emits one event located at the centroid of the 4-bubble
cluster — the quantity that matters scientifically (T1 rate vs distance-to-edge).

Algorithm (matching)
--------------------
For each consecutive pair (t, t+1): estimate drift (phase cross-correlation of
foam masks); build an ``n_t × m_{t+1}`` gated cost matrix
``cost = w_centroid·dist/max_disp + w_area·|log(A_t/A_{t+1})|`` (entries beyond
``max_displacement_px`` or ``area_ratio_tol`` set to ∞); solve with the Hungarian
algorithm; unmatched-in-t → T2, unmatched-in-t+1 → birth.

Shapes / dtypes
---------------
``TrackingResult.id_maps``  : list of ``np.ndarray[int32, (H, W)]``, 0 = background.
``TrackingResult.correspondence`` : ``pd.DataFrame`` with columns
    ``frame | bubble_id | label_in_frame | area_px | cx | cy``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from .config import PipelineConfig, TrackConfig
from .segmentation import SegmentationResult

__all__ = [
    "TopologicalEvent",
    "TrackingResult",
    "track_sequence",
    "summarize_events",
    "overlay_ids",
    "overlay_events",
]


# ──────────────────────────── data classes ────────────────────────────────── #

@dataclass
class TopologicalEvent:
    """A detected foam topology change between consecutive frames.

    ``meta`` always carries a location ``cx``/``cy`` (pixels, frame-*t+1* unless
    noted) so events can be overlaid and binned by distance-to-edge.
    """

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
        0 = background; positive = stable bubble ID.
    events:
        Topological events sorted by frame (ascending).
    correspondence:
        Tidy DataFrame, one row per (frame, bubble) — see module docstring.
        ``cx``/``cy`` are **native** per-frame pixel coordinates.
    n_tracks:
        Total number of unique stable bubble IDs issued.
    frame_offsets:
        Per-frame cumulative drift ``(off_x, off_y)`` that maps a frame's native
        pixel coordinates into the **common (frame-0) coordinate frame**:
        ``registered = native + offset``. ``frame_offsets[0] == (0.0, 0.0)``; each
        entry accumulates the per-step foam-mask drift Module 2 already computes
        for matching. All zeros when ``cfg.track.register_drift`` is False. Length
        equals ``len(id_maps)``.
    """

    id_maps: list[np.ndarray]
    events: list[TopologicalEvent]
    correspondence: pd.DataFrame
    n_tracks: int
    frame_offsets: list[tuple[float, float]] = field(default_factory=list)


# ──────────────────────────── internals ───────────────────────────────────── #

def _bubble_props(seg: SegmentationResult) -> list[dict]:
    """Extract ``{label, cx, cy, area}`` for every bubble in *seg*."""
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


def _estimate_drift(mask_t: np.ndarray, mask_t1: np.ndarray) -> tuple[float, float]:
    """Phase cross-correlation of two foam masks → ``(dy, dx)`` drift.

    Returns the shift such that a point at ``(cy, cx)`` in frame *t+1* corresponds
    to ``(cy + dy, cx + dx)`` in frame *t*.
    """
    from skimage.registration import phase_cross_correlation

    shift, _, _ = phase_cross_correlation(
        mask_t.astype(np.float32), mask_t1.astype(np.float32), upsample_factor=4,
    )
    return float(shift[0]), float(shift[1])   # (dy, dx)


def _adjacency_lengths(labels: np.ndarray) -> dict[frozenset, int]:
    """Shared-border length (px) for every adjacent bubble pair.

    A pixel border is counted once per horizontally/vertically adjacent
    differing-label pixel pair (4-connectivity). Both labels must be > 0.

    Parameters
    ----------
    labels : np.ndarray[int32, (H, W)]
        Label map in **stable**-ID space (background = 0).

    Returns
    -------
    dict[frozenset[int], int]
        ``{frozenset({a, b}): border_length_px}``.
    """
    counts: dict[frozenset, int] = {}
    for a, b in (
        (labels[:, :-1], labels[:, 1:]),   # horizontal neighbours
        (labels[:-1, :], labels[1:, :]),   # vertical neighbours
    ):
        mask = (a > 0) & (b > 0) & (a != b)
        if not mask.any():
            continue
        pairs = np.stack([a[mask], b[mask]], axis=1)
        uniq, cnt = np.unique(pairs, axis=0, return_counts=True)
        for (i, j), c in zip(uniq.tolist(), cnt.tolist()):
            key = frozenset((int(i), int(j)))
            counts[key] = counts.get(key, 0) + int(c)
    return counts


def _neighbors(adj: dict[frozenset, int], node: int, min_len: int) -> set[int]:
    """Neighbours of *node* whose shared border ≥ ``min_len``."""
    out: set[int] = set()
    for pair, length in adj.items():
        if node in pair and length >= min_len:
            other = next(iter(pair - {node}))
            out.add(other)
    return out


def _match_frame_pair(
    props_t: list[dict],
    props_t1: list[dict],
    drift_dy: float,
    drift_dx: float,
    cfg: TrackConfig,
) -> tuple[dict[int, int], list[int], list[int]]:
    """Hungarian matching of bubble lists between two consecutive frames.

    Returns
    -------
    label_map : dict local-label-in-t → local-label-in-t+1 for matches.
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
            cx_j = pj["cx"] + drift_dx          # bring t+1 centroid into t coords
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
    """New array with local labels replaced by stable IDs (0 = background)."""
    out = np.zeros_like(labels, dtype=np.int32)
    for local, stable in local_to_stable.items():
        out[labels == local] = stable
    return out


def _detect_t1_between(
    adj_t: dict[frozenset, int],
    adj_t1: dict[frozenset, int],
    centroids_t1: dict[int, tuple[float, float]],
    persist: set[int],
    min_border: int,
) -> list[dict]:
    """Find individual localized neighbour-swaps between two frames.

    A swap is a lost edge ``{P, Q}`` (border ≥ ``min_border`` in *t*, gone in
    *t+1*) whose two *common neighbours in t* ``{R, S}`` form a **gained** edge
    (absent in *t*, border ≥ ``min_border`` in *t+1*). All four must be in
    ``persist``.

    Returns
    -------
    list[dict]
        One per swap: ``{lost, gained, cluster (sorted 4-tuple), cx, cy,
        border_lost_px, border_gained_px}``.
    """
    def length(adj, a, b):
        return adj.get(frozenset((a, b)), 0)

    swaps: list[dict] = []
    seen: set[tuple] = set()
    # candidate lost edges among persisting bubbles
    for pair, L in adj_t.items():
        if L < min_border:
            continue
        P, Q = tuple(pair)
        if P not in persist or Q not in persist:
            continue
        if length(adj_t1, P, Q) >= min_border:
            continue  # edge survived → not lost
        # common neighbours of P and Q in frame t
        common = (_neighbors(adj_t, P, min_border) & _neighbors(adj_t, Q, min_border)) - {P, Q}
        common = {c for c in common if c in persist}
        if len(common) < 2:
            continue
        common_list = sorted(common)
        for ia in range(len(common_list)):
            for ib in range(ia + 1, len(common_list)):
                R, S = common_list[ia], common_list[ib]
                # R-S must be a *gained* edge: absent in t, present in t+1
                if length(adj_t, R, S) >= min_border:
                    continue
                if length(adj_t1, R, S) < min_border:
                    continue
                cluster = tuple(sorted((P, Q, R, S)))
                if cluster in seen:
                    continue
                seen.add(cluster)
                cs = [centroids_t1[b] for b in cluster if b in centroids_t1]
                cx = float(np.mean([c[0] for c in cs])) if cs else float("nan")
                cy = float(np.mean([c[1] for c in cs])) if cs else float("nan")
                swaps.append({
                    "lost": (P, Q), "gained": (R, S), "cluster": cluster,
                    "cx": cx, "cy": cy,
                    "border_lost_px": int(L),
                    "border_gained_px": int(length(adj_t1, R, S)),
                })
    return swaps


# ──────────────────────────── public API ──────────────────────────────────── #

def track_sequence(results: list[SegmentationResult], cfg: PipelineConfig) -> TrackingResult:
    """Assign stable bubble IDs across all frames and detect topological events.

    Parameters
    ----------
    results :
        Ordered Module-1 outputs (one per frame, earliest first) from **one
        tracking session**.
    cfg :
        ``cfg.track`` governs matching and T1 detection.

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
    centroids_per_frame: list[dict[int, tuple[float, float]]] = [
        {p["label"]: (p["cx"], p["cy"]) for p in props0}
    ]
    # cumulative drift mapping each frame's native coords → frame-0 coords
    # (registered = native + offset); accumulates the same per-step drift used
    # for matching, so it is the single source of truth (no re-estimation).
    frame_offsets: list[tuple[float, float]] = [(0.0, 0.0)]
    cum_off_x, cum_off_y = 0.0, 0.0
    for p in props0:
        corr_rows.append({
            "frame": 0, "bubble_id": local_to_stable[p["label"]],
            "label_in_frame": p["label"],
            "area_px": p["area"], "cx": p["cx"], "cy": p["cy"],
        })

    # ── Frames 1..n: match, assign IDs, log T2/birth ──────────────────────── #
    for t in range(1, len(results)):
        props_prev = _bubble_props(results[t - 1])
        props_curr = _bubble_props(results[t])

        drift_dy, drift_dx = 0.0, 0.0
        if tcfg.register_drift:
            drift_dy, drift_dx = _estimate_drift(results[t - 1].foam_mask, results[t].foam_mask)
        cum_off_x += drift_dx
        cum_off_y += drift_dy
        frame_offsets.append((cum_off_x, cum_off_y))

        label_map, unmatched_prev, unmatched_curr = _match_frame_pair(
            props_prev, props_curr, drift_dy, drift_dx, tcfg
        )

        new_l2s: dict[int, int] = {}
        for local_prev, local_curr in label_map.items():
            stable = local_to_stable.get(local_prev)
            if stable is not None:
                new_l2s[local_curr] = stable

        curr_centroid = {p["label"]: (p["cx"], p["cy"]) for p in props_curr}

        # Births: unmatched in current frame get new IDs
        for local_curr in unmatched_curr:
            new_l2s[local_curr] = id_next
            cx, cy = curr_centroid[local_curr]
            events.append(TopologicalEvent(
                frame=t, kind="birth", bubble_ids=(id_next,),
                meta={"local_label": local_curr, "cx": cx, "cy": cy},
            ))
            id_next += 1

        # Disappearances: unmatched in previous frame (locate at last-seen centroid)
        prev_centroid = {p["label"]: (p["cx"], p["cy"]) for p in props_prev}
        for local_prev in unmatched_prev:
            stable = local_to_stable.get(local_prev, 0)
            if stable:
                cx, cy = prev_centroid.get(local_prev, (float("nan"), float("nan")))
                events.append(TopologicalEvent(
                    frame=t, kind="T2_disappear", bubble_ids=(stable,),
                    meta={"last_seen_frame": t - 1, "cx": cx, "cy": cy},
                ))

        local_to_stable = new_l2s
        id_maps.append(_remap(results[t].labels, local_to_stable))
        centroids_per_frame.append(
            {local_to_stable[p["label"]]: (p["cx"], p["cy"])
             for p in props_curr if p["label"] in local_to_stable}
        )
        for p in props_curr:
            sid = local_to_stable.get(p["label"], 0)
            corr_rows.append({
                "frame": t, "bubble_id": sid, "label_in_frame": p["label"],
                "area_px": p["area"], "cx": p["cx"], "cy": p["cy"],
            })

    # ── T1 detection (second pass: needs adjacency + look-ahead confirm) ──── #
    adj_per_frame = [_adjacency_lengths(m) for m in id_maps]
    present_per_frame = [set(np.unique(m)) - {0} for m in id_maps]
    mb = tcfg.t1_min_border_px
    for t in range(1, len(id_maps)):
        persist = present_per_frame[t - 1] & present_per_frame[t]
        swaps = _detect_t1_between(
            adj_per_frame[t - 1], adj_per_frame[t], centroids_per_frame[t], persist, mb
        )
        for sw in swaps:
            R, S = sw["gained"]
            # confirmation: new R-S edge must survive t1_confirm_frames more frames
            confirmed = 0
            for c in range(1, tcfg.t1_confirm_frames + 1):
                if t + c >= len(adj_per_frame):
                    break  # not enough frames to confirm → accept (boundary of series)
                if adj_per_frame[t + c].get(frozenset((R, S)), 0) >= mb \
                        and R in present_per_frame[t + c] and S in present_per_frame[t + c]:
                    confirmed += 1
                else:
                    break
            need = min(tcfg.t1_confirm_frames, len(adj_per_frame) - 1 - t)
            if confirmed < need:
                continue
            events.append(TopologicalEvent(
                frame=t, kind="T1_swap", bubble_ids=sw["cluster"],
                meta={"lost_pair": sw["lost"], "gained_pair": sw["gained"],
                      "cx": sw["cx"], "cy": sw["cy"],
                      "border_lost_px": sw["border_lost_px"],
                      "border_gained_px": sw["border_gained_px"],
                      "confirmed_frames": confirmed},
            ))

    events.sort(key=lambda e: (e.frame, e.kind))
    return TrackingResult(
        id_maps=id_maps,
        events=events,
        correspondence=pd.DataFrame(corr_rows),
        n_tracks=id_next - 1,
        frame_offsets=frame_offsets,
    )


def summarize_events(result: TrackingResult) -> pd.DataFrame:
    """Tidy DataFrame, one row per event: ``frame | kind | bubble_ids | ...meta``."""
    if not result.events:
        return pd.DataFrame(columns=["frame", "kind", "bubble_ids"])
    rows = [{"frame": e.frame, "kind": e.kind, "bubble_ids": e.bubble_ids, **e.meta}
            for e in result.events]
    return pd.DataFrame(rows)


# ──────────────────────────── visual audit ────────────────────────────────── #

def _id_color(bubble_id: int) -> tuple[int, int, int]:
    """Deterministic, well-spread RGB for a stable ID (consistent across frames)."""
    # golden-ratio hue hashing → distinct, frame-stable colours
    import colorsys
    h = (bubble_id * 0.6180339887498949) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def overlay_ids(
    img: np.ndarray,
    id_map: np.ndarray,
    *,
    draw_labels: bool = True,
    alpha: float = 0.45,
    font_scale: float = 0.4,
) -> np.ndarray:
    """Tint each bubble by a *frame-stable* per-ID colour and (optionally) print
    its stable ID. Same bubble ⇒ same colour across frames, so ID persistence is
    verifiable by eye.

    Parameters
    ----------
    img : uint8 (H, W)
        Raw grayscale frame.
    id_map : int32 (H, W)
        Stable-ID label map (0 = background).

    Returns
    -------
    np.ndarray
        uint8 (H, W, 3) RGB overlay.
    """
    import cv2
    from skimage.segmentation import find_boundaries

    if img.ndim != 2:
        raise ValueError(f"overlay_ids: img must be (H, W), got {img.shape}")
    if id_map.shape != img.shape:
        raise ValueError(f"overlay_ids: id_map {id_map.shape} != img {img.shape}")

    base = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    tint = base.copy()
    ids = np.unique(id_map)
    ids = ids[ids > 0]
    for bid in ids.tolist():
        tint[id_map == bid] = _id_color(int(bid))
    out = cv2.addWeighted(tint, alpha, base, 1 - alpha, 0)
    out[find_boundaries(id_map, mode="outer")] = (20, 20, 20)
    if draw_labels:
        for bid in ids.tolist():
            ys, xs = np.where(id_map == bid)
            cy, cx = int(ys.mean()), int(xs.mean())
            cv2.putText(out, str(int(bid)), (cx - 6, cy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA)
    return out


def overlay_events(
    img: np.ndarray,
    events: list[TopologicalEvent],
    frame: int,
    *,
    kinds: tuple[str, ...] = ("T1_swap", "T2_disappear", "birth"),
    radius: int = 16,
) -> np.ndarray:
    """Overlay events observed at *frame* onto its raw image for visual audit.

    T1 → yellow circle + "T1" at the 4-bubble cluster centroid; T2 → red ✕ at the
    last-seen centroid; birth → green + at the new centroid.

    Parameters
    ----------
    img : uint8 (H, W)
        Raw grayscale frame *frame* (events at this index are drawn).
    events : list[TopologicalEvent]
    frame : int
        Only events with ``e.frame == frame`` are drawn.

    Returns
    -------
    np.ndarray
        uint8 (H, W, 3) RGB.
    """
    import cv2

    if img.ndim != 2:
        raise ValueError(f"overlay_events: img must be (H, W), got {img.shape}")
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    style = {
        "T1_swap": ((255, 230, 0), "T1"),
        "T2_disappear": ((255, 40, 40), "T2"),
        "birth": ((40, 220, 40), "b"),
    }
    for e in events:
        if e.frame != frame or e.kind not in kinds:
            continue
        cx, cy = e.meta.get("cx"), e.meta.get("cy")
        if cx is None or cy is None or not (np.isfinite(cx) and np.isfinite(cy)):
            continue
        c = (int(round(cx)), int(round(cy)))
        color, tag = style.get(e.kind, ((255, 255, 255), "?"))
        if e.kind == "T1_swap":
            cv2.circle(rgb, c, radius, color, 2)
        elif e.kind == "T2_disappear":
            d = radius // 2
            cv2.line(rgb, (c[0] - d, c[1] - d), (c[0] + d, c[1] + d), color, 2)
            cv2.line(rgb, (c[0] - d, c[1] + d), (c[0] + d, c[1] - d), color, 2)
        else:
            d = radius // 2
            cv2.line(rgb, (c[0] - d, c[1]), (c[0] + d, c[1]), color, 2)
            cv2.line(rgb, (c[0], c[1] - d), (c[0], c[1] + d), color, 2)
        cv2.putText(rgb, tag, (c[0] + radius, c[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return rgb
