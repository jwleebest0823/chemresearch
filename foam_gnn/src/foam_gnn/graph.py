"""
foam_gnn.graph  (MODULE 3)
==========================
Per-frame **graph construction**: nodes = bubbles, edges = adjacent bubble pairs
that share a film. Built with NetworkX; optionally converted to a PyTorch
Geometric ``Data`` object via a lazy import (the base package stays torch-free —
see :mod:`foam_gnn.guards`).

Assumptions
-----------
* Input is one *tracking session* worth of Module-1 ``SegmentationResult`` plus the
  Module-2 ``TrackingResult`` (stable ``id_maps``, ``correspondence``,
  ``frame_offsets``). Graphs are built in **stable-ID space**, so a node's
  ``bubble_id`` is the same identity across frames.
* Topology (which bubbles are adjacent, and the shared-border length) comes from
  the stable-ID label map via :func:`foam_gnn.tracking._adjacency_lengths`
  (shared-boundary pixel count — robust, no polygon intersection).
* Node ``area``/``centroid`` are **reused** from the tracking correspondence where
  available (not recomputed); ``perimeter`` (hence ``circularity``) and ``n_sides``
  are the new work. ``distance_to_evap_edge`` reuses the Module-1 ``dist_to_edge``
  map (distance transform of the foam mask = distance to the open evaporation
  perimeter), sampled in **native** pixel coordinates.
* Spatial coordinates reported on nodes (``centroid_x``/``centroid_y``) are in the
  **registered/common (frame-0) coordinate frame** (native + ``frame_offsets[t]``).
  Pixel *sampling* of ``dist_to_edge`` always uses native coordinates (that is
  where the map is defined). Edge features are translation-invariant, so the
  coordinate frame does not affect them.

Shapes
------
``id_map`` : int32 ``(H, W)`` (0 = background). ``dist_to_edge`` : float32 ``(H, W)``.
"""
from __future__ import annotations

import math

import numpy as np

from .config import GraphConfig, PipelineConfig
from .guards import check_array
from .segmentation import SegmentationResult
from .tracking import (TrackingResult, _adjacency_lengths,
                       adjacency_lengths_bridged, bridge_distance_px)

__all__ = [
    "build_frame_graph",
    "build_session_graphs",
    "graph_to_pyg",
    "NODE_FEATURES",
    "EDGE_FEATURES",
]

NODE_FEATURES = ("area", "n_sides", "centroid_x", "centroid_y",
                 "circularity", "perimeter", "distance_to_evap_edge")
EDGE_FEATURES = ("contact_line_length", "squeezing_strain", "distance_to_evap_edge")


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _region_geometry(id_map: np.ndarray) -> dict[int, dict]:
    """Per stable-ID region geometry from a label map.

    Returns ``{bubble_id: {"area", "cx", "cy", "perimeter"}}`` with native
    centroid coordinates and a Crofton-style perimeter estimate.
    ``perimeter`` is approximate on pixelated watershed lines (``# DECISION``:
    acceptable for a coarse circularity diagnostic).
    """
    from skimage.measure import regionprops

    out: dict[int, dict] = {}
    for p in regionprops(id_map):
        out[int(p.label)] = {
            "area": int(p.area),
            "cy": float(p.centroid[0]),   # regionprops centroid = (row, col) = (y, x)
            "cx": float(p.centroid[1]),
            "perimeter": float(p.perimeter),
        }
    return out


def _sample(dist: np.ndarray, x: float, y: float) -> float:
    """Sample a map at native ``(x, y)`` with bounds clipping (fail-soft at edges)."""
    h, w = dist.shape
    xi = int(min(max(round(x), 0), w - 1))
    yi = int(min(max(round(y), 0), h - 1))
    return float(dist[yi, xi])


def _circularity(area: float, perimeter: float) -> float:
    """``4π·area / perimeter²`` (1.0 for a perfect circle). NaN if perimeter≈0."""
    if perimeter <= 1e-9:
        return float("nan")
    return float(4.0 * math.pi * area / (perimeter * perimeter))


def _squeezing_strain(area_i: float, area_j: float, d_ij: float) -> float:
    """ε = ((R_i + R_j) − d_ij) / (R_i + R_j), with R = √(A/π).

    # DECISION: R is an **effective-circular** radius. This approximation
    degrades for the polygonal bubbles of the late, dry, coarsened foam (their
    real extent along the centroid line differs from √(A/π)); treat ε as a
    qualitative squeezing proxy, not a calibrated mechanical strain.
    """
    r_i = math.sqrt(max(area_i, 0.0) / math.pi)
    r_j = math.sqrt(max(area_j, 0.0) / math.pi)
    denom = r_i + r_j
    if denom <= 1e-9:
        return float("nan")
    return float((denom - d_ij) / denom)


