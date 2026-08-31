"""Tests for foam_gnn.gnn (optional torch extra). Skipped when torch is absent.

Covers the properties the design depends on: the model learns a signal that REQUIRES
topology (so the GNN-vs-MLP comparison is meaningful), it is invariant to
rotation/reflection by construction, and it degrades gracefully with no edges.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from foam_gnn.gnn import (  # noqa: E402
    EDGE_FEATURES_GNN,
    FoamGNN,
    FrameGraph,
    augment_graph,
    train_gnn_ensemble,
)


def _ring_graph(n: int, seed: int, neighbour_signal: bool) -> FrameGraph:
    """A ring of n bubbles. Target depends on the NEIGHBOURS' areas when
    ``neighbour_signal`` — a signal only a topology-aware model can capture."""
    rng = np.random.default_rng(seed)
    area = rng.uniform(500, 4000, size=n)
    x = np.stack([area, rng.integers(4, 8, size=n).astype(float),
                  rng.uniform(5, 200, size=n)], axis=1)
    src = np.arange(n)
    dst = (src + 1) % n
    ei = np.stack([np.concatenate([src, dst]), np.concatenate([dst, src])])
    ea = np.zeros((ei.shape[1], len(EDGE_FEATURES_GNN)))
    ea[:, 0] = 30.0
    nb = area[(src + 1) % n] + area[(src - 1) % n]
    y = (nb - 2 * area) * 1e-3 if neighbour_signal else area * 1e-3
    return FrameGraph(x=x, edge_index=ei, edge_attr=ea, y=y,
                      mask=np.ones(n, dtype=bool), bubble_uid=[f"s:{i}" for i in range(n)],
                      foam="A", session="s", frame=0)


def test_forward_shapes_and_no_edge_case():
    g = _ring_graph(12, 0, True)
    import torch
    m = FoamGNN(g.x.shape[1], len(EDGE_FEATURES_GNN), hidden=16, n_mp=2, dropout=0.0)
    out = m(torch.as_tensor(g.x, dtype=torch.float32),
            torch.as_tensor(g.edge_index, dtype=torch.long),
            torch.as_tensor(g.edge_attr, dtype=torch.float32))
    assert out.shape == (12,)
    # an isolated-node graph (no edges) must still run
    out2 = m(torch.as_tensor(g.x, dtype=torch.float32),
             torch.zeros((2, 0), dtype=torch.long),
             torch.zeros((0, len(EDGE_FEATURES_GNN)), dtype=torch.float32))
    assert out2.shape == (12,) and torch.isfinite(out2).all()


def test_rejects_bad_message_passing_depth():
    with pytest.raises(ValueError, match="n_mp"):
        FoamGNN(3, 4, hidden=8, n_mp=0)


def test_isotropy_holds_by_construction():
    # The design asks for rotation/reflection augmentation. Because no absolute position
    # or angle is a feature, invariance is structural: rotating the foam cannot change
    # any input. This test pins that no positional feature sneaks in later.
    from foam_gnn.gnn import NODE_FEATURES_GNN
    for f in NODE_FEATURES_GNN + EDGE_FEATURES_GNN:
        assert "centroid" not in f and f not in ("cx", "cy"), \
            f"{f} is positional — that breaks isotropy"


def test_augment_preserves_topology_and_targets():
    g = _ring_graph(10, 1, True)
    a = augment_graph(g, np.random.default_rng(0), noise=0.05)
    assert np.array_equal(a.edge_index, g.edge_index)
    assert np.array_equal(a.y, g.y)
    assert not np.allclose(a.x[:, 0], g.x[:, 0])      # areas jittered


def test_gnn_learns_a_neighbour_dependent_signal():
    # Sanity that the harness can learn at all, on a signal that NEEDS the graph.
    tr = [_ring_graph(24, s, True) for s in range(6)]
    va = [_ring_graph(24, 100 + s, True) for s in range(2)]
    te = [_ring_graph(24, 200 + s, True) for s in range(2)]
    out = train_gnn_ensemble(tr, va, te, hidden=32, n_mp=2, dropout=0.0,
                             max_epochs=400, patience=80, n_seeds=1, augment_noise=0.0)
    y = np.concatenate([g.y[g.mask] for g in te])
    mae_gnn = float(np.mean(np.abs(out["pred_test"] - y)))
    mae_mean = float(np.mean(np.abs(np.mean(np.concatenate([g.y[g.mask] for g in tr])) - y)))
    assert mae_gnn < mae_mean, f"GNN {mae_gnn:.3f} should beat predict-the-mean {mae_mean:.3f}"
