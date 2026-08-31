"""
foam_gnn.gt_preseed
====================
Ground-truth labeling support: the canonical frame manifest (which ``(set, exp,
frame)`` triples are labeled) and **correction-based pre-seeding** — computing the
current temporal marker-propagation segmentation for a requested frame so the
annotator corrects it rather than draws ~150-300 bubbles from scratch.

# DECISION — correction-based annotation, and the bias it introduces
----------------------------------------------------------------------
Hand-labeling ~30 frames (each ~150-300 bubbles) fully from scratch is infeasible
(40+ hours). Standard annotation practice instead is **correction-based**: pre-seed
the labels layer with an automatic segmentation, and have the annotator fix its
errors (delete false regions, split/merge, add missed bubbles) rather than paint
every bubble by hand.

This is a REAL METHODOLOGICAL CAVEAT, not a footnote: correction-based ground truth
is **biased toward the seeding method**. An annotator correcting a segmentation is
systematically less likely to notice an error the segmenter makes *consistently*
(nothing proposed there -> nothing to look at) than one who draws independently —
"rubber-stamping". The bias is worst exactly on the population this project depends
on: bubbles the propagated segmenter **misses entirely** (no proposed region to
examine), especially small bubbles near the evaporation edge.

Two mitigations, both load-bearing for scientific honesty (neither REMOVES the bias):
1. **Provenance is recorded per-frame** in ``groundtruth/manifest.csv``
   (``seed_method`` / ``preseed_source`` columns, see :func:`upsert_manifest_row`)
   so every downstream evaluation can see — and if needed exclude or flag — which
   labels are correction-based.
2. ``label.py`` supports an **audit mode**: pressing ``V`` in napari (the built-in
   "toggle selected layer visibility" binding) hides the pre-seed entirely, showing
   only the raw frame, so the annotator can search for missed bubbles on the bare
   image before/in addition to correcting the seeded labels.

Both must be disclosed in any writeup that uses this GT — see
``docs/groundtruth_labeling.md``.

Shapes: label maps int32/uint16 ``(H, W)``, 0 = background.
"""
from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio
import numpy as np
import pandas as pd

from .config import PipelineConfig
from .dataset import contiguous_runs, experiment_timestamps
from .io_utils import load_experiment_frames
from .seg_eval import relabel_sequential

__all__ = [
    "LABEL_FRAMES",
    "SEED_PROPAGATED",
    "SEED_BLANK",
    "SEED_UNKNOWN_LEGACY",
    "MANIFEST_COLUMNS",
    "frame_status",
    "STATUS_IN_PROGRESS",
    "STATUS_FINAL",
    "STATUS_INSPECTED",
    "UNUSABLE_STATUSES",
    "frame_tag",
    "raw_frame_path",
    "corrected_path",
    "preseed_path",
    "save_label_png",
    "load_label_png",
    "propagate_session_labels",
    "compute_or_load_preseed",
    "upsert_manifest_row",
]

