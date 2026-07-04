"""
foam_gnn.dataset
================
**Single source of truth for the PHYSICAL structure of the dataset.**

The on-disk layout has 7 folders (``exp1`` .. ``exp7``), but these are **3
physically independent foams** imaged across a total of **7 acquisition
sessions** (Foam C alone spans 5). Everything downstream — cross-validation
splits and tracking segmentation — keys off the structure declared here, not off
the folder names.

Two invariants this module exists to enforce
--------------------------------------------
1. **Cross-validation unit = FOAM.** Leave-one-foam-out = 3 folds (A, B, C).
   Foam C's five folders (``exp3`` .. ``exp7``) must **never** be split across
   train/test — they are the *same* bubble raft re-imaged, so splitting them is
   data leakage *by construction*, not by convention. :func:`leave_one_foam_out`
   is the only sanctioned way to build folds.
2. **Tracking unit = SESSION.** Each experiment folder is tracked *internally
   only*. Bubbles are **never** matched across an inter-session gap: over the
   multi-hour gaps inside Foam C the raft fully reorganizes, so identities do not
   survive. Sessions are placed on a common real-time axis (parsed timestamps) so
   long-timescale coarsening *across* C is still measurable even though tracking
   is per-session.

The 3 foams
-----------
* **Foam A** = ``exp1``         — B/W JPG, ~198 frames @30 s, magnification M1.
* **Foam B** = ``exp2``         — high-res TIF from a *different* USB camera:
  different image shape (1536x2048 vs 1024x1280) and magnification; the colour is
  a non-physical sensor cast and is discarded -> grayscale.
* **Foam C** = ``exp3..exp7``   — ONE bubble raft imaged in 5 sessions over
  ~10.7 h on a single day (2026-06-16), magnification ~M1.

Filename timestamps
-------------------
Frames are named ``<timestamp><3-digit tail>`` with the timestamp in one of two
zero-padded forms (the tail is sub-second / capture milliseconds):

* **15 digits** ``YYMMDDHHMMSS`` + 3  (exp1, exp3..exp7).  ``YY`` -> ``20YY``.
* **17 digits** ``YYYYMMDDHHMMSS`` + 3  (exp2).

Assumptions baked in (verified against the committed data, 2026-06)
-------------------------------------------------------------------
* Per-experiment frame counts: exp1=198, exp2=103, exp3..exp7=99 each.
* Acquisition interval is 30 s *within* a contiguous run. Some folders contain a
  small internal gap (exp1 has one 2.5-min gap splitting it into two 99-frame
  runs; exp2's first frame is a ~1.2-min outlier before a clean 102-frame run).
  Use :func:`contiguous_runs` to obtain gap-free runs for tracking.
* Images live in **one nested subfolder** inside each ``expN/`` (e.g.
  ``exp1/2D bubble array/*.jpg``). :func:`experiment_dir` resolves this.

This module imports nothing heavy (no cv2/torch); only ``pandas`` is used, and
only inside :func:`temporal_table`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__all__ = [
    "ExperimentMeta",
    "EXPERIMENTS",
    "FOAM_SESSIONS",
    "FOAMS",
    "foam_of",
    "experiments_of_foam",
    "all_experiments",
    "available_experiments",
    "leave_one_foam_out",
    "parse_timestamp",
    "experiment_dir",
    "experiment_frame_paths",
    "experiment_timestamps",
    "contiguous_runs",
    "temporal_table",
]


# --------------------------------------------------------------------------- #
# Per-experiment metadata registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExperimentMeta:
    """Immutable description of one experiment folder.

    Attributes
    ----------
    name : str
        Folder name, e.g. ``"exp1"``.
    foam : str
        Physical foam this session belongs to: ``"A" | "B" | "C"``. This is the
        cross-validation unit.
    image_hw : tuple[int, int]
        Expected ``(H, W)`` of every frame in this experiment. Per-experiment
        (NOT one global value) because Foam B's camera produces a different
        shape; loading must shape-check against the *right* size, not disable the
        check. DECISION (B3): shape is data, not a tunable -> lives here.
    ext : str
        Frame file extension, lower-case with dot, e.g. ``".jpg"`` / ``".tif"``.
    interval_seconds : float
        Nominal acquisition interval within a contiguous run.
    notes : str
        Human-readable provenance.
    """

    name: str
    foam: str
    image_hw: tuple[int, int]
    ext: str
    interval_seconds: float = 30.0
    notes: str = ""


# DECISION: foam -> ordered sessions. THE single source of truth for both CV
# folds (group by foam) and tracking segments (one per session). Foam C's five
# entries are one continuous raft and must move through CV together.
FOAM_SESSIONS: dict[str, tuple[str, ...]] = {
    "A": ("exp1",),
    "B": ("exp2",),
    "C": ("exp3", "exp4", "exp5", "exp6", "exp7"),
}
FOAMS: tuple[str, ...] = tuple(FOAM_SESSIONS)  # ("A", "B", "C")

EXPERIMENTS: dict[str, ExperimentMeta] = {
    "exp1": ExperimentMeta(
        "exp1", "A", (1024, 1280), ".jpg",
        notes="Foam A; B/W JPG; mag M1; 198 frames = two 99-frame runs split by a 2.5-min gap.",
    ),
    "exp2": ExperimentMeta(
        "exp2", "B", (1536, 2048), ".tif",
        notes="Foam B; high-res TIF; different USB camera -> different shape/mag; "
              "non-physical colour discarded -> grayscale; 1.2-min outlier first frame.",
    ),
    "exp3": ExperimentMeta("exp3", "C", (1024, 1280), ".jpg", notes="Foam C session 1/5."),
    "exp4": ExperimentMeta("exp4", "C", (1024, 1280), ".jpg", notes="Foam C session 2/5."),
    "exp5": ExperimentMeta("exp5", "C", (1024, 1280), ".jpg", notes="Foam C session 3/5."),
    "exp6": ExperimentMeta("exp6", "C", (1024, 1280), ".jpg", notes="Foam C session 4/5."),
    "exp7": ExperimentMeta("exp7", "C", (1024, 1280), ".jpg", notes="Foam C session 5/5."),
}

# Cross-check the two declarations agree (fail loud at import time).
_flat = tuple(e for exps in FOAM_SESSIONS.values() for e in exps)
assert set(_flat) == set(EXPERIMENTS), "FOAM_SESSIONS and EXPERIMENTS disagree on experiment set"
for _name, _meta in EXPERIMENTS.items():
    assert _meta.foam in FOAM_SESSIONS and _name in FOAM_SESSIONS[_meta.foam], (
        f"{_name}: foam {_meta.foam!r} inconsistent with FOAM_SESSIONS"
    )


# --------------------------------------------------------------------------- #
# Grouping helpers (CV folds, lookups)
# --------------------------------------------------------------------------- #
def foam_of(exp: str) -> str:
    """Return the foam label ('A'|'B'|'C') for an experiment name (fail loud)."""
    if exp not in EXPERIMENTS:
        raise KeyError(f"unknown experiment {exp!r}; known: {sorted(EXPERIMENTS)}")
    return EXPERIMENTS[exp].foam


def experiments_of_foam(foam: str) -> tuple[str, ...]:
    """Return the ordered session tuple for a foam (fail loud)."""
    if foam not in FOAM_SESSIONS:
        raise KeyError(f"unknown foam {foam!r}; known: {FOAMS}")
    return FOAM_SESSIONS[foam]


def all_experiments() -> tuple[str, ...]:
    """All experiment names in canonical (foam, then session) order."""
    return _flat


def available_experiments(data_root: str | Path, exps: tuple[str, ...] | None = None) -> tuple[str, ...]:
    """Registry experiments whose data folder actually exists under ``data_root``.

    Tolerant of a **removed** folder (e.g. exp2/Foam B is being scrapped): the
    registry keeps its metadata, but callers that iterate real data should use
    this so a missing folder is skipped, not a fail-loud error. Preserves order.
    """
    out: list[str] = []
    for e in (exps or all_experiments()):
        try:
            experiment_dir(data_root, e)
        except (FileNotFoundError, ValueError):
            continue
        out.append(e)
    return tuple(out)


def leave_one_foam_out() -> list[dict]:
    """Build the 3 leave-one-foam-out CV folds.

    Returns
    -------
    list[dict]
        One dict per fold with keys ``test_foam`` (str), ``test_exps``
        (tuple[str, ...]) and ``train_exps`` (tuple[str, ...]). By construction no
        experiment appears in both train and test, and Foam C's sessions are never
        split — they always land entirely in train or entirely in test.
    """
    folds: list[dict] = []
    for held in FOAMS:
        test_exps = FOAM_SESSIONS[held]
        train_exps = tuple(e for f in FOAMS if f != held for e in FOAM_SESSIONS[f])
        # invariant guard: disjoint train/test
        assert not (set(train_exps) & set(test_exps)), "LOFO leakage: train/test overlap"
        folds.append({"test_foam": held, "test_exps": test_exps, "train_exps": train_exps})
    return folds


# --------------------------------------------------------------------------- #
# Timestamp parsing
# --------------------------------------------------------------------------- #
def parse_timestamp(name: str | Path) -> datetime:
    """Parse a frame filename's encoded timestamp.

    Accepts a bare stem, a filename, or a path; the extension and any directory
    parts are ignored. Two zero-padded digit layouts are supported:

    * 15 digits ``YYMMDDHHMMSS`` + 3-digit ms tail  (``YY`` -> ``20YY``).
    * 17 digits ``YYYYMMDDHHMMSS`` + 3-digit ms tail.

    Returns
    -------
    datetime
        Parsed timestamp; the 3-digit tail is stored as milliseconds
        (microsecond = tail * 1000).

    Raises
    ------
    ValueError
        If the stem is not all-digits, has an unsupported length, or encodes an
        out-of-range calendar field (the ``datetime`` constructor validates the
        latter). Fail loud — a misparsed timestamp would silently corrupt the
        real-time axis and the inter-session gap structure.
    """
    stem = Path(name).stem if isinstance(name, (str, Path)) else str(name)
    if not stem.isdigit():
        raise ValueError(f"timestamp stem must be all digits, got {stem!r}")
    if len(stem) == 15:        # YYMMDDHHMMSS + ms(3)
        year = 2000 + int(stem[0:2])
        o = 2
    elif len(stem) == 17:      # YYYYMMDDHHMMSS + ms(3)
        year = int(stem[0:4])
        o = 4
    else:
        raise ValueError(
            f"unsupported timestamp length {len(stem)} for {stem!r} (expected 15 or 17)"
        )
    month, day = int(stem[o:o + 2]), int(stem[o + 2:o + 4])
    hh, mm, ss = int(stem[o + 4:o + 6]), int(stem[o + 6:o + 8]), int(stem[o + 8:o + 10])
    ms = int(stem[o + 10:o + 13])
    try:
        return datetime(year, month, day, hh, mm, ss, ms * 1000)
    except ValueError as exc:
        raise ValueError(f"{stem!r}: invalid calendar fields ({exc})") from exc


# --------------------------------------------------------------------------- #
# On-disk frame discovery (nested subfolder + per-experiment extension)
# --------------------------------------------------------------------------- #
def experiment_dir(data_root: str | Path, exp: str) -> Path:
    """Resolve the directory that actually holds an experiment's frames.

    Each ``expN/`` contains exactly one nested subfolder with the images (e.g.
    ``exp1/2D bubble array/``). This returns that subfolder if frames of the
    experiment's extension are not found directly under ``expN/``.

    Raises
    ------
    FileNotFoundError
        If ``expN/`` is missing or no frames can be located.
    ValueError
        If ``expN/`` is ambiguous (multiple candidate subfolders).
    """
    meta = EXPERIMENTS[exp] if exp in EXPERIMENTS else None
    ext = meta.ext if meta else ".jpg"
    top = Path(data_root) / exp
    if not top.is_dir():
        raise FileNotFoundError(f"experiment folder not found: {top}")
    if any(top.glob(f"*{ext}")):
        return top
    subdirs = [d for d in top.iterdir() if d.is_dir()]
    have = [d for d in subdirs if any(d.glob(f"*{ext}"))]
    if len(have) == 1:
        return have[0]
    if not have:
        raise FileNotFoundError(f"no '*{ext}' frames under {top} or its subfolders")
    raise ValueError(f"{top}: ambiguous layout, {len(have)} subfolders contain *{ext} frames")


def experiment_frame_paths(data_root: str | Path, exp: str) -> list[Path]:
    """Return the experiment's frame paths sorted chronologically by filename.

    Filenames are zero-padded encoded timestamps, so lexical sort == chronological
    sort. Fail loud if none are found.
    """
    meta = EXPERIMENTS[exp] if exp in EXPERIMENTS else None
    ext = meta.ext if meta else ".jpg"
    d = experiment_dir(data_root, exp)
    frames = sorted(d.glob(f"*{ext}"))
    if not frames:
        raise FileNotFoundError(f"no '*{ext}' frames in {d}")
    return frames


def experiment_timestamps(data_root: str | Path, exp: str) -> list[datetime]:
    """Parsed timestamps for an experiment, in chronological order."""
    return [parse_timestamp(p) for p in experiment_frame_paths(data_root, exp)]


# --------------------------------------------------------------------------- #
# Temporal analysis
# --------------------------------------------------------------------------- #
def contiguous_runs(
    timestamps: list[datetime],
    *,
    interval_seconds: float = 30.0,
    max_gap_factor: float = 2.0,
) -> list[tuple[int, int]]:
    """Split a timestamp list into gap-free runs.

    A break is declared wherever the spacing to the next frame exceeds
    ``max_gap_factor * interval_seconds``. Used to obtain a genuinely consecutive
    series for tracking / displacement statistics (e.g. exp1's internal 2.5-min
    gap must not be treated as a single 30-s step).

    Parameters
    ----------
    timestamps : list[datetime]
        Chronologically ordered (ascending) timestamps.
    interval_seconds, max_gap_factor : float
        A gap is "real" when ``dt > max_gap_factor * interval_seconds``.

    Returns
    -------
    list[tuple[int, int]]
        ``[(start_idx, stop_idx), ...]`` half-open index ranges into
        ``timestamps``; concatenated they cover the whole list with no overlap.
    """
    if not timestamps:
        return []
    thr = max_gap_factor * interval_seconds
    runs: list[tuple[int, int]] = []
    start = 0
    for i in range(1, len(timestamps)):
        dt = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if dt > thr:
            runs.append((start, i))
            start = i
    runs.append((start, len(timestamps)))
    return runs


def temporal_table(data_root: str | Path, exps: tuple[str, ...] | None = None):
    """Per-experiment temporal summary as a tidy ``pandas.DataFrame``.

    Columns: ``exp | foam | n | start | end | duration_min | dt_median_s |
    dt_min_s | dt_max_s | n_internal_gaps | longest_run | image_hw | ext``.

    ``n_internal_gaps`` / ``longest_run`` come from :func:`contiguous_runs` at the
    experiment's nominal interval. The frame is sorted by ``start`` so the common
    real-time axis (especially Foam C's 5 sessions) is obvious.
    """
    import numpy as np
    import pandas as pd

    exps = exps or all_experiments()
    rows: list[dict] = []
    for exp in exps:
        meta = EXPERIMENTS.get(exp)
        ts = experiment_timestamps(data_root, exp)
        ts = sorted(ts)
        secs = np.array([(t - ts[0]).total_seconds() for t in ts])
        diffs = np.diff(secs) if len(ts) > 1 else np.array([np.nan])
        runs = contiguous_runs(ts, interval_seconds=meta.interval_seconds if meta else 30.0)
        rows.append({
            "exp": exp,
            "foam": meta.foam if meta else "?",
            "n": len(ts),
            "start": ts[0],
            "end": ts[-1],
            "duration_min": (ts[-1] - ts[0]).total_seconds() / 60.0,
            "dt_median_s": float(np.median(diffs)),
            "dt_min_s": float(np.min(diffs)),
            "dt_max_s": float(np.max(diffs)),
            "n_internal_gaps": len(runs) - 1,
            "longest_run": max((b - a) for a, b in runs),
            "image_hw": meta.image_hw if meta else None,
            "ext": meta.ext if meta else None,
        })
    df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)
    return df
