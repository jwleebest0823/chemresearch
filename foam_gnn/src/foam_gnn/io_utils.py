"""
foam_gnn.io_utils
=================
Frame discovery and loading, with validation at the boundary.

Assumptions
-----------
* Each experiment is a subfolder of ``DataConfig.data_root`` holding frames that
  sort chronologically by filename (zero-padded indices recommended). This is
  the *only* coupling to the on-disk layout, so adding experiments 2/3 is just
  adding folders.
* Frames are read as colour then converted to grayscale (luminance). The colour
  channels carry only a non-physical sensor/illumination cast and are discarded
  on purpose (brightfield, no interferometry -> no thickness from colour).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .config import DataConfig
from .guards import check_array

__all__ = ["list_experiment_frames", "load_frame"]


def list_experiment_frames(cfg: DataConfig) -> dict[str, list[Path]]:
    """Return ``{experiment_name: [sorted frame paths]}``.

    Raises ``FileNotFoundError`` (fail loud) if an experiment folder is missing
    or contains no matching frames, rather than silently yielding an empty set.
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
        if not frames:
            raise FileNotFoundError(f"no frames matching '{cfg.frame_glob}' in {d}")
        out[exp] = frames
    return out


def load_frame(path: str | Path, cfg: DataConfig) -> np.ndarray:
    """Load one frame as an 8-bit grayscale image.

    Returns
    -------
    np.ndarray
        ``uint8`` array of shape ``(H, W)``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the file cannot be decoded, or (when ``cfg.enforce_shape``) its shape
        differs from ``cfg.expected_hw``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"frame not found: {path}")
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"failed to decode image (corrupt or unsupported): {path}")
    # DECISION: discard non-physical chroma -> luminance grayscale.
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if cfg.enforce_shape and gray.shape != tuple(cfg.expected_hw):
        raise ValueError(
            f"{path.name}: shape {gray.shape} != expected {tuple(cfg.expected_hw)} "
            f"(set DataConfig.enforce_shape=False to allow heterogeneous sizes)"
        )
    return check_array("frame", gray, ndim=2, dtype=np.uint8)
