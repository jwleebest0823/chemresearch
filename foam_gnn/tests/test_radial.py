"""
Tests for foam_gnn.radial — the radial-gradient hypothesis test.

Synthetic trusted sets with a KNOWN implanted gradient (recovered) and flat data
(null with CI covering 0), plus a von Neumann K recovery. All statistics come with
cluster-bootstrap CIs.
"""
from __future__ import annotations

import pandas as pd

from foam_gnn.config import PipelineConfig
from foam_gnn.radial import radial_gradient_test, segment_rates

_COLS = ["frame", "time_seconds", "bubble_id", "area", "n_sides",
         "distance_to_evap_edge", "cx", "cy", "segment_id"]


def _build(bubbles):
    """bubbles: list of dict(bubble_id, dist, areas, n_sides(list|int)). One segment each."""
    rows, segs = [], []
    for sid, b in enumerate(bubbles):
        areas = b["areas"]
        ns = b["n_sides"] if isinstance(b["n_sides"], list) else [b["n_sides"]] * len(areas)
        for f, (a, n) in enumerate(zip(areas, ns)):
            rows.append({"frame": f, "time_seconds": float(f * 30), "bubble_id": b["bubble_id"],
                         "area": float(a), "n_sides": int(n), "distance_to_evap_edge": float(b["dist"]),
                         "cx": 500.0, "cy": 500.0, "segment_id": sid})
        segs.append({"segment_id": sid, "bubble_id": b["bubble_id"], "dist_mid": float(b["dist"])})
    return pd.DataFrame(rows, columns=_COLS), pd.DataFrame(segs)


def test_recovers_implanted_negative_gradient():
    # rate decreases with distance → Spearman(dist, rate) strongly negative
    bubbles = [{"bubble_id": i + 1, "dist": 5.0 * i,
                "areas": [1000 + (-0.05 * 5.0 * i) * (30 * f) for f in range(6)],
                "n_sides": 6} for i in range(40)]
    tr, seg = _build(bubbles)
    res = radial_gradient_test(tr, seg, PipelineConfig())
    assert res.spearman_rho < -0.5
    assert res.spearman_ci[1] < 0                      # CI excludes 0 (gradient present)


def test_flat_is_null_ci_covers_zero():
    # slope uncorrelated with distance → Spearman ~0, CI covers 0
    bubbles = [{"bubble_id": i + 1, "dist": 5.0 * i,
                "areas": [1000 + (((i * 37) % 11) - 5) * (30 * f) for f in range(6)],
                "n_sides": 6} for i in range(40)]
    tr, seg = _build(bubbles)
    res = radial_gradient_test(tr, seg, PipelineConfig())
    assert res.spearman_ci[0] < 0 < res.spearman_ci[1]  # CI covers 0
    assert res.decision == "null"


def test_von_neumann_K_recovered():
    # implant dA/dt = K*(n-6) with K=2, all at one distance → K_by_bin K ≈ 2
    K = 2.0
    dt = 30.0
    ncycle = [4, 5, 7, 8, 3, 9]
    bubbles = []
    for i in range(8):
        areas = [1000.0]
        for f in range(1, 6):
            n_prev = ncycle[(i + f - 1) % len(ncycle)]
            areas.append(areas[-1] + K * (n_prev - 6) * dt)
        ns = [ncycle[(i + f) % len(ncycle)] for f in range(6)]
        bubbles.append({"bubble_id": i + 1, "dist": 100.0, "areas": areas, "n_sides": ns})
    tr, seg = _build(bubbles)
    res = radial_gradient_test(tr, seg, PipelineConfig())
    kb = res.K_by_bin
    occupied = kb[kb["n_intervals"] > 0]
    assert len(occupied) >= 1
    assert abs(float(occupied["K"].iloc[occupied["n_intervals"].argmax()]) - K) < 0.2


def test_segment_rates_ols_matches_slope():
    tr, seg = _build([{"bubble_id": 1, "dist": 50.0,
                       "areas": [100 + 10 * f for f in range(6)], "n_sides": 6}])
    rr = segment_rates(tr, seg)
    # dA/dt = 10 px² per 30 s = 1/3 px²/s
    assert abs(float(rr["dA_dt_ols"].iloc[0]) - (10.0 / 30.0)) < 1e-9
