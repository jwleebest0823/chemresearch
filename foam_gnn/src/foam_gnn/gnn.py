"""
foam_gnn.gnn
============
The **encode–process–decode message-passing GNN** for per-bubble coarsening-rate
prediction, plus the graph assembly it consumes. Imports ``torch`` at top level, so
(like :mod:`foam_gnn.nn_models`) this module is NOT imported by the base package —
import it only where the optional ML extra is installed.

Architecture (per the approved design)
--------------------------------------
* **encode**   node/edge MLPs -> hidden width ``ModelConfig.hidden_dim`` (32–64).
* **process**  ``ModelConfig.n_mp_layers`` (2–3) message-passing steps with residual
  updates. Each step: message = MLP([x_i, x_j, e_ij]) -> sum-aggregate -> node update.
* **decode**   node MLP -> a single scalar per bubble (the target).

Small-data discipline baked in (# DECISION)
-------------------------------------------
* **No absolute position.** Node features are ``area``, ``n_sides``,
  ``distance_to_evap_edge`` only; edge features are *relative* geometry (contact-line
  length, squeezing strain, edge distance-to-edge, and the neighbour's log-area ratio).
  A model that never sees ``(cx, cy)`` cannot memorise "this bubble at this spot", which
  is the dominant overfitting mode with ~10^2 bubbles.
* **Isotropy / augmentation.** Because no absolute position or angle enters the
  features, the model is *already* invariant to rotation and reflection — the
  augmentation the design asks for is satisfied by construction rather than by sampling
  transformed copies. :func:`augment_graph` still provides feature-noise jitter for
  regularisation, and the invariance is asserted in the tests.
* **Heavy regularisation**: dropout, weight decay, early stopping on a held-out set of
  whole bubbles, and seed ensembling.

Shapes
------
``x`` ``(N, F_node)`` float32; ``edge_index`` ``(2, E)`` long (both directions stored);
``edge_attr`` ``(E, F_edge)`` float32; ``y`` ``(N,)`` float32; ``mask`` ``(N,)`` bool
marking nodes that have a target (only trusted bubbles do).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

__all__ = [
    "NODE_FEATURES_GNN",
    "EDGE_FEATURES_GNN",
    "FrameGraph",
    "build_frame_graphs",
    "augment_graph",
    "FoamGNN",
    "train_gnn_ensemble",
]

# DECISION: NO absolute position (cx, cy) — isotropy + anti-memorisation. These mirror
# foam_gnn.modeling.FEATURE_COLUMNS so the GNN and the MLP see the same node evidence
# and the comparison isolates the effect of TOPOLOGY.
NODE_FEATURES_GNN = ("area", "n_sides", "distance_to_evap_edge")
EDGE_FEATURES_GNN = ("contact_line_length", "squeezing_strain",
                     "distance_to_evap_edge", "log_area_ratio")


@dataclass
class FrameGraph:
    """One frame's graph, restricted to nodes that carry a prediction target."""

    x: np.ndarray            # (N, F_node)
    edge_index: np.ndarray   # (2, E)
    edge_attr: np.ndarray    # (E, F_edge)
    y: np.ndarray            # (N,)
    mask: np.ndarray         # (N,) bool — True where y is defined
    bubble_uid: list[str]
    foam: str
    session: str
    frame: int


