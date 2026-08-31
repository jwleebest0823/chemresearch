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
    fit_von_neumann,
    lofo_folds,
    make_horizon_samples,
    mae,
    predict_per_bubble_linear,
    predict_persistence,
    predict_von_neumann,
    residual_structure,
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


def test_von_neumann_recovers_implanted_K():
    # implant dA/dt = K*(n-6) exactly, K=0.7
    rng = np.random.default_rng(0)
    n = rng.integers(3, 10, size=400).astype(float)
    K_true = 0.7
    dadt = K_true * (n - 6.0)
    bub = rng.integers(0, 40, size=400)
    fit = fit_von_neumann(n, dadt, bubble_of=bub, n_boot=200)
    assert fit["K"] == pytest.approx(K_true, abs=1e-9)
    assert fit["r2_origin"] == pytest.approx(1.0, abs=1e-9)
    assert fit["K_ci"][0] > 0  # cleanly fittable (CI entirely positive)
    # free intercept ~0 for a pure through-origin law
    assert abs(fit["intercept_free"]) < 1e-6


def test_von_neumann_degenerate_and_negative_K():
    # pure noise -> K CI should straddle 0 (not cleanly fittable)
    rng = np.random.default_rng(1)
    n = rng.integers(3, 10, size=300).astype(float)
    dadt = rng.normal(0, 1, size=300)      # no relation to n
    bub = rng.integers(0, 30, size=300)
    fit = fit_von_neumann(n, dadt, bubble_of=bub, n_boot=300)
    assert fit["K_ci"][0] < 0 < fit["K_ci"][1]   # straddles 0


def test_residual_structure_detects_implanted_distance_dependence():
    # dA/dt = K(n-6) + slope*distance  -> residual should correlate with distance
    rng = np.random.default_rng(2)
    n = 200
    rows = []
    for b in range(20):
        for k in range(10):
            nn = rng.integers(3, 10)
            dist = rng.uniform(0, 100)
            dadt = 0.5 * (nn - 6) + 0.05 * dist   # distance term the law misses
            rows.append({"foam": "A", "session": "s", "seg_uid": f"s:{b}",
                         "bubble_uid": f"s:{b}", "frame": k, "horizon": 5,
                         "area_t": 2000.0, "time_t": 30.0 * k, "n_sides": float(nn),
                         "distance_to_evap_edge": dist, "target_dadt": dadt,
                         "target_frac": 0.0, "past_slope": np.nan})
    s = pd.DataFrame(rows)
    cfg = PipelineConfig()
    K = fit_von_neumann(s["n_sides"].to_numpy(), s["target_dadt"].to_numpy())["K"]
    rs = residual_structure(s, K, cfg)
    assert rs["distance_to_evap_edge"]["resolved"]        # CI excludes 0
    assert rs["distance_to_evap_edge"]["rho"] > 0.3
