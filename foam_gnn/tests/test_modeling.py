"""Unit tests for foam_gnn.modeling (Stage-1 primitives) on synthetic trusted data.

Synthetic control: two foams, bubbles with KNOWN linear area trajectories, so the
target dA/dt and the per-bubble-linear baseline are analytically checkable and the
horizon partnering / LOFO / quiescent-split logic is verified without segmentation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.modeling import (
    TRUSTED_COLUMNS,
    evaluate_baselines,
    lofo_folds,
    make_horizon_samples,
    mae,
    predict_per_bubble_linear,
    predict_persistence,
    segment_dynamic_flags,
    target_distribution,
)

DT = 30.0  # seconds per frame


def _bubble(foam, session, bid, n_frames, area0, slope_per_s):
    """One trusted segment with area = area0 + slope*t (linear, gap-free)."""
    rows = []
    for f in range(n_frames):
        t = f * DT
        rows.append({
            "foam": foam, "session": session, "seg_uid": f"{session}:{bid}",
            "bubble_uid": f"{session}:{bid}", "segment_id": bid, "bubble_id": bid,
            "frame": f, "time_seconds": t, "area": area0 + slope_per_s * t,
            "n_sides": 6, "distance_to_evap_edge": 50.0, "cx": 10.0, "cy": 10.0,
        })
    return rows


def _synthetic() -> pd.DataFrame:
    rows = []
    # Foam A: one shrinking bubble (dynamic), one flat (quiescent)
    rows += _bubble("A", "expA", 1, 25, 3000.0, -0.5)     # dA/dt = -0.5 px^2/s
    rows += _bubble("A", "expA", 2, 25, 3000.0, 0.0)      # flat
    # Foam C: one growing bubble (dynamic), one flat (quiescent)
    rows += _bubble("C", "expC", 1, 25, 2000.0, +0.4)
    rows += _bubble("C", "expC", 2, 25, 2000.0, 0.0)
    return pd.DataFrame(rows)[TRUSTED_COLUMNS]


def test_target_dadt_and_partnering():
    df = _synthetic()
    s = make_horizon_samples(df, horizon=5)
    # each 25-frame segment yields 20 horizon-5 samples
    assert (s["seg_uid"].value_counts() == 20).all()
    # shrinking bubble: target_dadt == -0.5 exactly (linear)
    sh = s[s["seg_uid"] == "expA:1"]
    assert np.allclose(sh["target_dadt"], -0.5)
    # target_frac = ΔA/A over 5 frames = (-0.5*150)/area_t
    assert np.allclose(sh["target_frac"], (-0.5 * 5 * DT) / sh["area_t"])


def test_per_bubble_linear_recovers_slope():
    df = _synthetic()
    s = make_horizon_samples(df, horizon=1)
    pred = predict_per_bubble_linear(s)
    # first frame of each segment has no past slope -> falls back to 0
    first = s.groupby("seg_uid")["frame"].transform("min") == s["frame"]
    assert np.allclose(pred[first.to_numpy()], 0.0)
    # elsewhere it recovers the true slope (exactly, linear data)
    sh = (s["seg_uid"] == "expA:1") & ~first
    assert np.allclose(pred[sh.to_numpy()], -0.5)


def test_persistence_is_zero_and_mae():
    df = _synthetic()
    s = make_horizon_samples(df, horizon=5)
    assert np.all(predict_persistence(s) == 0.0)
    # MAE of persistence == mean|target|
    assert mae(predict_persistence(s), s["target_dadt"].to_numpy()) == pytest.approx(
        np.mean(np.abs(s["target_dadt"])))


def test_dynamic_quiescent_split():
    df = _synthetic()
    cfg = PipelineConfig()
    seg = segment_dynamic_flags(df, cfg)
    flags = seg.set_index("seg_uid")["dynamic"].to_dict()
    assert flags["expA:1"] and flags["expC:1"]         # sloped -> dynamic
    assert not flags["expA:2"] and not flags["expC:2"]  # flat -> quiescent


def test_lofo_folds_disjoint():
    df = _synthetic()
    folds = lofo_folds(df)
    assert {f["test_foam"] for f in folds} == {"A", "C"}
    for f in folds:
        assert f["test_foam"] not in f["train_foams"]


def test_evaluate_baselines_shape_and_persistence_dynamic():
    df = _synthetic()
    cfg = PipelineConfig()
    res = evaluate_baselines(df, cfg)
    # persistence MAE on the DYNAMIC subset must be > 0 (it ignores real change)
    dyn = res[(res["subset"] == "dynamic") & (res["method"] == "persistence")]
    assert (dyn["mae"] > 0).all()
    # on quiescent (flat) bubbles persistence is ~perfect
    qui = res[(res["subset"] == "quiescent") & (res["method"] == "persistence")]
    assert np.allclose(qui["mae"], 0.0)


def test_target_distribution_monotone_horizon():
    df = _synthetic()
    cfg = PipelineConfig()
    td = target_distribution(df, cfg).set_index("scope")
    # fractional change grows with horizon (linear data, non-decreasing)
    assert td.loc["h=1", "median_abs_frac"] <= td.loc["h=5", "median_abs_frac"]