def build_frame_graphs(
    trusted: "object",
    samples: "object",
    adjacency: dict[tuple[str, int], list[tuple[int, int, float, float, float]]],
) -> list[FrameGraph]:
    """Assemble per-frame graphs from the trusted table + horizon samples + adjacency.

    Parameters
    ----------
    trusted : tidy trusted-frame table (``foam_gnn.modeling.TRUSTED_COLUMNS``).
    samples : horizon samples (``foam_gnn.modeling.make_horizon_samples``) supplying the
        per-(session, frame, bubble) target ``target_dadt``.
    adjacency : ``{(session, frame): [(bubble_id_i, bubble_id_j, contact_len,
        squeeze, edge_dist), ...]}`` — the graph topology for that frame.

    Returns
    -------
    list[FrameGraph]
        One graph per (session, frame) that has at least one node with a target.
        Nodes are ALL trusted bubbles present in the frame (so a bubble without a target
        still passes messages); ``mask`` marks the ones that are scored.
    """
    tgt = {}
    for r in samples.itertuples():
        tgt[(r.session, int(r.frame), r.bubble_uid)] = float(r.target_dadt)

    out: list[FrameGraph] = []
    for (session, frame), g in trusted.groupby(["session", "frame"]):
        g = g.reset_index(drop=True)
        uid = list(g["bubble_uid"])
        bid_to_row = {int(b): i for i, b in enumerate(g["bubble_id"])}
        x = np.stack([g["area"].to_numpy(dtype=float),
                      g["n_sides"].to_numpy(dtype=float),
                      g["distance_to_evap_edge"].to_numpy(dtype=float)], axis=1)
        y = np.array([tgt.get((session, int(frame), u), np.nan) for u in uid], dtype=float)
        mask = np.isfinite(y)
        if not mask.any():
            continue
        src, dst, eat = [], [], []
        for (i, j, clen, squeeze, edist) in adjacency.get((session, int(frame)), []):
            if i not in bid_to_row or j not in bid_to_row:
                continue
            a, b = bid_to_row[i], bid_to_row[j]
            ai, aj = x[a, 0], x[b, 0]
            lar = float(np.log(max(aj, 1.0) / max(ai, 1.0)))
            for (u, v, r) in ((a, b, lar), (b, a, -lar)):   # both directions
                src.append(u)
                dst.append(v)
                eat.append([float(clen), float(squeeze), float(edist), r])
        edge_index = (np.array([src, dst], dtype=np.int64) if src
                      else np.zeros((2, 0), dtype=np.int64))
        edge_attr = (np.array(eat, dtype=float) if eat
                     else np.zeros((0, len(EDGE_FEATURES_GNN)), dtype=float))
        out.append(FrameGraph(x=x, edge_index=edge_index, edge_attr=np.nan_to_num(edge_attr),
                              y=np.nan_to_num(y), mask=mask, bubble_uid=uid,
                              foam=str(g["foam"].iloc[0]), session=str(session),
                              frame=int(frame)))
    return out


def augment_graph(fg: FrameGraph, rng: np.random.Generator, noise: float = 0.02) -> FrameGraph:
    """Feature-jitter augmentation (multiplicative noise on the continuous features).

    Rotation/reflection augmentation is a NO-OP by construction here: no absolute
    position or angle is used as a feature, so every graph is already invariant to it
    (asserted in tests). What remains useful for a ~10^2-bubble dataset is mild feature
    noise, which is what this applies.
    """
    x = fg.x.copy()
    x[:, 0] *= (1.0 + noise * rng.standard_normal(x.shape[0]))          # area
    x[:, 2] *= (1.0 + noise * rng.standard_normal(x.shape[0]))          # distance
    ea = fg.edge_attr.copy()
    if ea.size:
        ea *= (1.0 + noise * rng.standard_normal(ea.shape))
    return FrameGraph(x=x, edge_index=fg.edge_index, edge_attr=ea, y=fg.y, mask=fg.mask,
                      bubble_uid=fg.bubble_uid, foam=fg.foam, session=fg.session,
                      frame=fg.frame)


def _mlp(i: int, h: int, o: int, dropout: float) -> nn.Sequential:
    return nn.Sequential(nn.Linear(i, h), nn.ReLU(), nn.Dropout(dropout), nn.Linear(h, o))


class FoamGNN(nn.Module):
    """Encode–process–decode message-passing GNN. ``(graph) -> (N,)`` predictions."""

    def __init__(self, n_node_feat: int, n_edge_feat: int, hidden: int = 64,
                 n_mp: int = 3, dropout: float = 0.3) -> None:
        super().__init__()
        if not 1 <= n_mp <= 8:
            raise ValueError(f"n_mp must be in [1, 8], got {n_mp}")
        self.node_enc = _mlp(n_node_feat, hidden, hidden, dropout)
        self.edge_enc = _mlp(n_edge_feat, hidden, hidden, dropout)
        self.msg = nn.ModuleList([_mlp(3 * hidden, hidden, hidden, dropout) for _ in range(n_mp)])
        self.upd = nn.ModuleList([_mlp(2 * hidden, hidden, hidden, dropout) for _ in range(n_mp)])
        self.dec = _mlp(hidden, hidden, 1, dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                edge_attr: torch.Tensor) -> torch.Tensor:
        h = self.node_enc(x)
        e = self.edge_enc(edge_attr) if edge_attr.numel() else \
            torch.zeros((0, h.shape[1]), dtype=h.dtype, device=h.device)
        for msg, upd in zip(self.msg, self.upd):
            if edge_index.numel():
                s, d = edge_index[0], edge_index[1]
                m = msg(torch.cat([h[s], h[d], e], dim=1))
                agg = torch.zeros_like(h).index_add_(0, d, m)     # sum aggregation
            else:
                agg = torch.zeros_like(h)
            h = h + upd(torch.cat([h, agg], dim=1))               # residual update
        return self.dec(h).squeeze(-1)


