"""
foam_gnn.nn_models
==================
Optional **torch** models for the modeling stage. This module imports ``torch`` at
top level and is therefore NOT imported by the base package — import it only from
code paths that have the optional ML extra installed (mirrors the lazy split used
by :func:`foam_gnn.graph.graph_to_pyg`).

Stage-3 contents
----------------
* :class:`MLP` — a small, heavily-regularized no-graph regressor on per-bubble
  features (the graph-free control the GNN must beat).
* :func:`train_mlp_ensemble` — seed-ensemble training with bubble-level early
  stopping; returns predictions in the **same scale** as the ``y`` passed in.

Assumptions / small-data discipline
-----------------------------------
* Inputs are already standardized by the caller using **train-fold** statistics
  (no leakage). Predictions are returned in the (standardized) ``y`` scale the
  caller supplied; the caller inverts.
* No absolute-position features (isotropy) — enforced upstream in
  :data:`foam_gnn.modeling.FEATURE_COLUMNS`.
* Heavy regularization (dropout + weight decay) and early stopping on a held-out
  set of **whole bubbles** are the defense against overfitting on a few-hundred-
  bubble dataset. Seed ensembling reduces initialization variance.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn

__all__ = ["MLP", "train_mlp_ensemble"]


class MLP(nn.Module):
    """2-hidden-layer MLP regressor (ReLU + dropout). Shapes: (N, in) -> (N,)."""

    def __init__(self, in_dim: int, hidden: int = 64, dropout: float = 0.3) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (N, in) -> (N,)
        return self.net(x).squeeze(-1)


def _train_one(
    Xtr, ytr, Xva, yva, *, in_dim, hidden, dropout, lr, weight_decay,
    max_epochs, patience, seed,
):
    """Train one MLP with early stopping on (Xva, yva) val MAE; return best model."""
    torch.manual_seed(seed)
    model = MLP(in_dim, hidden, dropout)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    lossf = nn.MSELoss()
    Xtr_t, ytr_t = torch.as_tensor(Xtr, dtype=torch.float32), torch.as_tensor(ytr, dtype=torch.float32)
    Xva_t, yva_t = torch.as_tensor(Xva, dtype=torch.float32), torch.as_tensor(yva, dtype=torch.float32)
    best_state, best_val, bad = None, float("inf"), 0
    for _ in range(max_epochs):
        model.train()
        opt.zero_grad()
        loss = lossf(model(Xtr_t), ytr_t)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            vmae = float(torch.mean(torch.abs(model(Xva_t) - yva_t)))
        if vmae < best_val - 1e-6:
            best_val, bad = vmae, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, best_val


def train_mlp_ensemble(
    Xtr: np.ndarray, ytr: np.ndarray,
    Xva: np.ndarray, yva: np.ndarray,
    Xte: np.ndarray,
    *,
    hidden: int = 64, dropout: float = 0.3, lr: float = 1e-3,
    weight_decay: float = 1e-4, max_epochs: int = 500, patience: int = 30,
    n_seeds: int = 5,
) -> dict:
    """Train a seed ensemble; return mean predictions (same scale as ``y``).

    Returns ``{"pred_test", "pred_train", "val_mae"}`` where ``pred_*`` are the
    ensemble-mean predictions on ``Xte`` / ``Xtr``. ``pred_train`` supports the
    train-vs-held-out overfitting-gap check.
    """
    in_dim = Xtr.shape[1]
    preds_te, preds_tr, vmaes = [], [], []
    for s in range(n_seeds):
        model, vmae = _train_one(
            Xtr, ytr, Xva, yva, in_dim=in_dim, hidden=hidden, dropout=dropout,
            lr=lr, weight_decay=weight_decay, max_epochs=max_epochs,
            patience=patience, seed=s)
        with torch.no_grad():
            preds_te.append(model(torch.as_tensor(Xte, dtype=torch.float32)).numpy())
            preds_tr.append(model(torch.as_tensor(Xtr, dtype=torch.float32)).numpy())
        vmaes.append(vmae)
    return {"pred_test": np.mean(preds_te, axis=0),
            "pred_train": np.mean(preds_tr, axis=0),
            "val_mae": float(np.mean(vmaes))}