# (set, exp, frame_index, note) — consecutive pairs across the coarsening timeline;
# EVAL and TRAIN are disjoint by SESSION on Foam C (eval exp3/exp5, train
# exp4/exp6/exp7) and by FRAME on Foam A (one session only). Single source of truth
# for dev/export_label_frames.py, dev/preseed_labels.py and label.py — see
# docs/groundtruth_labeling.md for the rationale.
LABEL_FRAMES: list[tuple[str, str, int, str]] = [
    # ── EVAL (held out, never trained on) ──
    ("eval", "exp1", 0, "Foam A dense early run0; pair f001"),
    ("eval", "exp1", 1, "Foam A; consecutive f000"),
    ("eval", "exp1", 49, "Foam A mid run0; pair f050"),
    ("eval", "exp1", 50, "Foam A; consecutive f049"),
    ("eval", "exp1", 97, "Foam A late run0; pair f098"),
    ("eval", "exp1", 98, "Foam A; consecutive f097"),
    ("eval", "exp1", 148, "Foam A run1 mid; pair f149"),
    ("eval", "exp1", 149, "Foam A; consecutive f148"),
    ("eval", "exp3", 0, "Foam C dense early; pair f001"),
    ("eval", "exp3", 1, "Foam C; consecutive f000"),
    ("eval", "exp3", 49, "Foam C mid; pair f050"),
    ("eval", "exp3", 50, "Foam C; consecutive f049"),
    ("eval", "exp3", 97, "Foam C late; pair f098"),
    ("eval", "exp3", 98, "Foam C; consecutive f097"),
    ("eval", "exp5", 49, "Foam C session exp5 mid; pair f050"),
    ("eval", "exp5", 50, "Foam C; consecutive f049"),
    # ── TRAIN (fine-tuning only; disjoint sessions on C, disjoint frames on A) ──
    ("train", "exp1", 24, "Foam A run0 train; pair f025"),
    ("train", "exp1", 25, "Foam A; consecutive f024"),
    ("train", "exp1", 73, "Foam A run0 train; pair f074"),
    ("train", "exp1", 74, "Foam A; consecutive f073"),
    ("train", "exp1", 120, "Foam A run1 train; pair f121"),
    ("train", "exp1", 121, "Foam A; consecutive f120"),
    ("train", "exp4", 0, "Foam C train session exp4; pair f001"),
    ("train", "exp4", 1, "Foam C; consecutive f000"),
    ("train", "exp4", 49, "Foam C train session exp4; pair f050"),
    ("train", "exp4", 50, "Foam C; consecutive f049"),
    ("train", "exp6", 49, "Foam C train session exp6; pair f050"),
    ("train", "exp6", 50, "Foam C; consecutive f049"),
    ("train", "exp7", 49, "Foam C train session exp7; pair f050"),
    ("train", "exp7", 50, "Foam C; consecutive f049"),
]

SEED_PROPAGATED = "propagated_segmenter_correction"
SEED_BLANK = "blank_manual"
# DECISION: written only when RESUMING a frame that has a corrected mask on disk but
# NO manifest row (e.g. it predates this provenance system) -- honest "we don't
# actually know" rather than silently defaulting to blank or guessing propagated.
SEED_UNKNOWN_LEGACY = "unknown_legacy_resume"

MANIFEST_COLUMNS = ["set", "exp", "frame_index", "path", "labeler", "date", "notes",
                    "seed_method", "preseed_source", "status"]

# DECISION: `status` gates whether a labeled frame may be used as ground truth.
# A frame that was merely OPENED (so its file on disk is still the raw automatic
# pre-seed, with no human correction) is NOT ground truth: scoring the segmenter
# against its own output would "validate" it perfectly and silently. Such frames are
# marked `inspected_not_corrected` and are EXCLUDED by load_gt_manifest by default.
STATUS_IN_PROGRESS = "in_progress"                  # human correction started, usable but partial
STATUS_FINAL = "final"                              # correction complete
STATUS_INSPECTED = "inspected_not_corrected"        # opened only; file == pre-seed; NOT GT
UNUSABLE_STATUSES = frozenset({STATUS_INSPECTED, "abandoned"})


# --------------------------------------------------------------------------- #
# Path builders
# --------------------------------------------------------------------------- #
def frame_tag(frame_index: int) -> str:
    """``f<idx>`` zero-padded to 3 digits, e.g. ``49 -> "f049"``."""
    return f"f{frame_index:03d}"


def raw_frame_path(gt_root: str | Path, dset: str, exp: str, frame_index: int) -> Path:
    """Exported raw frame for labeling: ``<gt_root>/tolabel/<set>/<exp>_f<idx>.png``."""
    return Path(gt_root) / "tolabel" / dset / f"{exp}_{frame_tag(frame_index)}.png"


