"""
Smoke + correctness tests for MODULE 3 (graph construction).

Synthetic label maps with KNOWN adjacency/geometry verify the feature math
(contact_line_length, n_sides, circularity, squeezing_strain, dist sampling,
registered coordinates). PyG conversion is exercised only if torch_geometric is
installed (it is an optional extra).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from foam_gnn.config import GraphConfig, PipelineConfig
from foam_gnn.graph import (
    EDGE_FEATURES,
    NODE_FEATURES,
    build_frame_graph,
    graph_to_pyg,
)


def _two_bubbles() -> tuple[np.ndarray, np.ndarray]:
    """30x30 map: bubble 1 | bubble 2 share a vertical film of length 20.

    dist_to_edge is a ramp ``dist[y, x] = x`` so sampling is checkable.
    """
    labels = np.zeros((30, 30), np.int32)
    labels[5:25, 5:15] = 1     # rows 5-24, cols 5-14  -> area 200
    labels[5:25, 15:25] = 2    # rows 5-24, cols 15-24 -> area 200
    dist = np.tile(np.arange(30, dtype=np.float32), (30, 1))   # dist[y,x] = x
    return labels, dist


def test_build_frame_graph_basic():
    labels, dist = _two_bubbles()
    G = build_frame_graph(labels, dist, cfg=GraphConfig(), frame_offset=(100.0, 200.0),
                          frame=7, time_seconds=210.0)
    assert set(G.nodes) == {1, 2}
    assert G.number_of_edges() == 1
    assert G.graph["frame"] == 7 and G.graph["time_seconds"] == 210.0

    # node geometry
    for bid, cx_native in ((1, 9.5), (2, 19.5)):
        n = G.nodes[bid]
        assert n["area"] == 200
        assert n["n_sides"] == 1
        assert abs(n["centroid_x_native"] - cx_native) < 1e-6
        assert abs(n["centroid_x"] - (cx_native + 100.0)) < 1e-6   # registered = native + offset
        assert abs(n["centroid_y"] - (14.5 + 200.0)) < 1e-6
        # distance sampled from the ramp ~ centroid column
        assert abs(n["distance_to_evap_edge"] - cx_native) <= 1.0
        # near-rectangular bubble: circularity below 1 and positive
        assert 0.0 < n["circularity"] < 1.0

    # edge features
    e = G.edges[1, 2]
    assert e["contact_line_length"] == 20.0          # shared-border pixel count
    R = math.sqrt(200 / math.pi)
    expected_strain = ((2 * R) - 10.0) / (2 * R)      # d_ij = 10
    assert abs(e["squeezing_strain"] - expected_strain) < 1e-6
    assert abs(e["distance_to_evap_edge"] - 14.5) <= 1.0


def test_min_border_filter_controls_edges_and_n_sides():
    labels = np.zeros((12, 30), np.int32)
    labels[0:10, 0:10] = 1
    labels[0:10, 10:20] = 2          # shares 10-px film with 1
    labels[0:2, 20:25] = 3           # shares only 2-px film with 2
    dist = np.ones((12, 30), np.float32)

    g_strict = build_frame_graph(labels, dist, cfg=GraphConfig(min_shared_border_px=3))
    assert g_strict.has_edge(1, 2)
    assert not g_strict.has_edge(2, 3)               # 2-px film gated out
    assert g_strict.nodes[2]["n_sides"] == 1
    assert g_strict.nodes[3]["n_sides"] == 0

    g_loose = build_frame_graph(labels, dist, cfg=GraphConfig(min_shared_border_px=1))
    assert g_loose.has_edge(2, 3)
    assert g_loose.nodes[2]["n_sides"] == 2


def test_circularity_of_disc_near_one():
    # a filled disc should have circularity close to 1
    H = W = 60
    yy, xx = np.ogrid[:H, :W]
    labels = ((yy - 30) ** 2 + (xx - 30) ** 2 <= 20 ** 2).astype(np.int32)
    dist = np.ones((H, W), np.float32)
    G = build_frame_graph(labels, dist, cfg=GraphConfig())
    assert 0.85 < G.nodes[1]["circularity"] <= 1.05


def test_guards_reject_bad_inputs():
    labels, dist = _two_bubbles()
    with pytest.raises(ValueError):
        build_frame_graph(labels, dist[:10], cfg=GraphConfig())     # shape mismatch
    bad = dist.copy()
    bad[0, 0] = np.inf
    with pytest.raises(ValueError):
        build_frame_graph(labels, bad, cfg=GraphConfig())           # non-finite dist


def test_graph_to_pyg_optional():
    pytest.importorskip("torch_geometric")
    labels, dist = _two_bubbles()
    G = build_frame_graph(labels, dist, cfg=GraphConfig())
    data = graph_to_pyg(G)
    assert data.x.shape == (2, len(NODE_FEATURES))
    assert data.edge_index.shape == (2, 2)            # 1 undirected edge -> 2 directed
    assert data.edge_attr.shape == (2, len(EDGE_FEATURES))
    assert data.bubble_id.tolist() == [1, 2]


def test_node_edge_feature_names_match_config():
    cfg = PipelineConfig()
    assert tuple(cfg.graph.node_features) == NODE_FEATURES
    assert tuple(cfg.graph.edge_features) == EDGE_FEATURES
