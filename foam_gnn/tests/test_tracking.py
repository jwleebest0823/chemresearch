"""
Smoke tests for MODULE 2 (tracking).

Tests the full track_sequence() pipeline on the 5 sample frames:
  - output contract (shapes, dtypes, column names)
  - stable ID persistence across frames
  - event detection (T2 disappearances for a coarsening foam, births, T1)
  - edge cases (empty sequence, single frame)
  - summarize_events helper

These are smoke / contract tests, not scientific validation of tracking quality.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.segmentation import SegmentationResult
from foam_gnn.tracking import (
    TopologicalEvent,
    TrackingResult,
    summarize_events,
    track_sequence,
)

_VALID_KINDS = {"T2_disappear", "birth", "T1_swap"}
_CORR_COLS = {"frame", "bubble_id", "label_in_frame", "area_px", "cx", "cy"}


# ──────────────────────── session-scoped tracking ─────────────────────────── #

@pytest.fixture(scope="session")
def tracking(results, cfg):
    return track_sequence(results, cfg)


# ──────────────────────── contract tests ──────────────────────────────────── #

def test_track_result_type(tracking):
    assert isinstance(tracking, TrackingResult)


def test_id_maps_count(tracking, results):
    assert len(tracking.id_maps) == len(results)


def test_id_maps_shape_dtype(tracking, results):
    for id_map, res in zip(tracking.id_maps, results):
        assert id_map.shape == (1024, 1280)
        assert id_map.dtype == np.int32
        assert id_map.min() >= 0


def test_id_maps_background_zero(tracking):
    for id_map in tracking.id_maps:
        # background label in original segmentation (0) must stay 0
        assert 0 in np.unique(id_map)


def test_n_tracks_positive(tracking, results):
    # must have at least as many tracks as bubbles in the largest frame
    max_bubbles = max(r.n_bubbles for r in results)
    assert tracking.n_tracks >= max_bubbles


def test_id_count_per_frame_matches_n_bubbles(tracking, results):
    for id_map, res in zip(tracking.id_maps, results):
        n_ids = int((id_map > 0).max())   # at least one positive id exists
        # the number of unique positive IDs ≥ 1 (frame has bubbles)
        n_unique = len(np.unique(id_map[id_map > 0]))
        assert n_unique == res.n_bubbles, (
            f"id_map has {n_unique} unique positive IDs but seg has {res.n_bubbles} bubbles"
        )


# ──────────────────────── ID stability ────────────────────────────────────── #

def test_stable_ids_persist_across_frames(tracking, results):
    """Some IDs must be reused across multiple frames (tracker is doing something).

    The 5 sample frames are sparse (not temporally consecutive), so per-pair
    overlap can be low. We test the weaker property that at least N distinct
    bubble IDs appear in more than one frame — i.e., the tracker is not
    issuing a fresh ID for every bubble in every frame.
    """
    corr = tracking.correspondence
    id_frame_counts = corr.groupby("bubble_id")["frame"].nunique()
    reused = int((id_frame_counts > 1).sum())
    assert reused >= 10, (
        f"only {reused} IDs appear in more than one frame — tracker may not be matching"
    )


def test_frame0_ids_start_at_1(tracking, results):
    """Frame-0 IDs are assigned 1..n_bubbles with no gaps."""
    ids = np.unique(tracking.id_maps[0])
    ids = ids[ids > 0]
    assert ids.min() == 1
    assert set(ids) == set(range(1, results[0].n_bubbles + 1))


# ──────────────────────── events ──────────────────────────────────────────── #

def test_events_list_type(tracking):
    assert isinstance(tracking.events, list)
    for e in tracking.events:
        assert isinstance(e, TopologicalEvent)


def test_event_kinds_valid(tracking):
    for e in tracking.events:
        assert e.kind in _VALID_KINDS, f"unexpected event kind: {e.kind!r}"


def test_event_frames_in_range(tracking, results):
    for e in tracking.events:
        assert 0 < e.frame < len(results), f"event frame {e.frame} out of range"


def test_t2_events_exist(tracking):
    """Coarsening foam must produce T2 disappearances across 5 frames."""
    t2s = [e for e in tracking.events if e.kind == "T2_disappear"]
    assert len(t2s) > 0, "no T2 disappearance events detected across 5 coarsening frames"


def test_t2_matches_bubble_count_drop(tracking, results):
    """Net T2s between consecutive frames should explain most of the count decrease."""
    for t in range(1, len(results)):
        n_prev = results[t - 1].n_bubbles
        n_curr = results[t].n_bubbles
        if n_curr < n_prev:
            t2s = [e for e in tracking.events if e.frame == t and e.kind == "T2_disappear"]
            # T2s should be at least 1 (we can't expect exact match due to merges/births)
            assert len(t2s) >= 1, (
                f"frame {t}: bubble count dropped {n_prev}->{n_curr} but 0 T2 events"
            )


def test_events_sorted_by_frame(tracking):
    frames = [e.frame for e in tracking.events]
    assert frames == sorted(frames)


def test_event_bubble_ids_positive(tracking):
    for e in tracking.events:
        assert all(bid > 0 for bid in e.bubble_ids)


# ──────────────────────── correspondence table ────────────────────────────── #

def test_correspondence_is_dataframe(tracking):
    assert isinstance(tracking.correspondence, pd.DataFrame)


def test_correspondence_columns(tracking):
    assert _CORR_COLS.issubset(set(tracking.correspondence.columns))


def test_correspondence_row_count(tracking, results):
    """One row per (frame, bubble) — total rows = sum of bubble counts."""
    expected = sum(r.n_bubbles for r in results)
    assert len(tracking.correspondence) == expected


def test_correspondence_frame_values(tracking, results):
    frames_in_df = sorted(tracking.correspondence["frame"].unique())
    assert frames_in_df == list(range(len(results)))


def test_correspondence_bubble_ids_nonneg(tracking):
    assert (tracking.correspondence["bubble_id"] >= 0).all()


def test_correspondence_area_positive(tracking):
    assert (tracking.correspondence["area_px"] > 0).all()


# ──────────────────────── summarize_events ────────────────────────────────── #

def test_summarize_events_type(tracking):
    df = summarize_events(tracking)
    assert isinstance(df, pd.DataFrame)


def test_summarize_events_columns(tracking):
    df = summarize_events(tracking)
    assert {"frame", "kind", "bubble_ids"}.issubset(set(df.columns))


def test_summarize_events_row_count(tracking):
    df = summarize_events(tracking)
    assert len(df) == len(tracking.events)


# ──────────────────────── edge cases ──────────────────────────────────────── #

def test_empty_sequence(cfg):
    result = track_sequence([], cfg)
    assert isinstance(result, TrackingResult)
    assert result.id_maps == []
    assert result.events == []
    assert isinstance(result.correspondence, pd.DataFrame)
    assert result.n_tracks == 0


def test_single_frame(results, cfg):
    result = track_sequence([results[0]], cfg)
    assert len(result.id_maps) == 1
    assert result.events == []   # no inter-frame events for a single frame
    assert len(result.correspondence) == results[0].n_bubbles
