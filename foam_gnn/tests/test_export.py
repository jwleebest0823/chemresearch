"""
Smoke + correctness tests for the CSV export (long/tidy nodes + edges).

Builds tiny synthetic segmentation frames, runs the REAL Module-2
``track_sequence`` on them (so stable IDs / events are genuine), then exports.
Verifies: long-format handling of disappearance (no rows after last frame), the
disappear-vs-coalesce classifier, event placement on the final frame, schema, and
the fail-loud validator.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage as ndi

from foam_gnn.config import PipelineConfig
from foam_gnn.segmentation import SegmentationResult
from foam_gnn.tracking import track_sequence
from foam_gnn.export_csv import (
    EDGE_COLUMNS,
    NODE_COLUMNS,
    _validate,
    classify_deaths,
    export_session,
    write_readme,
    write_session_csvs,
)


def _seg(labels: np.ndarray) -> SegmentationResult:
    labels = labels.astype(np.int32)
    foam = ndi.binary_fill_holes(labels > 0)
    dist = ndi.distance_transform_edt(foam).astype(np.float32)
    return SegmentationResult(labels, foam, dist, int(labels.max()))


def _coalesce_frames() -> list[SegmentationResult]:
    """3 static frames where small bubble 2 is absorbed by big neighbour 1 at t=2.

    Foam rect rows 8-31, cols 8-31. B=1 (left), C=2 (small top-right), E=3
    (bottom-right). At frame 2, C's footprint becomes part of B (B grows).
    """
    def frame(merged: bool) -> np.ndarray:
        a = np.zeros((40, 40), np.int32)
        a[8:32, 8:24] = 1                 # B
        a[16:32, 24:32] = 3               # E
        a[8:16, 24:32] = 1 if merged else 2   # C absorbed by B when merged
        return a
    return [_seg(frame(False)), _seg(frame(False)), _seg(frame(True))]


def test_classify_deaths_coalesce():
    results = _coalesce_frames()
    cfg = PipelineConfig()
    tr = track_sequence(results, cfg)
    deaths = classify_deaths(results, tr, cfg)
    # merge_id_rule="max": the merged region inherits max(1, 2) = 2, so bubble 1
    # (last seen frame 1) is the one that coalesces INTO survivor 2 — no new ID.
    assert (1, 1) in deaths, deaths
    assert deaths[(1, 1)]["event"] == "coalesce"
    assert deaths[(1, 1)]["absorber_id"] == 2
    assert deaths[(1, 1)]["event_confidence"] in {"low", "medium"}


def test_classify_deaths_pure_disappear():
    """A bubble whose footprint becomes background (not absorbed) -> 'disappear'."""
    def frame(present: bool) -> np.ndarray:
        a = np.zeros((30, 30), np.int32)
        a[5:25, 5:15] = 1
        if present:
            a[5:15, 16:24] = 2            # isolated bubble, 1-px gap from bubble 1
        return a
    results = [_seg(frame(True)), _seg(frame(True)), _seg(frame(False))]
    cfg = PipelineConfig()
    tr = track_sequence(results, cfg)
    deaths = classify_deaths(results, tr, cfg)
    assert (1, 2) in deaths
    assert deaths[(1, 2)]["event"] == "disappear"
    assert deaths[(1, 2)]["absorber_id"] is None


def test_export_session_longformat_and_schema():
    results = _coalesce_frames()
    cfg = PipelineConfig()
    tr = track_sequence(results, cfg)
    nodes, edges = export_session(results, tr, cfg, foam="A", session="syn")

    assert list(nodes.columns) == NODE_COLUMNS
    assert list(edges.columns) == EDGE_COLUMNS
    # long format under max rule: bubble 1 merges into survivor 2, so bubble 1 is
    # present at frames 0,1 but NOT frame 2; survivor 2 persists.
    f2 = set(nodes[nodes["frame"] == 2]["bubble_id"])
    assert 1 not in f2
    assert {2, 3}.issubset(f2)
    # event marked only on bubble 1's final frame (frame 1); survivor 2 has none
    row = nodes[(nodes["frame"] == 1) & (nodes["bubble_id"] == 1)]
    assert row["event"].iloc[0] == "coalesce"
    assert (nodes[nodes["bubble_id"] == 2]["event"] == "").all()
    # edges are undirected & ordered i<j, positive contact length
    assert (edges["bubble_id_i"] < edges["bubble_id_j"]).all()
    assert (edges["contact_line_length"] > 0).all()
    # session/foam stamped
    assert set(nodes["foam"]) == {"A"} and set(nodes["session"]) == {"syn"}


def test_time_seconds_from_timestamps():
    from datetime import datetime, timedelta
    results = _coalesce_frames()
    cfg = PipelineConfig()
    tr = track_sequence(results, cfg)
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    ts = [t0 + timedelta(seconds=30 * i) for i in range(len(results))]
    nodes, _ = export_session(results, tr, cfg, foam="A", session="syn", timestamps=ts)
    assert sorted(nodes["time_seconds"].unique().tolist()) == [0.0, 30.0, 60.0]


def test_validate_rejects_inf():
    import pandas as pd
    row = {c: 0.0 for c in NODE_COLUMNS}
    row.update(bubble_id=1, event="", event_confidence="",
               foam="A", session="syn", distance_to_evap_edge=np.inf)
    bad = pd.DataFrame([row], columns=NODE_COLUMNS)
    with pytest.raises(ValueError):
        _validate(bad, pd.DataFrame(columns=EDGE_COLUMNS))


_DATA = Path(__file__).resolve().parents[1] / "data"
_HAS_DATA = _DATA.is_dir() and (_DATA / "exp1").is_dir()


@pytest.mark.skipif(not _HAS_DATA, reason="raw data/ not present (gitignored)")
def test_real_frames_smoke_foam_a():
    """End-to-end on 3 consecutive real Foam-A frames: segment -> track -> export."""
    from foam_gnn.dataset import experiment_timestamps, contiguous_runs
    from foam_gnn.io_utils import load_experiment_frames
    from foam_gnn.segmentation import build_segmenter

    cfg = PipelineConfig()
    ts = experiment_timestamps("data", "exp1")
    a, b = contiguous_runs(ts)[0]
    idx = list(range(a, a + 3))
    _, imgs = load_experiment_frames("data", "exp1", indices=idx)
    seg = build_segmenter(cfg)
    results = [seg.segment(im) for im in imgs]
    tr = track_sequence(results, cfg)
    nodes, edges = export_session(results, tr, cfg, foam="A", session="exp1",
                                  timestamps=[ts[i] for i in idx])
    assert list(nodes.columns) == NODE_COLUMNS
    assert list(edges.columns) == EDGE_COLUMNS
    assert len(nodes) > 50 and len(edges) > 50           # a dense real foam frame
    assert nodes["n_sides"].max() >= 3                    # interior bubbles are 3+-sided
    assert (edges["contact_line_length"] > 0).all()
    assert set(nodes["event"].unique()).issubset({"", "disappear", "coalesce"})


def test_write_csvs_and_readme(tmp_path):
    results = _coalesce_frames()
    cfg = PipelineConfig()
    tr = track_sequence(results, cfg)
    nodes, edges = export_session(results, tr, cfg, foam="A", session="syn")
    np_path, ep_path = write_session_csvs(tmp_path, nodes, edges)
    readme = write_readme(tmp_path)
    assert np_path.is_file() and ep_path.is_file() and readme.is_file()
    assert "PRELIMINARY" in readme.read_text(encoding="utf-8")