# --------------------------------------------------------------------------- #
# Frame graph
# --------------------------------------------------------------------------- #
def build_frame_graph(
    id_map: np.ndarray,
    dist_to_edge: np.ndarray,
    *,
    cfg: GraphConfig,
    node_props: dict[int, dict] | None = None,
    frame_offset: tuple[float, float] = (0.0, 0.0),
    frame: int = 0,
    time_seconds: float = 0.0,
):
    """Build one frame's bubble graph.

    Parameters
    ----------
    id_map : int32 (H, W)
        Stable-ID label map (0 = background).
    dist_to_edge : float32 (H, W)
        Module-1 distance-to-evaporation-edge map for this frame (native coords).
    cfg : GraphConfig
        ``min_shared_border_px`` gates edges / ``n_sides``.
    node_props : dict[int, {"area","cx","cy"}], optional
        Reused native area/centroid per stable id (from tracking correspondence).
        Missing ids fall back to recomputed geometry.
    frame_offset : (off_x, off_y)
        Cumulative drift (``frame_offsets[t]``) → registered centroids.
    frame, time_seconds : graph-level metadata.

    Returns
    -------
    networkx.Graph
        Nodes keyed by ``bubble_id`` with attributes in :data:`NODE_FEATURES`
        (plus ``centroid_x_native``/``centroid_y_native`` for sampling provenance);
        edges with attributes in :data:`EDGE_FEATURES`. Graph attrs: ``frame``,
        ``time_seconds``, ``n_nodes``, ``n_edges``.
    """
    import networkx as nx

    check_array("graph.id_map", id_map, ndim=2, nonneg=True)
    check_array("graph.dist_to_edge", dist_to_edge, ndim=2, finite=True)
    if id_map.shape != dist_to_edge.shape:
        raise ValueError(f"id_map {id_map.shape} != dist_to_edge {dist_to_edge.shape}")

    geom = _region_geometry(id_map)
    off_x, off_y = float(frame_offset[0]), float(frame_offset[1])

    # native area/centroid: reuse correspondence where given, else recomputed geom
    def native(bid: int) -> tuple[float, float, float]:
        if node_props and bid in node_props:
            p = node_props[bid]
            return float(p["area"]), float(p["cx"]), float(p["cy"])
        g = geom[bid]
        return float(g["area"]), float(g["cx"]), float(g["cy"])

    gcfg = cfg
    if getattr(gcfg, "bridge_gaps", "off") == "on":
        _inside = dist_to_edge > 0            # foam interior only; never bridge outside
        _bridge = bridge_distance_px(id_map, gcfg.bridge_radius_frac,
                                     gcfg.bridge_gap_quantile, inside=_inside)
        adj = adjacency_lengths_bridged(id_map, _bridge, inside=_inside)
    elif getattr(gcfg, "bridge_gaps", "off") == "off":
        adj = _adjacency_lengths(id_map)
    else:
        raise ValueError(f"unknown graph.bridge_gaps={gcfg.bridge_gaps!r}; choose 'on'/'off'")
    mb = cfg.min_shared_border_px
    # n_sides = number of neighbours sharing a film of at least mb pixels
    degree: dict[int, int] = {}
    for pair, length in adj.items():
        if length >= mb:
            for b in pair:
                degree[b] = degree.get(b, 0) + 1

    G = nx.Graph(frame=int(frame), time_seconds=float(time_seconds))

    ids = [int(b) for b in np.unique(id_map) if b > 0]
    for bid in ids:
        area, cx_n, cy_n = native(bid)
        perim = geom[bid]["perimeter"] if bid in geom else float("nan")
        d_edge = _sample(dist_to_edge, cx_n, cy_n)
        G.add_node(
            bid,
            bubble_id=bid,
            area=float(area),
            n_sides=int(degree.get(bid, 0)),
            centroid_x=float(cx_n + off_x),     # registered (common-frame) coords
            centroid_y=float(cy_n + off_y),
            centroid_x_native=float(cx_n),
            centroid_y_native=float(cy_n),
            circularity=_circularity(area, perim),
            perimeter=float(perim),
            distance_to_evap_edge=float(d_edge),
        )

    for pair, length in adj.items():
        if length < mb:
            continue
        i, j = sorted(int(x) for x in pair)
        if i not in G or j not in G:
            continue
        ai, xi, yi = native(i)
        aj, xj, yj = native(j)
        d_ij = float(math.hypot(xi - xj, yi - yj))
        mx, my = (xi + xj) / 2.0, (yi + yj) / 2.0
        G.add_edge(
            i, j,
            contact_line_length=float(length),
            squeezing_strain=_squeezing_strain(ai, aj, d_ij),
            distance_to_evap_edge=_sample(dist_to_edge, mx, my),
            centroid_distance=d_ij,
        )

    G.graph["n_nodes"] = G.number_of_nodes()
    G.graph["n_edges"] = G.number_of_edges()
    return G


