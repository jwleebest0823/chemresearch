"""
Tests for foam_gnn.stability — the trusted-track filter + gates.

Synthetic node tables with KNOWN track structure verify: frame-0-origin
eligibility, persistence, area-continuity splitting, merge splitting, and that we
never threshold on instantaneous size. A lightweight TrackingResult carries only
the fields the filter reads (diagnostics.frame0_max_id, events).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.stability import (
    NODE_TABLE_COLUMNS,
    select_stable_tracks,
    stability_gates,
)
from foam_gnn.tracking import TopologicalEvent, TrackingResult


def _fake_tracking(frame0_max: int, events=None) -> TrackingResult:
    empty = pd.DataFrame(columns=["frame", "bubble_id"])
    tr = TrackingResult([], events or [], empty, 0)
    tr.diagnostics = {"frame0_max_id": frame0_max}
    return tr


def _rows(bid, frames, areas, dist=100.0, n_sides=6, cx=500.0, cy=500.0):
    return [{"frame": f, "time_seconds": float(f * 30), "bubble_id": bid,
             "area": float(a), "n_sides": n_sides, "distance_to_evap_edge": dist,
             "cx": cx, "cy": cy} for f, a in zip(frames, areas)]


def _node_table(rowsets) -> pd.DataFrame:
    rows = [r for rs in rowsets for r in rs]
    return pd.DataFrame(rows, columns=NODE_TABLE_COLUMNS)


def test_frame0_origin_and_persistence():
    cfg = PipelineConfig()               # min_persist_frames=5, area_jump_tol=0.5
    nt = _node_table([
        _rows(1, range(10), [100] * 10),                 # stable 10-frame track → kept
        _rows(3, range(3), [100] * 3),                   # too short (3<5) → dropped
        _rows(100, range(10), [100] * 10),               # birth id > frame0_max → ineligible
    ])
    sel = select_stable_tracks(nt, _fake_tracking(frame0_max=50), cfg)
    assert set(sel.eligible_survival["bubble_id"]) == {1, 3}      # 100 excluded
    assert sel.stats["n_trusted_bubbles"] == 1                    # only bubble 1
    seg = sel.segments
    assert list(seg["bubble_id"]) == [1] and seg["n_frames"].iloc[0] == 10
    assert bool(sel.eligible_survival.set_index("bubble_id").loc[3, "survived"]) is False


def test_area_jump_splits_track():
    cfg = PipelineConfig()
    # continuous for 5 frames, then a 3x area jump (|Δlog|≈1.1 > 0.5), then 5 more
    nt = _node_table([_rows(1, range(10), [100] * 5 + [300] * 5)])
    sel = select_stable_tracks(nt, _fake_tracking(50), cfg)
    assert len(sel.segments) == 2                                 # split at the jump
    assert list(sel.segments["n_frames"]) == [5, 5]


def test_merge_splits_track():
    cfg = PipelineConfig()
    ev = [TopologicalEvent(5, "merge", (1, 2), {"survivor": 2, "merged_ids": (1,)})]
    nt = _node_table([_rows(2, range(10), [100] * 10)])          # survivor 2, continuous area
    sel = select_stable_tracks(nt, _fake_tracking(50, ev), cfg)
    # a merge at frame 5 breaks the track even though area is continuous here
    assert len(sel.segments) == 2
    assert set(sel.segments["end_frame"]) == {4, 9}


def test_small_bubbles_not_size_filtered():
    """A small but stable bubble is KEPT (persistence, not size)."""
    cfg = PipelineConfig()
    nt = _node_table([_rows(1, range(8), [12] * 8)])            # tiny area, stable
    sel = select_stable_tracks(nt, _fake_tracking(50), cfg)
    assert sel.stats["n_trusted_bubbles"] == 1


def test_area_and_count_fractions_reported():
    cfg = PipelineConfig()
    nt = _node_table([
        _rows(1, range(10), [1000] * 10),                        # big stable → kept
        _rows(2, range(2), [50] * 2),                            # small short → dropped
    ])
    sel = select_stable_tracks(nt, _fake_tracking(50), cfg)
    # 1 of 2 bubbles kept, but nearly all AREA kept (the "30% count, 85% area" fact)
    assert sel.stats["frac_bubbles_trusted"] == 0.5
    assert sel.stats["frac_area_trusted"] > 0.9


def test_guards_reject_bad_table():
    cfg = PipelineConfig()
    bad = pd.DataFrame({"frame": [0]})                          # missing columns
    with pytest.raises(ValueError):
        select_stable_tracks(bad, _fake_tracking(50), cfg)


def test_survival_confound_gate_flags_correlation():
    """If near-edge (small dist) bubbles systematically fail to survive, the gate
    flags a confound (Condition 1)."""
    cfg = PipelineConfig()
    rowsets = []
    # near-edge bubbles (dist small) are short-lived → dropped; interior survive
    for b in range(1, 21):
        dist = float(b * 10)                                    # 10..200
        length = 2 if dist < 100 else 8                         # near-edge die young
        rowsets.append(_rows(b, range(length), [100] * length, dist=dist))
    sel = select_stable_tracks(_node_table(rowsets), _fake_tracking(50), cfg)
    gates = stability_gates(sel, cfg)
    assert np.isfinite(gates["survival_distance_rho"])
    assert gates["confounded"] is True                          # survival ↑ with distance
    assert gates["decision"] == "confounded"
