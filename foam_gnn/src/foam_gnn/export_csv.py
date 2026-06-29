"""
foam_gnn.export_csv
===================
Long-format (tidy) CSV export of the per-frame bubble graphs — the deliverable
requested by the mentor. Two files per foam (Foam C: per session):

* ``nodes.csv`` — one row per (frame, bubble_id).
* ``edges.csv`` — one row per (frame, bubble_id_i, bubble_id_j).

Why long format
---------------
Bubbles are born and disappear, so a fixed-width "one column per bubble" matrix
would be mostly padding. In long format a bubble simply has **no rows after its
last frame** (disappearance/coalescence) and **no rows before its first**
(birth) — topology change is represented by presence/absence, not sentinels.

Event labels are PRELIMINARY
----------------------------
The ``event`` column (``disappear``/``coalesce``) is derived from Module-2's
topological log, which is **contaminated by segmentation flicker**: small bubbles
blinking in/out of detection produce spurious disappear+birth pairs. The
``event_confidence`` column (``low``/``medium``) is a transparent heuristic, NOT a
calibrated probability. Treat all event labels as preliminary pending
noise-robustness work — this caveat is repeated in ``README_csv.md`` so it
travels with the data.

Assumptions
-----------
* One ``export_session`` call = one tracking session (Foam C is 5 sessions).
* ``disappear`` vs ``coalesce`` is decided by native-pixel footprint overlap
  (drift between consecutive frames is small, ~2.6 px median) — see
  :func:`classify_deaths`.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .graph import build_session_graphs
from .segmentation import SegmentationResult
from .tracking import TrackingResult, _adjacency_lengths

__all__ = [
    "NODE_COLUMNS",
    "EDGE_COLUMNS",
    "classify_deaths",
    "export_session",
    "write_session_csvs",
    "write_readme",
]

NODE_COLUMNS = [
    "foam", "session", "frame", "time_seconds", "bubble_id",
    "area", "n_sides", "centroid_x", "centroid_y", "circularity", "perimeter",
    "distance_to_evap_edge", "event", "event_confidence",
]
EDGE_COLUMNS = [
    "foam", "session", "frame", "time_seconds", "bubble_id_i", "bubble_id_j",
    "contact_line_length", "squeezing_strain", "distance_to_evap_edge",
]


def classify_deaths(
    results: list[SegmentationResult],
    tracking: TrackingResult,
    cfg: PipelineConfig,
) -> dict[tuple[int, int], dict]:
    """Classify each T2 death as ``disappear`` or ``coalesce`` with a confidence.

    Heuristic (``# DECISION``): for a bubble ``b`` last seen at frame ``t-1`` and
    absent at ``t``, look at which surviving stable id covers ``b``'s last
    footprint in frame ``t``. If a single, previously-adjacent neighbour ``s``
    covers ≥ ``coalesce_min_overlap_frac`` of that footprint **and** grew from
    ``t-1`` to ``t``, label ``coalesce`` (absorbed into ``s``); otherwise
    ``disappear``. Overlap is in native pixels (small inter-frame drift ignored).

    ``event_confidence`` is ``low`` when the bubble's lifetime ≤
    ``event_low_conf_max_lifetime`` or its last area < ``event_low_conf_area_px``
    (both flicker-prone), else ``medium``. NOT calibrated.

    Returns
    -------
    dict[(last_seen_frame, bubble_id) -> {"event", "event_confidence", "absorber_id"}]
        Keyed so it attaches to the bubble's final node row.
    """
    gcfg = cfg.graph
    corr = tracking.correspondence
    # lifetime (frames present) and per-(frame,id) area for quick lookup
    lifetime = corr[corr["bubble_id"] > 0].groupby("bubble_id")["frame"].nunique().to_dict()
    area_at = {(int(r.frame), int(r.bubble_id)): float(r.area_px)
               for r in corr.itertuples() if int(r.bubble_id) > 0}

    out: dict[tuple[int, int], dict] = {}
    for e in tracking.events:
        if e.kind != "T2_disappear":
            continue
        b = int(e.bubble_ids[0])
        t_last = int(e.meta.get("last_seen_frame", e.frame - 1))
        t = t_last + 1
        if not (0 <= t_last < len(tracking.id_maps) and t < len(tracking.id_maps)):
            continue
        foot = tracking.id_maps[t_last] == b
        area_b = int(foot.sum())
        label, absorber = "disappear", None
        if area_b > 0:
            covering = tracking.id_maps[t][foot]
            covering = covering[covering > 0]
            if covering.size:
                vals, counts = np.unique(covering, return_counts=True)
                s = int(vals[counts.argmax()])
                overlap_frac = float(counts.max()) / area_b
                adj_prev = _adjacency_lengths(tracking.id_maps[t_last])
                was_adjacent = frozenset((b, s)) in adj_prev
                grew = area_at.get((t, s), 0.0) > area_at.get((t_last, s), 0.0)
                if overlap_frac >= gcfg.coalesce_min_overlap_frac and was_adjacent and grew:
                    label, absorber = "coalesce", s
        last_area = area_at.get((t_last, b), float(area_b))
        conf = ("low"
                if lifetime.get(b, 0) <= gcfg.event_low_conf_max_lifetime
                or last_area < gcfg.event_low_conf_area_px
                else "medium")
        out[(t_last, b)] = {"event": label, "event_confidence": conf, "absorber_id": absorber}
    return out


def export_session(
    results: list[SegmentationResult],
    tracking: TrackingResult,
    cfg: PipelineConfig,
    *,
    foam: str,
    session: str,
    timestamps: list[datetime] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build ``(nodes_df, edges_df)`` for one session in long/tidy format.

    Parameters
    ----------
    results, tracking : Module-1/2 outputs for the same session.
    foam : "A" | "C" (Foam B excluded upstream).
    session : experiment label, e.g. "exp1" / "exp3".
    timestamps : per-frame datetimes; ``time_seconds`` = seconds since the first.
        If None, ``time_seconds`` falls back to the frame index.

    Returns
    -------
    (nodes_df, edges_df) with columns :data:`NODE_COLUMNS` / :data:`EDGE_COLUMNS`.
    """
    if timestamps is not None:
        if len(timestamps) != len(results):
            raise ValueError(f"timestamps ({len(timestamps)}) != frames ({len(results)})")
        t0 = timestamps[0]
        times = [float((ts - t0).total_seconds()) for ts in timestamps]
    else:
        times = [float(t) for t in range(len(results))]

    graphs = build_session_graphs(results, tracking, cfg, times_seconds=times)
    deaths = classify_deaths(results, tracking, cfg)

    node_rows: list[dict] = []
    edge_rows: list[dict] = []
    for t, G in enumerate(graphs):
        tsec = G.graph["time_seconds"]
        for bid, a in G.nodes(data=True):
            ev = deaths.get((t, int(bid)), None)
            node_rows.append({
                "foam": foam, "session": session, "frame": t, "time_seconds": tsec,
                "bubble_id": int(bid), "area": a["area"], "n_sides": a["n_sides"],
                "centroid_x": a["centroid_x"], "centroid_y": a["centroid_y"],
                "circularity": a["circularity"], "perimeter": a["perimeter"],
                "distance_to_evap_edge": a["distance_to_evap_edge"],
                "event": ev["event"] if ev else "",
                "event_confidence": ev["event_confidence"] if ev else "",
            })
        for i, j, d in G.edges(data=True):
            lo, hi = sorted((int(i), int(j)))
            edge_rows.append({
                "foam": foam, "session": session, "frame": t, "time_seconds": tsec,
                "bubble_id_i": lo, "bubble_id_j": hi,
                "contact_line_length": d["contact_line_length"],
                "squeezing_strain": d["squeezing_strain"],
                "distance_to_evap_edge": d["distance_to_evap_edge"],
            })

    nodes_df = pd.DataFrame(node_rows, columns=NODE_COLUMNS)
    edges_df = pd.DataFrame(edge_rows, columns=EDGE_COLUMNS)
    _validate(nodes_df, edges_df)
    return nodes_df, edges_df


def _validate(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> None:
    """Fail loud on structural problems / non-finite (Inf) numeric values.

    NaN is *allowed* in ``circularity``/``squeezing_strain`` (degenerate geometry)
    but counted; Inf is never allowed.
    """
    if not nodes_df.empty:
        if (nodes_df["bubble_id"] <= 0).any():
            raise ValueError("nodes.csv contains non-positive bubble_id")
        num = ["area", "centroid_x", "centroid_y", "perimeter", "distance_to_evap_edge"]
        for c in num:
            if np.isinf(nodes_df[c].to_numpy(dtype=float)).any():
                raise ValueError(f"nodes.csv column {c!r} contains Inf")
        bad_ev = set(nodes_df["event"].unique()) - {"", "disappear", "coalesce"}
        if bad_ev:
            raise ValueError(f"nodes.csv has unexpected event labels: {bad_ev}")
    if not edges_df.empty:
        for c in ("contact_line_length", "distance_to_evap_edge"):
            arr = edges_df[c].to_numpy(dtype=float)
            if np.isinf(arr).any():
                raise ValueError(f"edges.csv column {c!r} contains Inf")
        if (edges_df["contact_line_length"] <= 0).any():
            raise ValueError("edges.csv has non-positive contact_line_length")


def write_session_csvs(out_dir: str | Path, nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> tuple[Path, Path]:
    """Write ``nodes.csv`` / ``edges.csv`` into ``out_dir`` (created if needed)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    nodes_path, edges_path = out / "nodes.csv", out / "edges.csv"
    nodes_df.to_csv(nodes_path, index=False)
    edges_df.to_csv(edges_path, index=False)
    return nodes_path, edges_path


_README = """\
# Foam graph CSV export — format & caveats

Per-frame bubble graphs for the evaporating quasi-2D foam, in **long (tidy)**
format. Nodes are bubbles; edges are adjacent bubble pairs sharing a film.
Generated by `foam_gnn.export_csv`. Spatial units are **pixels** (no µm/px scale
in the data); areas in **px²**; `time_seconds` is seconds since each session's
first frame.

## Files (per foam; Foam C per session)
- `nodes.csv` — one row per (frame, bubble_id).
- `edges.csv` — one row per (frame, bubble_id_i, bubble_id_j).

Foam B (exp2) is **excluded**: its higher magnification leaves no background, so
segmentation and the evaporation-edge boundary are not yet reliable.

## Why long format handles disappearance cleanly
A bubble exists only on the frames where it is detected: it has **no rows after
its last frame** (disappearance/coalescence) and **none before its first**
(birth). No fixed-width padding, no sentinel rows — births and deaths are encoded
by presence/absence.

## nodes.csv columns
| column | meaning |
|---|---|
| foam, session | foam id ("A"/"C") and experiment ("exp1"…); session distinguishes Foam C's 5 runs |
| frame, time_seconds | frame index and seconds since session start |
| bubble_id | **stable** identity across frames (Module 2 tracking) |
| area | bubble area (px²) |
| n_sides | number of neighbouring bubbles sharing a film ≥ min_shared_border_px (von Neumann n) |
| centroid_x, centroid_y | centroid in the **registered/common (frame-0) frame** (drift-corrected) |
| circularity | 4π·area / perimeter² (1.0 = circle); NaN if perimeter≈0 |
| perimeter | region perimeter (px), Crofton estimate (approximate on pixelated films) |
| distance_to_evap_edge | shortest distance (px) from the bubble centroid to the foam's open evaporation boundary |
| event | empty, except a bubble's **final** frame: `disappear` or `coalesce` — **PRELIMINARY** |
| event_confidence | `low` / `medium` heuristic on the event label — **NOT calibrated** |

(`event`/`event_confidence` are empty strings for normal frames; `pandas.read_csv`
reads those as `NaN` unless you pass `keep_default_na=False` — empty simply means
"no event this frame".)

## edges.csv columns
| column | meaning |
|---|---|
| foam, session, frame, time_seconds | as above |
| bubble_id_i, bubble_id_j | the two adjacent bubbles (i < j) |
| contact_line_length | shared-film length (px), counted as shared-boundary pixels (primary feature; von Neumann diffusion channel) |
| squeezing_strain | ε = ((R_i+R_j) − d_ij)/(R_i+R_j), R=√(A/π), d_ij=centroid distance. **Effective-circular** R — degrades for polygonal late-stage bubbles |
| distance_to_evap_edge | distance (px) from the edge midpoint to the evaporation boundary |

An edge disappears from the table when its shared film vanishes.

## ⚠ Event labels are PRELIMINARY (read before using `event`)
`disappear`/`coalesce` come from Module-2's topological event log, which is
**contaminated by segmentation flicker**: small bubbles near the detection limit
blink in and out, producing spurious `disappear` (and matching `birth`) events.
Across thresholds the death and birth counts track each other — the signature of
flicker, not real coarsening. `event_confidence` is a transparent heuristic
(`low` for short-lived or tiny bubbles), not a probability. **Do not treat raw
event counts as physical T2/coalescence rates** until noise-robustness work lands.
Node/edge geometric features (area, contact_line_length, etc.) are not affected by
this caveat.
"""


def write_readme(out_dir: str | Path) -> Path:
    """Write ``README_csv.md`` (format + preliminary-event caveat) into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "README_csv.md"
    path.write_text(_README, encoding="utf-8")
    return path
