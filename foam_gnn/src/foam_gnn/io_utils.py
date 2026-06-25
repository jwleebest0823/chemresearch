"""
foam_gnn.io_utils
=================
Frame discovery and loading, with validation at the boundary.

Assumptions
-----------
* The physical/temporal structure (which folders are which foam, per-experiment
  image shape and file extension, nested-subfolder layout) lives in
  :mod:`foam_gnn.dataset`. This module only *reads pixels*; it defers all
  structure questions there.
* Frames are read unchanged then converted to grayscale (luminance). The colour
  channels carry only a non-physical sensor/illumination cast and are discarded
  on purpose (brightfield, no interferometry -> no thickness from colour).
* **Unicode paths.** ``cv2.imread`` cannot open files whose *path* contains
  non-ASCII characters (this repo lives under ``...\\문서\\...``); it silently
  returns ``None``. We therefore decode via ``np.fromfile`` + ``cv2.imdecode``,
  which is byte-oriented and unicode-safe. This also reads the TIF frames
  (Foam B) without a separate code path.
* **Per-experiment shape (B3).** There is no single global frame size: Foam B's
  camera produces 1536x2048 vs 1024x1280 for A/C. Shape is checked against the
  *correct* per-experiment size (from the registry), never disabled wholesale.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .config import DataConfig
from .dataset import EXPERIMENTS, experiment_frame_paths
from .guards import check_array

__all__ = [
    "list_experiment_frames",
    "load_frame",
    "load_experiment_frames",
]


def _imdecode_gray(path: Path) -> np.ndarray:
    """Unicode-safe decode of one image file to 8-bit grayscale ``(H, W)``.

    Uses ``np.fromfile`` (byte read, handles non-ASCII paths) + ``cv2.imdecode``.
    Handles JPG and TIF identically. Multi-channel input is converted to
    luminance; a single-channel input is returned as-is.

    Raises
    ------
    ValueError
        If the bytes cannot be decoded (corrupt / unsupported), or the result is
        not 8-bit after decode.
    """
    buf = np.fromfile(str(path), dtype=np.uint8)
    if buf.size == 0:
        raise ValueError(f"empty file (0 bytes): {path}")
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"failed to decode image (corrupt or unsupported): {path}")
    if img.ndim == 3:
        # DECISION: discard non-physical chroma -> luminance grayscale.
        # imdecode yields BGR(A) channel order; take the colour channels only.
        img = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        # Foam B TIFs are 8-bit, but guard the assumption: scale anything else to 8-bit.
        lo, hi = float(img.min()), float(img.max())
        img = np.zeros_like(img, dtype=np.uint8) if hi <= lo else \
            ((img.astype(np.float64) - lo) * (255.0 / (hi - lo))).astype(np.uint8)
    return img


def list_experiment_frames(cfg: DataConfig) -> dict[str, list[Path]]:
    """Return ``{experiment_name: [sorted frame paths]}`` for ``cfg.experiments``.

    Frames are sorted lexically (== chronologically, since names are zero-padded
    timestamps). If no frames match directly under ``data_root/exp/`` the single
    nested subfolder is searched (the real data nests images one level down).

    Raises ``FileNotFoundError`` (fail loud) if a folder is missing or yields no
    matching frames.
    """
    out: dict[str, list[Path]] = {}
    for exp in cfg.experiments:
        d = cfg.data_root / exp
        if not d.is_dir():
            raise FileNotFoundError(
                f"experiment folder not found: {d} "
                f"(data_root={cfg.data_root}, experiments={cfg.experiments})"
            )
        frames = sorted(d.glob(cfg.frame_glob))
        if not frames:  # descend into a single nested subfolder (real-data layout)
            subdirs = [s for s in d.iterdir() if s.is_dir()]
            cand = [s for s in subdirs if any(s.glob(cfg.frame_glob))]
            if len(cand) == 1:
                frames = sorted(cand[0].glob(cfg.frame_glob))
        if not frames:
            raise FileNotFoundError(f"no frames matching '{cfg.frame_glob}' in {d} (or its subfolder)")
        out[exp] = frames
    return out


def load_frame(
    path: str | Path,
    cfg: DataConfig | None = None,
    *,
    expected_hw: tuple[int, int] | None = None,
) -> np.ndarray:
    """Load one frame as an 8-bit grayscale ``(H, W)`` array (unicode-safe).

    Shape enforcement (fail loud) is resolved in priority order:

    1. explicit ``expected_hw`` argument, if given;
    2. else ``cfg.expected_hw`` when ``cfg is not None and cfg.enforce_shape``;
    3. else no shape check.

    Parameters
    ----------
    path : str | Path
    cfg : DataConfig, optional
        Back-compat path: callers that pass a config get its global
        ``expected_hw`` / ``enforce_shape`` behaviour. Prefer ``expected_hw`` for
        per-experiment correctness (see :func:`load_experiment_frames`).
    expected_hw : (H, W), optional
        Per-frame expected shape; overrides ``cfg``.

    Raises
    ------
    FileNotFoundError, ValueError
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"frame not found: {path}")
    gray = _imdecode_gray(path)

    want = expected_hw
    if want is None and cfg is not None and cfg.enforce_shape:
        want = tuple(cfg.expected_hw)
    if want is not None and gray.shape != tuple(want):
        raise ValueError(
            f"{path.name}: shape {gray.shape} != expected {tuple(want)} "
            f"(per-experiment shapes live in foam_gnn.dataset.EXPERIMENTS)"
        )
    return check_array("frame", gray, ndim=2, dtype=np.uint8)


def load_experiment_frames(
    data_root: str | Path,
    exp: str,
    *,
    indices: slice | range | list[int] | None = None,
) -> tuple[list[Path], list[np.ndarray]]:
    """Discover and load an experiment's frames with the *correct* shape check.

    Looks up the per-experiment extension, nested layout and expected ``(H, W)``
    from :mod:`foam_gnn.dataset`, so Foam B's TIFs load and are shape-checked
    against 1536x2048 (not the A/C size).

    Parameters
    ----------
    data_root : str | Path
    exp : str
        Experiment name (must be in the registry).
    indices : slice | range | list[int], optional
        Subselect frames before loading (the full series can be hundreds of
        frames); ``None`` loads all.

    Returns
    -------
    (paths, images)
        ``paths`` : selected frame paths (chronological).
        ``images`` : matching list of ``uint8 (H, W)`` arrays.
    """
    if exp not in EXPERIMENTS:
        raise KeyError(f"unknown experiment {exp!r}; known: {sorted(EXPERIMENTS)}")
    hw = EXPERIMENTS[exp].image_hw
    paths = experiment_frame_paths(data_root, exp)
    if indices is not None:
        paths = list(np.asarray(paths, dtype=object)[indices]) if isinstance(indices, slice) \
            else [paths[i] for i in indices]
    images = [load_frame(p, expected_hw=hw) for p in paths]
    return paths, images
