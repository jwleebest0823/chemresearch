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

_VALID_KINDS = {"T2_disappear", "birth", "T1_swap", "merge"}
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
        # each segmentation region must carry exactly one unique positive stable ID
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


# ──────────────────────── B1: T1 detection (deterministic) ─────────────────── #
# These are real correctness tests on synthetic label maps with a KNOWN swap,
# not plumbing checks on sparse frames.

from foam_gnn.tracking import (  # noqa: E402
    _adjacency_lengths, _detect_t1_between, overlay_ids, overlay_events,
)


def _canonical_t1_pair():
    """Two 20x20 stable-ID maps encoding one textbook T1.

    Before: P(1)|Q(2) share the central vertical film; S(4) top band and R(3)
    bottom band each border both P and Q. After: P-Q gone, R-S share the central
    horizontal film; the four ring edges persist.
    """
    H = W = 20
    t = np.zeros((H, W), np.int32)
    t[:, :10] = 1   # P (left)
    t[:, 10:] = 2   # Q (right) — shares the central vertical film with P
    t[:3, :] = 4    # S (top band) borders both P and Q
    t[17:, :] = 3   # R (bottom band) borders both P and Q
    t1 = np.zeros((H, W), np.int32)
    t1[:10, :] = 4  # S (top) — now shares the central horizontal film with R
    t1[10:, :] = 3  # R (bottom)
    t1[:, :3] = 1   # P (left band)
    t1[:, 17:] = 2  # Q (right band)
    return t, t1


def test_detect_single_localized_t1():
    t, t1 = _canonical_t1_pair()
    cent = {1: (2, 10), 2: (18, 10), 3: (10, 18), 4: (10, 2)}
    swaps = _detect_t1_between(_adjacency_lengths(t), _adjacency_lengths(t1),
                               cent, persist={1, 2, 3, 4}, min_border=3)
    assert len(swaps) == 1, swaps
    s = swaps[0]
    assert set(s["lost"]) == {1, 2}
    assert set(s["gained"]) == {3, 4}
    assert s["cluster"] == (1, 2, 3, 4)
    # location at the cluster centre
    assert abs(s["cx"] - 10) < 1 and abs(s["cy"] - 10) < 1


def test_t1_requires_persistence_of_all_four():
    """If a bubble of the cluster does not persist, it is not a T1 (it's a T2)."""
    t, t1 = _canonical_t1_pair()
    swaps = _detect_t1_between(_adjacency_lengths(t), _adjacency_lengths(t1),
                               {1: (2, 10), 2: (18, 10), 3: (10, 18), 4: (10, 2)},
                               persist={1, 2, 3}, min_border=3)   # 4 missing
    assert swaps == []


def test_t1_border_threshold_rejects_flicker():
    """A 1-px lost edge (below min_border) is not a real lost film → no swap."""
    t, t1 = _canonical_t1_pair()
    # widen min_border above the gained R-S border so the genuine swap is gated out
    swaps = _detect_t1_between(_adjacency_lengths(t), _adjacency_lengths(t1),
                               {i: (10, 10) for i in (1, 2, 3, 4)},
                               persist={1, 2, 3, 4}, min_border=999)
    assert swaps == []


def test_no_t1_when_topology_unchanged():
    t, _ = _canonical_t1_pair()
    swaps = _detect_t1_between(_adjacency_lengths(t), _adjacency_lengths(t),
                               {i: (10, 10) for i in (1, 2, 3, 4)},
                               persist={1, 2, 3, 4}, min_border=3)
    assert swaps == []


# ──────────────────────── visual-audit overlays ───────────────────────────── #

def test_overlay_ids_contract():
    img = np.full((20, 20), 120, np.uint8)
    idm = np.zeros((20, 20), np.int32)
    idm[:10] = 5
    idm[10:] = 9
    ov = overlay_ids(img, idm)
    assert ov.shape == (20, 20, 3) and ov.dtype == np.uint8


def test_overlay_events_marks_only_requested_frame():
    from foam_gnn.tracking import TopologicalEvent
    img = np.full((40, 40), 100, np.uint8)
    evs = [TopologicalEvent(2, "T1_swap", (1, 2, 3, 4), {"cx": 20.0, "cy": 20.0})]
    on = overlay_events(img, evs, frame=2)
    off = overlay_events(img, evs, frame=3)
    assert on.shape == (40, 40, 3)
    # frame 2 draws something (differs from raw); frame 3 draws nothing
    assert (on != np.dstack([img] * 3)).any()
    assert (off == np.dstack([img] * 3)).all()


# ──────────────────────── merge fix (deterministic) ───────────────────────── #
# Mentor's rule: bubbles never appear — a merge inherits an EXISTING id (never a
# new one). These assert the rule on synthetic frames with KNOWN ids.