def build_session_graphs(
    results: list[SegmentationResult],
    tracking: TrackingResult,
    cfg: PipelineConfig,
    *,
    times_seconds: list[float] | None = None,
) -> list:
    """Build a graph for every frame of one tracking session.

    Reuses the tracking ``correspondence`` (area/centroid) and ``frame_offsets``;
    pulls ``dist_to_edge`` from each frame's ``SegmentationResult``.

    Parameters
    ----------
    results : per-frame Module-1 outputs (same order as ``tracking.id_maps``).
    tracking : Module-2 output for the same session.
    times_seconds : per-frame seconds since session start; defaults to
        ``frame_index * track.interval`` is NOT assumed — pass real timestamps for
        the CSV. If None, falls back to the frame index.

    Returns
    -------
    list[networkx.Graph]
    """
    if len(results) != len(tracking.id_maps):
        raise ValueError(
            f"results ({len(results)}) and id_maps ({len(tracking.id_maps)}) length mismatch"
        )
    corr = tracking.correspondence
    offsets = tracking.frame_offsets or [(0.0, 0.0)] * len(results)
    graphs = []
    for t in range(len(results)):
        sub = corr[corr["frame"] == t]
        node_props = {
            int(r.bubble_id): {"area": float(r.area_px), "cx": float(r.cx), "cy": float(r.cy)}
            for r in sub.itertuples() if int(r.bubble_id) > 0
        }
        ts = float(times_seconds[t]) if times_seconds is not None else float(t)
        graphs.append(build_frame_graph(
            tracking.id_maps[t], results[t].dist_to_edge,
            cfg=cfg.graph, node_props=node_props,
            frame_offset=offsets[t], frame=t, time_seconds=ts,
        ))
    return graphs


# --------------------------------------------------------------------------- #
# Optional PyTorch Geometric export (lazy import)
# --------------------------------------------------------------------------- #
def graph_to_pyg(
    G,
    *,
    node_features: tuple[str, ...] = NODE_FEATURES,
    edge_features: tuple[str, ...] = EDGE_FEATURES,
):
    """Convert a frame graph to a PyTorch Geometric ``Data`` object.

    Lazy import: ``torch`` / ``torch_geometric`` are an optional extra
    (``pip install -e ".[ml]"``). Raises a clear ``ImportError`` if absent so the
    NetworkX + CSV path never requires a deep-learning stack.

    Returns
    -------
    torch_geometric.data.Data
        ``x`` (n_nodes × len(node_features)), ``edge_index`` (2 × 2·n_edges,
        undirected → both directions), ``edge_attr`` (2·n_edges × len(edge_features)),
        ``bubble_id`` (n_nodes,), and graph-level ``frame`` / ``time_seconds``.
    """
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "graph_to_pyg needs torch + torch_geometric (optional extra). "
            "Install with: pip install -e \".[ml]\"  (or defer to the modeling module). "
            f"Original error: {exc}"
        ) from exc

    nodes = list(G.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    x = torch.tensor(
        [[float(G.nodes[n][f]) for f in node_features] for n in nodes],
        dtype=torch.float32,
    ) if nodes else torch.zeros((0, len(node_features)), dtype=torch.float32)
    bubble_id = torch.tensor([int(G.nodes[n]["bubble_id"]) for n in nodes], dtype=torch.long)

    src, dst, eattr = [], [], []
    for i, j, d in G.edges(data=True):
        for a, b in ((i, j), (j, i)):            # undirected → store both directions
            src.append(idx[a])
            dst.append(idx[b])
            eattr.append([float(d[f]) for f in edge_features])
    edge_index = torch.tensor([src, dst], dtype=torch.long) if src else torch.zeros((2, 0), dtype=torch.long)
    edge_attr = (torch.tensor(eattr, dtype=torch.float32)
                 if eattr else torch.zeros((0, len(edge_features)), dtype=torch.float32))

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    data.bubble_id = bubble_id
    data.frame = int(G.graph.get("frame", 0))
    data.time_seconds = float(G.graph.get("time_seconds", 0.0))
    return data
