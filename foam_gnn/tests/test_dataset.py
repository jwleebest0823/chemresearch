"""
Smoke tests for foam_gnn.dataset — the physical-structure source of truth.

Two layers:
  * pure-logic tests (registry, LOFO folds, timestamp parsing, run-splitting)
    that never touch disk — always run;
  * real-data tests (temporal_table over data/) that skip when the raw dataset is
    absent (it is gitignored; only the 5 fixture frames are committed).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from foam_gnn.dataset import (
    EXPERIMENTS,
    FOAM_SESSIONS,
    FOAMS,
    all_experiments,
    contiguous_runs,
    experiments_of_foam,
    foam_of,
    leave_one_foam_out,
    parse_timestamp,
    temporal_table,
)

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
_HAS_DATA = DATA_ROOT.is_dir() and any((DATA_ROOT / e).is_dir() for e in EXPERIMENTS)
requires_data = pytest.mark.skipif(not _HAS_DATA, reason="raw data/ not present (gitignored)")


# --------------------------- registry / grouping --------------------------- #
def test_three_foams():
    assert FOAMS == ("A", "B", "C")
    assert experiments_of_foam("C") == ("exp3", "exp4", "exp5", "exp6", "exp7")


def test_registry_consistency():
    for name, meta in EXPERIMENTS.items():
        assert name in FOAM_SESSIONS[meta.foam]
        assert len(meta.image_hw) == 2 and all(d > 0 for d in meta.image_hw)
        assert meta.ext.startswith(".")


def test_foam_b_has_distinct_shape():
    # B3 motivation: Foam B's camera differs -> shape must NOT equal A/C.
    assert EXPERIMENTS["exp2"].image_hw != EXPERIMENTS["exp1"].image_hw


def test_foam_of_and_unknown_raises():
    assert foam_of("exp1") == "A"
    with pytest.raises(KeyError):
        foam_of("nope")


# --------------------------- LOFO invariants --------------------------- #
def test_lofo_three_disjoint_folds():
    folds = leave_one_foam_out()
    assert len(folds) == 3
    for f in folds:
        assert not (set(f["train_exps"]) & set(f["test_exps"]))
        # every experiment is accounted for exactly once
        assert set(f["train_exps"]) | set(f["test_exps"]) == set(all_experiments())


def test_foam_c_never_split():
    """The core anti-leakage invariant: C's 5 sessions always move together."""
    c = set(FOAM_SESSIONS["C"])
    for f in leave_one_foam_out():
        in_test = c & set(f["test_exps"])
        in_train = c & set(f["train_exps"])
        assert not (in_test and in_train), "Foam C split across train/test = leakage"


# --------------------------- timestamp parsing --------------------------- #
def test_parse_15_digit():
    assert parse_timestamp("210118231515177") == datetime(2021, 1, 18, 23, 15, 15, 177000)


def test_parse_17_digit():
    assert parse_timestamp("20260608104825796") == datetime(2026, 6, 8, 10, 48, 25, 796000)


def test_parse_accepts_path_and_ignores_ext():
    assert parse_timestamp(Path("a/b/260616053359444.jpg")) == datetime(2026, 6, 16, 5, 33, 59, 444000)


@pytest.mark.parametrize("bad", ["abc", "123", "2026013299999999"[:16], "210118236015177"])
def test_parse_bad_raises(bad):
    # non-digit, wrong length, and out-of-range fields (minute=60) all fail loud
    with pytest.raises(ValueError):
        parse_timestamp(bad)


# --------------------------- run splitting --------------------------- #
def test_contiguous_runs_splits_on_gap():
    base = datetime(2026, 1, 1, 0, 0, 0)
    from datetime import timedelta
    ts = [base + timedelta(seconds=30 * i) for i in range(5)]
    ts += [base + timedelta(seconds=30 * 4 + 600 + 30 * i) for i in range(1, 4)]  # +10min gap
    runs = contiguous_runs(ts, interval_seconds=30.0)
    assert runs == [(0, 5), (5, 8)]


def test_contiguous_runs_empty():
    assert contiguous_runs([]) == []


# --------------------------- real data (skipped if absent) --------------------------- #
@requires_data
def test_temporal_table_shape_and_structure():
    df = temporal_table(DATA_ROOT)
    assert len(df) == len(EXPERIMENTS)
    assert set(df["foam"]) == {"A", "B", "C"}
    # Foam C is 5 sessions, all on the same calendar day
    c = df[df["foam"] == "C"]
    assert len(c) == 5
    assert c["start"].dt.date.nunique() == 1
    # within-run interval is ~30 s everywhere
    assert (df["dt_median_s"].between(29.0, 31.0)).all()


@requires_data
def test_exp1_has_internal_gap_and_99_run():
    df = temporal_table(DATA_ROOT)
    row = df[df["exp"] == "exp1"].iloc[0]
    assert row["n_internal_gaps"] >= 1
    assert row["longest_run"] == 99