import dataclasses as _dc                                        # noqa: E402
from scipy import ndimage as _ndi                                # noqa: E402


def _seg_from(labels: np.ndarray) -> SegmentationResult:
    labels = labels.astype(np.int32)
    foam = _ndi.binary_fill_holes(labels > 0)
    dist = _ndi.distance_transform_edt(foam).astype(np.float32)
    return SegmentationResult(labels, foam, dist, int(labels.max()))


def _merge_seq(persist: int = 2, w1: int = 15) -> list:
    """Bubbles 1 (left, width ``w1``) & 2 (right) merge into one region for
    ``persist`` frames after the initial two-bubble frame."""
    two = np.zeros((24, 40), np.int32)
    two[4:20, 4:4 + w1] = 1
    two[4:20, 4 + w1:36] = 2
    one = np.zeros((24, 40), np.int32)
    one[4:20, 4:36] = 1
    return [_seg_from(two)] + [_seg_from(one)] * persist


def test_merge_default_keeps_larger_area_id():
    """Dr. Oh's Option 3 (default): the survivor keeps the LARGER-AREA parent's ID,
    even though that ID is the *smaller* number — a discriminating case."""
    # w1=24 → bubble 1 is the LARGER area (24-wide) but has the SMALLER id;
    # bubble 2 is the smaller area (8-wide). keep_larger ⇒ survivor = 1 (not max = 2).
    tr = track_sequence(_merge_seq(w1=24), PipelineConfig())
    ids = [sorted(set(np.unique(m).tolist()) - {0}) for m in tr.id_maps]
    assert ids == [[1, 2], [1], [1]]                                # larger-area bubble 1 survives
    assert all(e.kind != "birth" for e in tr.events)                # a merge never births
    assert tr.diagnostics["max_bubble_id"] == 2                     # no new ID minted
    assert tr.diagnostics["invariant_B_holds"]
    merges = [e for e in tr.events if e.kind == "merge"]
    assert len(merges) == 1
    assert merges[0].meta["survivor"] == 1 and merges[0].meta["merged_ids"] == (2,)


def test_merge_max_rule_ablation_still_available():
    """The old 'max' rule remains selectable and gives a DIFFERENT survivor (the
    larger ID number) on the same unequal-size merge."""
    cfg = PipelineConfig(track=_dc.replace(PipelineConfig().track, merge_id_rule="max"))
    tr = track_sequence(_merge_seq(w1=24), cfg)                     # bubble 1 larger area, bubble 2 larger id
    assert sorted(set(np.unique(tr.id_maps[-1]).tolist()) - {0}) == [2]   # max id survives
    assert all(e.kind != "birth" for e in tr.events)


def test_merge_survivor_unique_per_frame():
    """A parent that splits ~50/50 into two merge regions cannot be the survivor of
    BOTH — the second falls back to its next-best parent, keeping IDs unique per
    frame (regression for the keep_larger duplicate-ID bug)."""
    f0 = np.zeros((24, 40), np.int32)
    f0[6:18, 2:8] = 2                     # small left (area 72)
    f0[6:18, 8:32] = 1                    # large centre (area 288) — will split 50/50
    f0[6:18, 32:38] = 3                   # small right (area 72)
    f1 = np.zeros((24, 40), np.int32)
    f1[6:18, 2:20] = 1                    # left half of 1 (frac .5) + bubble 2  → survivor 1
    f1[6:18, 20:38] = 2                   # right half of 1 (frac .5) + bubble 3 → survivor 1 taken → 3
    tr = track_sequence([_seg_from(f0), _seg_from(f1)], PipelineConfig())
    ids1 = sorted(set(np.unique(tr.id_maps[1]).tolist()) - {0})
    assert ids1 == [1, 3]                 # unique; larger bubble 1 keeps its ID once, 3 falls back
    assert len(ids1) == 2                 # one ID per region (frame 1 has 2 regions)
    assert tr.diagnostics["max_bubble_id"] == 3 and tr.diagnostics["invariant_B_holds"]


def test_merge_flicker_resurrection_no_new_id():
    two = np.zeros((24, 40), np.int32)
    two[4:20, 4:19] = 1
    two[4:20, 19:36] = 2
    one = np.zeros((24, 40), np.int32)
    one[4:20, 4:36] = 1
    tr = track_sequence([_seg_from(two), _seg_from(one), _seg_from(two)], PipelineConfig())
    ids = [sorted(set(np.unique(m).tolist()) - {0}) for m in tr.id_maps]
    assert ids == [[1, 2], [2], [1, 2]]                            # re-split restores BOTH ids
    assert all(e.kind != "birth" for e in tr.events)               # flicker mints no new id
    assert tr.diagnostics["invariant_B_holds"]
    assert tr.diagnostics["n_split_reconciled"] >= 1
