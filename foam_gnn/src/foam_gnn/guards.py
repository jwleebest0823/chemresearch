"""
foam_gnn.guards
===============
Runtime validation helpers. The design philosophy of this whole pipeline is
**fail loud, fail early**: every module boundary asserts the shape, dtype and
finiteness of its inputs and outputs so that bad data raises a clear error
immediately instead of silently corrupting a downstream model.

These helpers raise ``TypeError`` / ``ValueError`` with messages that name the
offending array and report expected-vs-actual. ``check_tensor`` lazily imports
torch so that importing this module never requires a deep-learning stack.
"""
from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["check_array", "check_tensor"]


def check_array(
    name: str,
    a: Any,
    *,
    ndim: int | None = None,
    shape: tuple[int | None, ...] | None = None,
    dtype: Any = None,
    finite: bool = False,
    nonneg: bool = False,
) -> np.ndarray:
    """Validate a numpy array; return it unchanged if valid.

    Parameters
    ----------
    name : str
        Human-readable identifier used in error messages.
    a : Any
        Object expected to be an ``np.ndarray``.
    ndim : int, optional
        Required number of dimensions.
    shape : tuple, optional
        Required shape; use ``None`` for wildcard axes, e.g. ``(None, 3)``.
    dtype : optional
        Required dtype. May be a concrete dtype (``np.uint8``) or a numpy
        scalar *kind* via ``np.floating`` / ``np.integer`` (subdtype check).
    finite : bool
        If True and the array is floating point, require all entries finite.
    nonneg : bool
        If True, require ``a.min() >= 0``.

    Raises
    ------
    TypeError, ValueError
        On any violation.
    """
    if not isinstance(a, np.ndarray):
        raise TypeError(f"{name}: expected np.ndarray, got {type(a).__name__}")
    if ndim is not None and a.ndim != ndim:
        raise ValueError(f"{name}: expected ndim={ndim}, got ndim={a.ndim} (shape={a.shape})")
    if shape is not None:
        if len(shape) != a.ndim:
            raise ValueError(f"{name}: expected shape {shape}, got {a.shape}")
        for axis, (exp, got) in enumerate(zip(shape, a.shape)):
            if exp is not None and exp != got:
                raise ValueError(f"{name}: axis {axis} expected {exp}, got {got} (full shape {a.shape})")
    if dtype is not None:
        if isinstance(dtype, type) and issubclass(dtype, np.generic):
            if not np.issubdtype(a.dtype, dtype):
                raise ValueError(f"{name}: expected dtype kind {dtype.__name__}, got {a.dtype}")
        elif a.dtype != np.dtype(dtype):
            raise ValueError(f"{name}: expected dtype {np.dtype(dtype)}, got {a.dtype}")
    if finite and a.size and np.issubdtype(a.dtype, np.floating) and not np.isfinite(a).all():
        n_bad = int((~np.isfinite(a)).sum())
        raise ValueError(f"{name}: contains {n_bad} non-finite (NaN/Inf) values")
    if nonneg and a.size and a.min() < 0:
        raise ValueError(f"{name}: expected non-negative values, got min={a.min()}")
    return a


def check_tensor(
    name: str,
    t: Any,
    *,
    shape: tuple[int | None, ...] | None = None,
    dtype: Any = None,
    finite: bool = True,
) -> "Any":
    """Validate a torch tensor; return it unchanged if valid. Torch is imported lazily."""
    import torch  # local import keeps the base package torch-free

    if not isinstance(t, torch.Tensor):
        raise TypeError(f"{name}: expected torch.Tensor, got {type(t).__name__}")
    if shape is not None:
        if len(shape) != t.dim():
            raise ValueError(f"{name}: expected shape {shape}, got {tuple(t.shape)}")
        for axis, (exp, got) in enumerate(zip(shape, t.shape)):
            if exp is not None and exp != got:
                raise ValueError(f"{name}: axis {axis} expected {exp}, got {got} (full shape {tuple(t.shape)})")
    if dtype is not None and t.dtype != dtype:
        raise ValueError(f"{name}: expected dtype {dtype}, got {t.dtype}")
    if finite and t.numel() and not torch.isfinite(t).all():
        n_bad = int((~torch.isfinite(t)).sum())
        raise ValueError(f"{name}: contains {n_bad} non-finite (NaN/Inf) values")
    return t