def corrected_path(gt_root: str | Path, dset: str, exp: str, frame_index: int) -> Path:
    """Hand-corrected label mask: ``<gt_root>/<set>/<exp>/f<idx>.png``."""
    return Path(gt_root) / dset / exp / f"{frame_tag(frame_index)}.png"


def preseed_path(gt_root: str | Path, dset: str, exp: str, frame_index: int) -> Path:
    """Cached automatic pre-seed: ``<gt_root>/preseed/<set>/<exp>/f<idx>.png``."""
    return Path(gt_root) / "preseed" / dset / exp / f"{frame_tag(frame_index)}.png"


# --------------------------------------------------------------------------- #
# Label PNG IO (imageio is unicode-path-safe on Windows; unlike cv2.imread)
# --------------------------------------------------------------------------- #
def save_label_png(path: str | Path, labels: np.ndarray) -> None:
    """Write a label map as a lossless 16-bit PNG (creates parent dirs)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(path, labels.astype(np.uint16))


def load_label_png(path: str | Path) -> np.ndarray:
    """Read a label PNG back as ``int32 (H, W)``."""
    arr = iio.imread(path)
    if arr.ndim == 3:      # some viewers export RGB even for label layers
        arr = arr[..., 0]
    return arr.astype(np.int32)


# --------------------------------------------------------------------------- #
# Propagation-based pre-seeding
# --------------------------------------------------------------------------- #
def propagate_session_labels(
    data_root: str | Path,
    exp: str,
    frame_indices: list[int],
    cfg: PipelineConfig | None = None,
) -> dict[int, np.ndarray]:
    """Run the temporal marker-propagation segmenter and return stable-ID labels
    for the requested ABSOLUTE frame indices of ``exp``.

    Propagation is sequential within a contiguous run, so this groups the request
    by run (:func:`foam_gnn.dataset.contiguous_runs`) and, per run, segments only
    ``[run_start, max(requested)+1)`` — the minimum prefix that covers every
    requested frame in that run — then slices out the requested indices. Frames in
    two different runs of the same experiment (e.g. ``exp1``'s two runs) are handled
    independently, each from its own run start.

    Returns ``{frame_index: labels int32 (H, W)}`` in STABLE-ID space (not yet
    relabeled to contiguous 1..K — see :func:`compute_or_load_preseed`).
    """
    from .propagate import segment_track_propagated  # local: torch-free but heavy import chain

    cfg = cfg or PipelineConfig()
    wanted = sorted(set(frame_indices))
    if not wanted:
        return {}
    ts = experiment_timestamps(data_root, exp)
    runs = contiguous_runs(ts)
    out: dict[int, np.ndarray] = {}
    for a, b in runs:
        local_needed = sorted(i - a for i in wanted if a <= i < b)
        if not local_needed:
            continue
        max_local = local_needed[-1]
        _paths, imgs = load_experiment_frames(data_root, exp, indices=list(range(a, a + max_local + 1)))
        _results, tr = segment_track_propagated(imgs, cfg)
        for i in local_needed:
            out[a + i] = tr.id_maps[i]
    missing = set(wanted) - set(out)
    if missing:
        raise ValueError(f"{exp}: frame indices {sorted(missing)} not in any contiguous run "
                         f"(runs={runs})")
    return out


def compute_or_load_preseed(
    data_root: str | Path,
    gt_root: str | Path,
    dset: str,
    exp: str,
    frame_index: int,
    cfg: PipelineConfig | None = None,
    *,
    use_cache: bool = True,
) -> tuple[np.ndarray, str]:
    """Get a pre-seed label mask for one frame, contiguously relabeled ``1..K``.

    Cache-first: loads ``preseed_path(...)`` if present. Otherwise computes via
    :func:`propagate_session_labels` for JUST this frame (slow — segments the whole
    prefix of its run) and, if ``use_cache``, writes it to the cache for next time.

    Returns ``(labels, source)`` with ``source`` in ``{"cache", "computed"}``.
    """
    pth = preseed_path(gt_root, dset, exp, frame_index)
    if use_cache and pth.is_file():
        return relabel_sequential(load_label_png(pth)), "cache"
    labels_by_idx = propagate_session_labels(data_root, exp, [frame_index], cfg)
    raw = labels_by_idx[frame_index]
    if use_cache:
        save_label_png(pth, raw)
    return relabel_sequential(raw), "computed"


# --------------------------------------------------------------------------- #
# Manifest provenance (# DECISION: preserve first-write seed_method on resume)
# --------------------------------------------------------------------------- #
def frame_status(gt_root: str | Path, dset: str, exp: str, frame_index: int) -> str:
    """The manifest ``status`` for one frame, or ``""`` if it has no row.

    Used by ``label.py`` to decide whether an existing mask on disk is genuine
    work-in-progress (resume it) or merely an untouched pre-seed that was opened and
    abandoned (do NOT resume — re-seed, so a stale pre-seed is not mistaken for GT).
    """
    man = Path(gt_root) / "manifest.csv"
    if not man.is_file():
        return ""
    df = pd.read_csv(man, keep_default_na=False)
    if "status" not in df.columns:
        return ""
    hit = df[(df["set"] == dset) & (df["exp"] == exp)
             & (df["frame_index"].astype(int) == int(frame_index))]
    return str(hit.iloc[0]["status"]).strip() if len(hit) else ""


def upsert_manifest_row(
    gt_root: str | Path,
    dset: str,
    exp: str,
    frame_index: int,
    *,
    seed_method: str,
    preseed_source: str = "",
    labeler: str = "",
    date: str = "",
    notes: str = "",
    status: str = STATUS_IN_PROGRESS,
) -> Path:
    """Insert or update one ``manifest.csv`` row for ``(set, exp, frame_index)``.

    ``seed_method`` / ``preseed_source`` are PROVENANCE: written on first save and
    then PRESERVED on every later resume-and-save (never silently overwritten), so
    the manifest always records how the label truly originated even after many
    correction sessions. ``labeler`` / ``date`` / ``notes`` / ``status`` are refreshed
    each call when non-empty. Returns the manifest path.
    """
    text_cols = [c for c in MANIFEST_COLUMNS if c != "frame_index"]
    man_path = Path(gt_root) / "manifest.csv"
    if man_path.is_file():
        # force text columns to object/str: an all-empty column read from CSV would
        # otherwise infer float64 (NaN), which then errors/warns on string assignment.
        df = pd.read_csv(man_path, dtype={"frame_index": "Int64",
                                          **{c: str for c in text_cols}}, keep_default_na=False)
    else:
        df = pd.DataFrame(columns=MANIFEST_COLUMNS)
    for c in MANIFEST_COLUMNS:
        if c not in df.columns:
            df[c] = ""
        elif c in text_cols:
            df[c] = df[c].astype(object)
    rel_path = f"{dset}/{exp}/{frame_tag(frame_index)}.png"
    mask = (df["set"] == dset) & (df["exp"] == exp) & (df["frame_index"] == frame_index) \
        if len(df) else pd.Series([], dtype=bool)
    if mask.any():
        i = df.index[mask][0]
        if not str(df.at[i, "seed_method"]).strip():
            df.at[i, "seed_method"] = seed_method
            df.at[i, "preseed_source"] = preseed_source
        if labeler:
            df.at[i, "labeler"] = labeler
        if date:
            df.at[i, "date"] = date
        if notes:
            df.at[i, "notes"] = notes
        if status:
            df.at[i, "status"] = status
        df.at[i, "path"] = rel_path
    else:
        df.loc[len(df)] = {"set": dset, "exp": exp, "frame_index": frame_index, "path": rel_path,
                           "labeler": labeler, "date": date, "notes": notes,
                           "seed_method": seed_method, "preseed_source": preseed_source,
                           "status": status}
    df.to_csv(man_path, index=False)
    return man_path