def _standardize_graphs(graphs: list[FrameGraph]):
    """Feature/target standardisation statistics from TRAIN graphs only (no leakage)."""
    X = np.concatenate([g.x for g in graphs], axis=0) if graphs else np.zeros((0, 3))
    E = np.concatenate([g.edge_attr for g in graphs], axis=0) if graphs else np.zeros((0, 4))
    Y = np.concatenate([g.y[g.mask] for g in graphs], axis=0) if graphs else np.zeros((0,))
    def ms(a, axis=0):
        mu = a.mean(axis=axis) if a.size else 0.0
        sd = a.std(axis=axis) if a.size else 1.0
        sd = np.where(np.asarray(sd) < 1e-9, 1.0, sd)
        return mu, sd
    return ms(X), ms(E), ms(Y)


def _to_tensors(g: FrameGraph, xs, es, ys):
    (xmu, xsd), (emu, esd), (ymu, ysd) = xs, es, ys
    x = torch.as_tensor((g.x - xmu) / xsd, dtype=torch.float32)
    ea = torch.as_tensor((g.edge_attr - emu) / esd, dtype=torch.float32) if g.edge_attr.size \
        else torch.zeros((0, len(EDGE_FEATURES_GNN)), dtype=torch.float32)
    ei = torch.as_tensor(g.edge_index, dtype=torch.long)
    y = torch.as_tensor((g.y - ymu) / ysd, dtype=torch.float32)
    m = torch.as_tensor(g.mask, dtype=torch.bool)
    return x, ei, ea, y, m


def train_gnn_ensemble(
    train_graphs: list[FrameGraph],
    val_graphs: list[FrameGraph],
    test_graphs: list[FrameGraph],
    *,
    hidden: int = 64, n_mp: int = 3, dropout: float = 0.3, lr: float = 1e-3,
    weight_decay: float = 1e-4, max_epochs: int = 300, patience: int = 30,
    n_seeds: int = 5, augment_noise: float = 0.02,
) -> dict:
    """Seed-ensemble training with bubble-level early stopping.

    Returns ``{"pred_test", "uid_test", "pred_train", "y_train", "val_mae"}`` with
    predictions in the ORIGINAL target units (px²/s).
    """
    if not train_graphs or not test_graphs:
        raise ValueError("need non-empty train and test graph lists")
    xs, es, ys = _standardize_graphs(train_graphs)
    (_ymu, _ysd) = ys
    tr = [_to_tensors(g, xs, es, ys) for g in train_graphs]
    va = [_to_tensors(g, xs, es, ys) for g in (val_graphs or train_graphs)]
    te = [_to_tensors(g, xs, es, ys) for g in test_graphs]

    preds, tr_preds, vmaes = [], [], []
    for seed in range(n_seeds):
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        model = FoamGNN(train_graphs[0].x.shape[1], len(EDGE_FEATURES_GNN),
                        hidden=hidden, n_mp=n_mp, dropout=dropout)
        opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        best, bad, best_state = float("inf"), 0, None
        for _ep in range(max_epochs):
            model.train()
            opt.zero_grad()
            loss = torch.zeros(())
            for g, (x, ei, ea, y, m) in zip(train_graphs, tr):
                if augment_noise > 0:
                    gg = augment_graph(g, rng, augment_noise)
                    x, ei, ea, y, m = _to_tensors(gg, xs, es, ys)
                p = model(x, ei, ea)
                if m.any():
                    loss = loss + torch.mean((p[m] - y[m]) ** 2)
            loss.backward()
            opt.step()
            model.eval()
            with torch.no_grad():
                num = den = 0.0
                for (x, ei, ea, y, m) in va:
                    if not m.any():
                        continue
                    p = model(x, ei, ea)
                    num += float(torch.abs(p[m] - y[m]).sum())
                    den += int(m.sum())
                vmae = num / den if den else float("inf")
            if vmae < best - 1e-6:
                best, bad = vmae, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        if best_state is not None:
            model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            preds.append(np.concatenate([model(x, ei, ea)[m].numpy()
                                         for (x, ei, ea, _y, m) in te if m.any()]))
            tr_preds.append(np.concatenate([model(x, ei, ea)[m].numpy()
                                            for (x, ei, ea, _y, m) in tr if m.any()]))
        vmaes.append(best)

    ymu, ysd = ys
    uid_test = [u for g in test_graphs for u, k in zip(g.bubble_uid, g.mask) if k]
    y_train = np.concatenate([g.y[g.mask] for g in train_graphs if g.mask.any()])
    return {"pred_test": np.mean(preds, axis=0) * ysd + ymu,
            "uid_test": uid_test,
            "pred_train": np.mean(tr_preds, axis=0) * ysd + ymu,
            "y_train": y_train,
            "val_mae": float(np.mean(vmaes))}
