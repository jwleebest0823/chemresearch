"""Smoke tests for foam_gnn.nn_models (optional torch extra).

Skipped entirely when torch is absent so the base test suite never requires the ML
stack. Verifies the ensemble trains and LEARNS a clear synthetic signal (a sanity
check that the precondition harness would detect real structure if it existed).
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from foam_gnn.nn_models import train_mlp_ensemble  # noqa: E402


def test_mlp_learns_linear_signal():
    rng = np.random.default_rng(0)
    n = 400
    X = rng.normal(0, 1, size=(n, 3))
    y = 2.0 * X[:, 0] - 1.0 * X[:, 1]                  # clean linear signal
    tr, va, te = slice(0, 240), slice(240, 320), slice(320, n)
    out = train_mlp_ensemble(X[tr], y[tr], X[va], y[va], X[te],
                             hidden=32, dropout=0.0, n_seeds=2, max_epochs=400, patience=40)
    pred = out["pred_test"]
    # MLP must beat predicting the train mean on a signal this clean
    mae_mlp = float(np.mean(np.abs(pred - y[te])))
    mae_mean = float(np.mean(np.abs(y[tr].mean() - y[te])))
    assert mae_mlp < 0.5 * mae_mean
    assert np.corrcoef(pred, y[te])[0, 1] > 0.9


def test_mlp_predicts_near_mean_on_pure_noise():
    rng = np.random.default_rng(1)
    n = 300
    X = rng.normal(0, 1, size=(n, 3))
    y = rng.normal(5.0, 1.0, size=n)                  # no relation to X, mean 5
    tr, va, te = slice(0, 180), slice(180, 240), slice(240, n)
    out = train_mlp_ensemble(X[tr], y[tr], X[va], y[va], X[te],
                             hidden=32, dropout=0.3, n_seeds=3, max_epochs=300, patience=30)
    # with no signal, predictions should collapse toward the (train) mean ~5
    assert abs(float(np.mean(out["pred_test"])) - 5.0) < 1.0
