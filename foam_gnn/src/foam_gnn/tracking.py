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
from scipy import ndimage as ndi
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
    kind: str                    # "T2_disappear" | "birth" | "T1_swap" | "merge"
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
    diagnostics:
        Merge-fix counters: ``n_merge_regions`` (regions with ≥2 parents),
        ``n_split_reconciled`` / ``flicker_durations`` (merge-flickers caught),
        ``n_resurrections``, ``n_ambiguous_resurrections`` (silent-corruption
        risks), ``n_births_remaining`` (segmentation-split/reorganization births —
        NOT fixed by the merge guard), ``n_merge_events``, ``frame0_max_id``,
        ``max_bubble_id`` and ``invariant_B_holds`` (max ID ≤ frame-0 max).
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
    diagnostics: dict = field(default_factory=dict)


# ──────────────────────────── internals ───────────────────────────────────── #

def _coord_grids(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Flattened row (y) and column (x) coordinate arrays for a frame shape.

    Shared across frames of one session (constant shape) so the per-frame
    property extraction avoids rebuilding them. Returns ``(rr, cc)`` each
    ``float64 (H*W,)`` in row-major (C) order.
    """
    h, w = shape
    rr = np.repeat(np.arange(h, dtype=np.float64), w)
    cc = np.tile(np.arange(w, dtype=np.float64), h)
    return rr, cc


def _props_from_labels(
    labels: np.ndarray,
    rr: np.ndarray | None = None,
    cc: np.ndarray | None = None,
) -> list[dict]:
    """Vectorized ``{label, cx, cy, area}`` for every bubble in a label map.

    Replaces the per-label boolean-mask loop with three ``np.bincount`` passes
    (area, Σx, Σy) over the flattened labels — one O(pixels) sweep instead of
    O(labels × pixels). Output is **bit-identical** to the old per-label
    ``xs.mean()`` / ``mask.sum()``: coordinate sums are integer-valued and stay
    below 2**53, so they are exact in float64 regardless of summation order, and
    the final ``Σx / area`` division has identical operands. Labels are returned
    in ascending order (matching ``np.unique``).

    Parameters
    ----------
    labels : int (H, W)
        Label map (0 = background). ``rr``/``cc`` are the flattened coordinate
        grids from :func:`_coord_grids`; rebuilt internally if absent or mismatched.
    """
    flat = labels.ravel()
    if flat.size == 0:
        return []
    n = int(flat.max())
    if n == 0:
        return []
    if rr is None or cc is None or rr.size != flat.size:
        rr, cc = _coord_grids(labels.shape)
    counts = np.bincount(flat, minlength=n + 1)
    sum_x = np.bincount(flat, weights=cc, minlength=n + 1)
    sum_y = np.bincount(flat, weights=rr, minlength=n + 1)
    present = np.nonzero(counts)[0]
    present = present[present > 0]            # labels > 0, ascending (== np.unique)
    rows: list[dict] = []
    for lbl in present.tolist():
        area = int(counts[lbl])
        rows.append({
            "label": int(lbl),
            "cx": float(sum_x[lbl] / area),
            "cy": float(sum_y[lbl] / area),
            "area": area,
        })
    return rows


def _bubble_props(seg: SegmentationResult) -> list[dict]:
    """Extract ``{label, cx, cy, area}`` for every bubble in *seg* (vectorized)."""
    return _props_from_labels(seg.labels)


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


def bridge_distance_px(labels: np.ndarray, radius_frac: float = 0.5,
                       gap_quantile: float = 0.99,
                       inside: np.ndarray | None = None) -> float:
    """Per-frame, scale-adaptive maximum bridging distance (px). int32 (H,W) -> float.

    # DECISION (D2, docs/correctness_audit.md): bubbles separated only by an unlabelled
    # film or a rejected Plateau border are physically neighbours, but `_adjacency_lengths`
    # needs two positive labels to touch, so those contacts are lost (13% of the foam
    # interior is label 0; <n> = 4.48 against the Euler requirement of ~6).
    #
    # The bridge is capped by TWO per-frame measured scales, never a pixel constant:
    #   * the `gap_quantile` of the gap half-width distribution -- the observed film /
    #     Plateau-border thickness in THIS frame;
    #   * `radius_frac` x the median bubble radius -- so a bridge can never span a
    #     bubble-sized void even if a foam has fat unresolved regions (Foam C).
    # Measured on Foam A: gap half-width p99 = 8.1 px, max 11.2 px, against a median
    # bubble radius of 23.8 px -- i.e. every gap really is a film, not a void.
    #
    # Over-bridging is additionally blocked by construction: background is assigned to
    # its NEAREST label, so an intervening labelled bubble always separates two
    # non-neighbours. Only genuinely unlabelled material is ever crossed.
    """
    bg = labels == 0
    if inside is not None:
        bg = bg & inside
    if not bg.any():
        return 0.0
    d = ndi.distance_transform_edt(labels == 0)
    gaps = d[bg]
    a = np.bincount(labels.ravel())[1:]
    a = a[a > 0]
    if a.size == 0:
        return 0.0
    med_r = float(np.median(np.sqrt(a / np.pi)))
    return float(min(np.quantile(gaps, gap_quantile), radius_frac * med_r))


def adjacency_lengths_bridged(labels: np.ndarray, max_bridge_px: float,
                              inside: np.ndarray | None = None) -> dict[frozenset, int]:
    """Shared-border length allowing contact ACROSS thin unlabelled gaps.

    Each background pixel within ``max_bridge_px`` of a labelled region is assigned to
    its nearest label; adjacency is then measured on the completed map. Two bubbles
    become neighbours iff the unlabelled gap between them is at most
    ``2 * max_bridge_px`` wide AND no third labelled region lies between them.

    ``inside`` (bool (H, W)) restricts bridging to the foam interior, so labels are
    never extended into the exterior background. ``max_bridge_px <= 0`` reproduces
    :func:`_adjacency_lengths` exactly.
    """
    if max_bridge_px <= 0:
        return _adjacency_lengths(labels)
    bg = labels == 0
    if not bg.any():
        return _adjacency_lengths(labels)
    dist, idx = ndi.distance_transform_edt(bg, return_indices=True)
    filled = labels.copy()
    take = bg & (dist <= float(max_bridge_px))
    if inside is not None:
        take &= inside
    if take.any():
        filled[take] = labels[idx[0][take], idx[1][take]]
    return _adjacency_lengths(filled)


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

    NOTE: deliberately NOT vectorized. It is not on the O(labels × pixels) hot
    path (called once per frame, not per label), and its exact frozenset-key
    construction / dict-insertion order is depended upon downstream: the T1
    detector renders ``lost_pair``/``gained_pair`` via ``tuple(frozenset_key)``,
    whose element order can flip for hash-colliding labels if the key is built
    differently. Keeping this original preserves byte-identical event output.
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
    # Vectorized cost matrix (bit-identical to the scalar double loop, element for
    # element: same subtraction order, same hypot/log/division, same gates).
    cx_t = np.array([p["cx"] for p in props_t], dtype=np.float64)
    cy_t = np.array([p["cy"] for p in props_t], dtype=np.float64)
    a_t = np.array([p["area"] for p in props_t], dtype=np.float64)
    cx_j = np.array([p["cx"] for p in props_t1], dtype=np.float64) + drift_dx   # → t coords
    cy_j = np.array([p["cy"] for p in props_t1], dtype=np.float64) + drift_dy
    a_j = np.array([p["area"] for p in props_t1], dtype=np.float64)

    dist = np.hypot(cx_t[:, None] - cx_j[None, :], cy_t[:, None] - cy_j[None, :])
    log_ratio = np.abs(np.log(a_t[:, None] / np.maximum(a_j[None, :], 1.0)))
    cost = np.full((n, m), INF)
    ok = (dist <= cfg.max_displacement_px) & (log_ratio <= cfg.area_ratio_tol)
    vals = (cfg.cost_w_centroid * dist / max(cfg.max_displacement_px, 1e-9)
            + cfg.cost_w_area * log_ratio)
    cost[ok] = vals[ok]

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
    """New array with local labels replaced by stable IDs (0 = background).

    Vectorized via a single lookup-table gather (``lut[labels]``) — O(pixels)
    instead of O(labels × pixels) boolean assignments. Identical result: labels
    absent from the map stay 0 (background), as before.
    """
    if not local_to_stable:
        return np.zeros_like(labels, dtype=np.int32)
    max_l = int(labels.max())
    lut = np.zeros(max_l + 1, dtype=np.int32)
    for local, stable in local_to_stable.items():
        if 0 <= local <= max_l:
            lut[local] = stable
    return lut[labels].astype(np.int32, copy=False)


# ──────────────────────────── merge genealogy ─────────────────────────────── #

def _area_lookup(id_map: np.ndarray) -> dict[int, int]:
    """``{stable_id: pixel_area}`` for a stable-ID label map (background excluded)."""
    flat = id_map.ravel()
    if flat.size == 0:
        return {}
    n = int(flat.max())
    if n == 0:
        return {}
    counts = np.bincount(flat, minlength=n + 1)
    return {int(i): int(counts[i]) for i in np.nonzero(counts)[0] if i > 0}


def _genealogy_parents(
    prev_id_map: np.ndarray,
    curr_labels: np.ndarray,
    area_prev: dict[int, int],
    tau: float,
) -> dict[int, dict[int, float]]:
    """Forward region genealogy for one frame transition.

    For each **current** local label, the set of **previous** stable IDs that are
    its parents, i.e. IDs *p* such that ``|footprint(p) ∩ region| / area(p) ≥ tau``
    — the fraction of the PARENT that flowed into the region (robust to incidental
    boundary overlap, which contributes few of the neighbour's pixels). ``≥ 2``
    parents ⇒ a merge. Drift is ignored in the overlap (small vs bubble size; same
    approximation as :func:`foam_gnn.export_csv.classify_deaths`).

    Parameters
    ----------
    prev_id_map : int32 (H, W)  — stable-ID map of frame t-1.
    curr_labels : int (H, W)    — LOCAL label map of frame t (0 = background).
    area_prev   : ``{stable_id: area}`` for ``prev_id_map``.

    Returns
    -------
    dict[curr_local -> dict[parent_stable -> parent_fraction]]  (only fracs ≥ tau).
    """
    pf = prev_id_map.ravel()
    cf = curr_labels.ravel()
    valid = (pf > 0) & (cf > 0)
    out: dict[int, dict[int, float]] = {}
    if not valid.any():
        return out
    p = pf[valid].astype(np.int64)
    c = cf[valid].astype(np.int64)
    stride = int(cf.max()) + 1                     # encode (parent, region) → one key
    uniq, cnt = np.unique(p * stride + c, return_counts=True)
    for k, n in zip(uniq.tolist(), cnt.tolist()):
        pi, ci = int(k // stride), int(k % stride)
        ap = area_prev.get(pi, 0)
        if ap > 0 and (n / ap) >= tau:
            out.setdefault(ci, {})[pi] = n / ap
    return out


def _choose_survivor(parents: set[int], rule: str, area_prev: dict[int, int],
                     exclude: set[int] | None = None) -> int | None:
    """Pick the stable ID a merged region inherits (see ``TrackConfig.merge_id_rule``).

    ``"keep_larger"`` → largest-area parent (physical continuity, DEFAULT), tie-broken
    by highest ID for determinism. ``"max"`` → highest ID. ``exclude`` removes parents
    already claimed by another region this frame (per-frame ID uniqueness); returns
    ``None`` if every parent is excluded.
    """
    cand = [p for p in parents if not exclude or p not in exclude]
    if not cand:
        return None
    if rule == "keep_larger":
        return max(cand, key=lambda p: (area_prev.get(p, 0), p))
    if rule != "max":
        raise ValueError(f"unknown merge_id_rule {rule!r}; choose 'keep_larger' or 'max'")
    return max(cand)


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

    # Extract per-bubble props ONCE per frame (was recomputed twice — as
    # props_prev then props_curr). Coordinate grids are shared across frames of the
    # session (constant shape); rebuilt inside _props_from_labels if a frame differs.
    rr, cc = _coord_grids(results[0].labels.shape)
    props_per_frame: list[list[dict]] = [_props_from_labels(r.labels, rr, cc) for r in results]

    # ── Frame 0: assign IDs 1..n_bubbles directly (local == stable) ───────── #
    props0 = props_per_frame[0]
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

    # Merge/flicker state. A merge creates a *cluster* remembering all parents and
    # their pre-merge footprints. While active (≤ ``W`` frames) a re-split of the
    # merged region is reconciled back to those footprints (merge-flicker); a
    # cluster that never re-splits is a real merge (→ a 'merge' event). No merge
    # ever mints a new ID: the region inherits ``merge_id_rule`` among its parents.
    clusters: list[dict] = []               # {merge_frame, last_frame, survivor, members:set, cx, cy}
    confirmed_merges: list[dict] = []        # aged-out clusters → merge events
    diag = {"n_merge_regions": 0, "n_resurrections": 0, "n_ambiguous_resurrections": 0,
            "n_births_remaining": 0, "n_dup_demoted": 0, "n_split_reconciled": 0}
    rule, tau, W = tcfg.merge_id_rule, tcfg.merge_overlap_frac, tcfg.merge_resurrect_window

    # ── Frames 1..n: match, detect merges, reconcile splits, assign IDs ────── #
    for t in range(1, len(results)):
        props_prev = props_per_frame[t - 1]
        props_curr = props_per_frame[t]
        prev_id_map = id_maps[t - 1]
        prev_stable_centroid = centroids_per_frame[t - 1]
        curr_labels = results[t].labels

        drift_dy, drift_dx = 0.0, 0.0
        if tcfg.register_drift:
            drift_dy, drift_dx = _estimate_drift(results[t - 1].foam_mask, results[t].foam_mask)
        cum_off_x += drift_dx
        cum_off_y += drift_dy
        frame_offsets.append((cum_off_x, cum_off_y))

        label_map, _unm_prev, _unm_curr = _match_frame_pair(
            props_prev, props_curr, drift_dy, drift_dx, tcfg
        )
        curr_centroid = {p["label"]: (p["cx"], p["cy"]) for p in props_curr}
        _foot_cache: dict[int, np.ndarray] = {}

        def _foot(c: int) -> np.ndarray:
            f = _foot_cache.get(c)
            if f is None:
                f = curr_labels == c
                _foot_cache[c] = f
            return f

        new_l2s: dict[int, int] = {}
        used_stable: set[int] = set()

        # ── A. fresh merges (genealogy: a region with ≥2 parents) ─────────── #
        area_prev = _area_lookup(prev_id_map)
        parents_of = _genealogy_parents(prev_id_map, curr_labels, area_prev, tau)
        for c, pdict in parents_of.items():
            ps = set(pdict)
            if len(ps) < 2:
                continue
            # A survivor ID may be claimed by at most ONE region this frame. If a
            # parent (e.g. one that splits ~50/50 into two merge regions) is already
            # taken, fall back to the next-best AVAILABLE parent by the same rule.
            # This preserves per-frame ID uniqueness for any merge_id_rule.
            surv = _choose_survivor(ps, rule, area_prev, exclude=used_stable)
            if surv is None:
                continue                                     # all parents claimed → not a merge here
            new_l2s[c] = surv
            used_stable.add(surv)
            diag["n_merge_regions"] += 1
            mcx, mcy = curr_centroid[c]
            clusters.append({"merge_frame": t, "last_frame": t - 1, "survivor": surv,
                             "members": set(ps), "cx": mcx, "cy": mcy})

        # ── B. reconcile a cluster only on a REAL re-split: the survivor's t-1
        #    footprint fans out to ≥2 current regions (precise test via the genealogy
        #    already computed). Then divide those fragments among the cluster members
        #    by PRE-MERGE footprint (survivor first) — merge-flicker. Otherwise the
        #    merged region persists as one; assign the survivor to it (so its
        #    continuation never births) and keep the cluster active. ─────────────── #
        surviving_clusters: list[dict] = []
        for cl in clusters:
            surv = cl["survivor"]
            if cl["merge_frame"] == t or (t - cl["merge_frame"]) > W:
                surviving_clusters.append(cl)                 # fresh, or aged-out (confirm in E)
                continue
            # survivor's t-1 footprint may fan out to several current regions; a
            # region is a "child" if it covers ≥ 0.3 of the survivor (# DECISION:
            # lower than the 0.5 merge threshold so uneven re-splits are caught).
            s_foot = prev_id_map == surv
            area_s = int(s_foot.sum())
            children = []
            if area_s:
                sub = curr_labels[s_foot]
                vals, cnts = np.unique(sub[sub > 0], return_counts=True)
                children = [int(v) for v, ct in zip(vals.tolist(), cnts.tolist())
                            if ct / area_s >= 0.3 and int(v) not in new_l2s]
            if len(children) < 2:                             # not split → survivor continues
                if children and children[0] not in new_l2s:
                    new_l2s[children[0]] = surv
                    used_stable.add(surv)
                surviving_clusters.append(cl)
                continue
            members = sorted(cl["members"], key=lambda m: (m != surv, m))   # survivor first
            matched: dict[int, int] = {}
            for m in members:
                foot_m = id_maps[cl["last_frame"]] == m
                am = int(foot_m.sum())
                if am == 0:
                    continue
                best_c, best_fr, second_fr = None, 0.0, 0.0
                for c in children:
                    if c in new_l2s:
                        continue
                    fr = float((_foot(c) & foot_m).sum()) / am
                    if fr > best_fr:
                        best_c, best_fr, second_fr = c, fr, best_fr
                    elif fr > second_fr:
                        second_fr = fr
                if best_c is not None and best_fr >= tau:
                    if second_fr >= (1.0 - tcfg.merge_ambiguous_frac) * best_fr:
                        diag["n_ambiguous_resurrections"] += 1
                    matched[m] = best_c
                    new_l2s[best_c] = m
                    used_stable.add(m)
            if len(matched) >= 2:                             # merged region re-split → flicker
                diag["n_split_reconciled"] += 1
                diag["n_resurrections"] += sum(1 for m in matched if m != surv)
                diag.setdefault("flicker_durations", []).append(t - cl["merge_frame"])
            else:
                surviving_clusters.append(cl)                 # not a clean split; keep active
        clusters = surviving_clusters

        # ── C. Hungarian matches for still-unassigned regions ─────────────── #
        for local_prev, local_curr in label_map.items():
            if local_curr in new_l2s:
                continue
            stable = local_to_stable.get(local_prev)
            if stable is None:
                continue
            if stable in used_stable:
                diag["n_dup_demoted"] += 1
                continue
            new_l2s[local_curr] = stable
            used_stable.add(stable)

        # ── D. genuinely unassigned regions → birth (segmentation split; the ONLY
        #    path that mints a new ID — NOT fixed by the merge/flicker guard) ── #
        for p in props_curr:
            c = p["label"]
            if c in new_l2s:
                continue
            cx, cy = curr_centroid[c]
            new_l2s[c] = id_next
            events.append(TopologicalEvent(
                frame=t, kind="birth", bubble_ids=(id_next,),
                meta={"local_label": c, "cx": cx, "cy": cy, "cause": "segmentation_split"},
            ))
            id_next += 1
            diag["n_births_remaining"] += 1

        # ── D.5 Guarantee per-frame ID uniqueness. A degenerate ~50/50 split can
        #    let two regions claim one stable ID across the merge / reconcile /
        #    match paths; keep it for the LARGER region and re-birth the rest
        #    (flagged). Rare; without it a frame's id_map would have fewer unique
        #    IDs than regions. ──────────────────────────────────────────────── #
        areas_by_local = {p["label"]: p["area"] for p in props_curr}
        keeper: dict[int, int] = {}
        for c in sorted(new_l2s, key=lambda k: -areas_by_local.get(k, 0)):
            s = new_l2s[c]
            if s in keeper:
                cx, cy = curr_centroid[c]
                new_l2s[c] = id_next
                events.append(TopologicalEvent(
                    frame=t, kind="birth", bubble_ids=(id_next,),
                    meta={"local_label": c, "cx": cx, "cy": cy,
                          "cause": "dedup_ambiguous_split"}))
                id_next += 1
                diag["n_births_remaining"] += 1
                diag["n_dup_demoted"] += 1
            else:
                keeper[s] = c

        # ── E. confirm merges whose cluster aged out without re-splitting ──── #
        kept: list[dict] = []
        for cl in clusters:
            (confirmed_merges if (t - cl["merge_frame"]) >= W else kept).append(cl)
        clusters = kept

        # ── F. previous IDs neither continued nor held in a cluster → T2 ───── #
        continued = set(new_l2s.values())
        held = set().union(*(cl["members"] for cl in clusters)) if clusters else set()
        for pid in set(local_to_stable.values()) - continued - held:
            cx, cy = prev_stable_centroid.get(pid, (float("nan"), float("nan")))
            events.append(TopologicalEvent(
                frame=t, kind="T2_disappear", bubble_ids=(pid,),
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

    # any cluster still active at session end never re-split → confirmed merge
    confirmed_merges.extend(clusters)
    clusters = []

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

    # ── confirmed merges → one 'merge' event per cluster (never re-split) ─── #
    n_merge_events = 0
    for cl in confirmed_merges:
        surv = cl["survivor"]
        merged = tuple(sorted(cl["members"] - {surv}))
        if not merged:
            continue                                    # degenerate (self only); skip
        n_merge_events += 1
        events.append(TopologicalEvent(
            frame=cl["merge_frame"], kind="merge",
            bubble_ids=tuple(sorted(cl["members"])),
            meta={"survivor": surv, "merged_ids": merged, "n_parents": len(cl["members"]),
                  "last_seen_frame": cl["merge_frame"] - 1, "cx": cl["cx"], "cy": cl["cy"]},
        ))

    # invariant-B diagnostic: no stable ID may exceed the frame-0 maximum
    frame0_max_id = int(id_maps[0].max()) if id_maps[0].size else 0
    max_id = max((int(m.max()) for m in id_maps if m.size), default=0)
    diag.update(n_merge_events=n_merge_events, frame0_max_id=frame0_max_id,
                max_bubble_id=max_id, invariant_B_holds=(max_id <= frame0_max_id))

    events.sort(key=lambda e: (e.frame, e.kind))
    return TrackingResult(
        id_maps=id_maps,
        events=events,
        correspondence=pd.DataFrame(corr_rows),
        n_tracks=id_next - 1,
        frame_offsets=frame_offsets,
        diagnostics=diag,
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
    kinds: tuple[str, ...] = ("T1_swap", "T2_disappear", "birth", "merge"),
    radius: int = 16,
) -> np.ndarray:
    """Overlay events observed at *frame* onto its raw image for visual audit.

    T1 → yellow circle + "T1" at the 4-bubble cluster centroid; T2 → red ✕ at the
    last-seen centroid; birth → green + at the new centroid; merge → magenta
    double-circle + "M" at the merged-region centroid.

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
        "merge": ((230, 40, 230), "M"),
    }
    for e in events:
        if e.frame != frame or e.kind not in kinds:
            continue
        cx, cy = e.meta.get("cx"), e.meta.get("cy")
        if cx is None or cy is None or not (np.isfinite(cx) and np.isfinite(cy)):
            continue
        c = (int(round(cx)), int(round(cy)))
        color, tag = style.get(e.kind, ((255, 255, 255), "?"))
        if e.kind == "merge":
            cv2.circle(rgb, c, radius, color, 2)
            cv2.circle(rgb, c, max(radius - 5, 3), color, 2)
        elif e.kind == "T1_swap":
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
