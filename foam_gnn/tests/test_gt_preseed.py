"""Tests for foam_gnn.gt_preseed — path builders, PNG roundtrip, manifest provenance
preservation, and the cache-hit branch of compute_or_load_preseed (no data/ I/O).

The propagate_session_labels / on-the-fly compute_or_load_preseed path (which needs
real frames) is exercised only by dev/preseed_labels.py + manual runs, not unit
tests — foam_gnn.propagate itself is already tested in test_propagate.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from foam_gnn.gt_preseed import (
    LABEL_FRAMES,
    SEED_PROPAGATED,
    compute_or_load_preseed,
    corrected_path,
    frame_tag,
    load_label_png,
    preseed_path,
    raw_frame_path,
    save_label_png,
    upsert_manifest_row,
)


def test_label_frames_eval_train_disjoint_by_session_on_foam_c():
    eval_exps = {e for s, e, _i, _n in LABEL_FRAMES if s == "eval" and e != "exp1"}
    train_exps = {e for s, e, _i, _n in LABEL_FRAMES if s == "train" and e != "exp1"}
    assert eval_exps.isdisjoint(train_exps)


def test_label_frames_no_duplicate_triples():
    keys = [(s, e, i) for s, e, i, _n in LABEL_FRAMES]
    assert len(keys) == len(set(keys))


def test_frame_tag_and_path_builders(tmp_path):
    assert frame_tag(7) == "f007"
    assert frame_tag(149) == "f149"
    assert raw_frame_path(tmp_path, "eval", "exp1", 49).name == "exp1_f049.png"
    assert corrected_path(tmp_path, "eval", "exp1", 49) == tmp_path / "eval" / "exp1" / "f049.png"
    assert preseed_path(tmp_path, "train", "exp4", 1) == tmp_path / "preseed" / "train" / "exp4" / "f001.png"


def test_label_png_roundtrip_16bit(tmp_path):
    labels = np.zeros((20, 20), dtype=np.int32)
    labels[2:5, 2:5] = 300      # exercise the 16-bit range (would clip at 8-bit)
    labels[10:15, 10:15] = 65000
    p = tmp_path / "f000.png"
    save_label_png(p, labels)
    back = load_label_png(p)
    assert back.dtype == np.int32
    assert np.array_equal(back, labels)


def test_compute_or_load_preseed_cache_hit_no_data_io(tmp_path, monkeypatch):
    # write a fake cached pre-seed directly -- compute_or_load_preseed must use it
    # and must NOT touch data/ (propagate_session_labels would raise if called,
    # since "data" won't resolve inside tmp_path).
    raw = np.zeros((10, 10), dtype=np.int32)
    raw[0:3, 0:3] = 5           # non-contiguous label on purpose
    raw[5:8, 5:8] = 12
    save_label_png(preseed_path(tmp_path, "eval", "exp1", 0), raw)

    def _boom(*a, **k):
        raise AssertionError("propagate_session_labels should not be called on a cache hit")
    monkeypatch.setattr("foam_gnn.gt_preseed.propagate_session_labels", _boom)

    labels, source = compute_or_load_preseed("data", tmp_path, "eval", "exp1", 0, use_cache=True)
    assert source == "cache"
    assert set(np.unique(labels)) == {0, 1, 2}   # relabeled contiguous


def test_upsert_manifest_row_inserts_and_preserves_seed_method(tmp_path):
    p = upsert_manifest_row(tmp_path, "eval", "exp1", 0,
                            seed_method=SEED_PROPAGATED, preseed_source="cache",
                            labeler="JW", date="2026-07-12")
    df = pd.read_csv(p)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["seed_method"] == SEED_PROPAGATED
    assert row["preseed_source"] == "cache"
    assert row["labeler"] == "JW"

    # simulate a RESUME save: seed_method must NOT be overwritten even if a
    # different value is passed, but labeler/notes should still refresh
    upsert_manifest_row(tmp_path, "eval", "exp1", 0,
                        seed_method="unknown_legacy_resume", preseed_source="",
                        labeler="JW2", notes="second pass")
    df2 = pd.read_csv(p)
    assert len(df2) == 1   # updated in place, not duplicated
    row2 = df2.iloc[0]
    assert row2["seed_method"] == SEED_PROPAGATED     # preserved
    assert row2["labeler"] == "JW2"                    # refreshed
    assert row2["notes"] == "second pass"


def test_upsert_manifest_row_distinct_frames_are_separate_rows(tmp_path):
    upsert_manifest_row(tmp_path, "eval", "exp1", 0, seed_method=SEED_PROPAGATED)
    upsert_manifest_row(tmp_path, "eval", "exp1", 1, seed_method=SEED_PROPAGATED)
    df = pd.read_csv(tmp_path / "manifest.csv")
    assert len(df) == 2
    assert set(df["frame_index"]) == {0, 1}
