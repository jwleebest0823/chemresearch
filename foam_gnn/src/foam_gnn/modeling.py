"""
foam_gnn.modeling
=================
Stage-1/2 modeling primitives: the per-bubble coarsening-rate **target**, the
**trivial baselines** every learned model must clear, and the **cluster-bootstrap**
evaluation harness. Pure ``pandas``/``numpy``/``scipy`` — no torch (the GNN lives
in a separate, optional module) so this is cheap to import and unit-testable.

What this operates on
---------------------
A **trusted-frame table**: the rows of :func:`foam_gnn.stability.select_stable_tracks`
(one row per frame of a trusted segment), concatenated across sessions with these
columns added by the assembly driver::

    foam | session | seg_uid | bubble_uid | segment_id | bubble_id |
    frame | time_seconds | area | n_sides | distance_to_evap_edge | cx | cy

``seg_uid`` = ``f"{session}:{segment_id}"`` (globally unique trusted segment);
``bubble_uid`` = ``f"{session}:{bubble_id}"`` (the cluster-bootstrap resampling
unit — a bubble's rows/intervals move together).

The target (# DECISION)
-----------------------
For horizon ``h`` (frames) and a frame ``t`` inside a trusted segment whose frame
``t+h`` is also in the *same* segment (segments are gap-free, so this just means the
segment extends ``h`` frames past ``t``):

* ``target_dadt`` = ``(A[t+h] - A[t]) / (time[t+h] - time[t])``  — mean areal rate
  over the horizon, px²/s. This is the quantity models predict.
* ``target_frac`` = ``(A[t+h] - A[t]) / A[t]``  — fractional change, for the
  scale-free target-distribution report (single-step ~noise vs horizon ~signal).

Small-data discipline
---------------------
* Evaluation is leave-one-foam-out (see :func:`lofo_folds`).
* Every CI is a **cluster bootstrap resampling whole bubbles** (``bubble_uid``),
  never rows — within-bubble autocorrelation would otherwise fake significance.
* Metrics are split **quiescent vs dynamic** (``EvalConfig.dynamic_frac_thresh``)
  so a "predict no change" model is not credited for the quiescent majority.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import PipelineConfig

__all__ = [
    "TRUSTED_COLUMNS",
    "FEATURE_COLUMNS",
    "lofo_folds",
    "make_horizon_samples",
    "segment_dynamic_flags",
    "target_distribution",
    "predict_persistence",
    "predict_global_mean",
    "predict_per_bubble_linear",
    "mae",
    "cluster_bootstrap_ci",
    "paired_delta_ci",
    "evaluate_baselines",
    "BaselineResult",
]

TRUSTED_COLUMNS = ["foam", "session", "seg_uid", "bubble_uid", "segment_id",
                   "bubble_id", "frame", "time_seconds", "area", "n_sides",
                   "distance_to_evap_edge", "cx", "cy"]

# Per-bubble features available to learned models (Stage 3). NO absolute position
# (cx, cy) — isotropy is required, so absolute-position features are deliberately
# excluded here (# DECISION). distance_to_evap_edge is the only spatial feature.
FEATURE_COLUMNS = ["area", "n_sides", "distance_to_evap_edge"]


def _require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns {missing}")


def lofo_folds(trusted: pd.DataFrame) -> list[dict]:
    """Leave-one-foam-out folds from the foams actually present.

    Returns ``[{"test_foam", "train_foams"}, ...]``. A foam's sessions never split
    across train/test (the foam is the CV unit).
    """
    foams = sorted(trusted["foam"].unique())
    if len(foams) < 2:
        raise ValueError(f"need >=2 foams for LOFO, got {foams}")
    return [{"test_foam": f, "train_foams": tuple(x for x in foams if x != f)} for f in foams]


def segment_dynamic_flags(trusted: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Per trusted segment: total fractional area change + dynamic/quiescent flag.

    Returns ``seg_uid | bubble_uid | foam | n_frames | frac_change | dynamic``.
    ``frac_change`` = ``|A_end - A_start| / A_start`` over the segment; ``dynamic``
    iff ``frac_change >= cfg.eval.dynamic_frac_thresh``.
    """
    _require_columns(trusted, ["seg_uid", "bubble_uid", "foam", "frame", "area"], "trusted")
    rows: list[dict] = []
    thr = cfg.eval.dynamic_frac_thresh
    for suid, g in trusted.groupby("seg_uid"):
        g = g.sort_values("frame")
        a0 = float(g["area"].iloc[0])
        a1 = float(g["area"].iloc[-1])
        frac = abs(a1 - a0) / a0 if a0 > 0 else float("nan")
        rows.append({"seg_uid": suid, "bubble_uid": g["bubble_uid"].iloc[0],
                     "foam": g["foam"].iloc[0], "n_frames": int(len(g)),
                     "frac_change": frac, "dynamic": bool(frac >= thr)})
    return pd.DataFrame(rows)


def make_horizon_samples(trusted: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Build supervised samples for one horizon (see module docstring for target).

    One row per (trusted segment, start-frame ``t``) that has a partner ``t+horizon``
    in the same segment. Columns: identity (``foam, session, seg_uid, bubble_uid,
    frame``), features at ``t`` (:data:`FEATURE_COLUMNS` + ``area_t``, ``time_t``),
    ``target_dadt``, ``target_frac``, and ``past_slope`` (causal area-vs-time slope
    over the segment frames ``<= t``; NaN when <2 past points) for the per-bubble
    linear baseline.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >=1, got {horizon}")
    _require_columns(trusted, TRUSTED_COLUMNS, "trusted")
    out: list[dict] = []
    for _suid, g in trusted.groupby("seg_uid"):
        g = g.sort_values("frame")
        frame = g["frame"].to_numpy()
        t = g["time_seconds"].to_numpy(dtype=float)
        a = g["area"].to_numpy(dtype=float)
        n = len(g)
        by_frame = {int(f): i for i, f in enumerate(frame)}
        base = g.iloc[0]
        for i in range(n):
            j = by_frame.get(int(frame[i]) + horizon)
            if j is None:
                continue
            dt = t[j] - t[i]
            if dt <= 0:
                continue
            # causal past slope over frames <= t (area vs time)
            if i >= 1 and np.ptp(t[: i + 1]) > 0:
                past_slope = float(np.polyfit(t[: i + 1], a[: i + 1], 1)[0])
            else:
                past_slope = float("nan")
            row = g.iloc[i]
            out.append({
                "foam": base["foam"], "session": base["session"],
                "seg_uid": base["seg_uid"], "bubble_uid": base["bubble_uid"],
                "frame": int(frame[i]), "horizon": int(horizon),
                "area_t": float(a[i]), "time_t": float(t[i]),
                "n_sides": float(row["n_sides"]),
                "distance_to_evap_edge": float(row["distance_to_evap_edge"]),
                "target_dadt": float((a[j] - a[i]) / dt),
                "target_frac": float((a[j] - a[i]) / a[i]) if a[i] > 0 else float("nan"),
                "past_slope": past_slope,
            })
    cols = ["foam", "session", "seg_uid", "bubble_uid", "frame", "horizon",
            "area_t", "time_t", "n_sides", "distance_to_evap_edge",
            "target_dadt", "target_frac", "past_slope"]
    return pd.DataFrame(out, columns=cols)


def target_distribution(trusted: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Median |fractional area change| at each horizon + the segment-level change.

    Confirms whether single-step change is near pixel noise while horizon/segment
    change is real. Returns one row per horizon plus a ``segment`` row, with
    ``n_samples``, ``median_abs_frac``, ``p90_abs_frac``, ``median_abs_dadt``.
    """
    rows: list[dict] = []
    for h in cfg.eval.rollout_horizons:
        s = make_horizon_samples(trusted, h)
        af = np.abs(s["target_frac"].to_numpy(dtype=float))
        ad = np.abs(s["target_dadt"].to_numpy(dtype=float))
        af = af[np.isfinite(af)]
        rows.append({"scope": f"h={h}", "n_samples": int(len(s)),
                     "median_abs_frac": float(np.median(af)) if len(af) else float("nan"),
                     "p90_abs_frac": float(np.percentile(af, 90)) if len(af) else float("nan"),
                     "median_abs_dadt": float(np.median(ad[np.isfinite(ad)])) if len(ad) else float("nan")})
    seg = segment_dynamic_flags(trusted, cfg)
    fc = seg["frac_change"].to_numpy(dtype=float)
    fc = fc[np.isfinite(fc)]
    rows.append({"scope": "segment", "n_samples": int(len(seg)),
                 "median_abs_frac": float(np.median(fc)) if len(fc) else float("nan"),
                 "p90_abs_frac": float(np.percentile(fc, 90)) if len(fc) else float("nan"),
                 "median_abs_dadt": float("nan")})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Baselines (all return a prediction array aligned to ``samples`` rows)
# --------------------------------------------------------------------------- #
def predict_persistence(samples: pd.DataFrame) -> np.ndarray:
    """Predict zero areal rate (area persists): dA/dt = 0."""
    return np.zeros(len(samples), dtype=float)


def predict_global_mean(samples: pd.DataFrame, train_mean_dadt: float) -> np.ndarray:
    """Predict a constant rate = the TRAIN-set mean target_dadt (fit on train foam)."""
    return np.full(len(samples), float(train_mean_dadt), dtype=float)


def predict_per_bubble_linear(samples: pd.DataFrame) -> np.ndarray:
    """Predict dA/dt = the bubble's causal past area-vs-time slope.

    Falls back to 0 (persistence) where the past slope is undefined (<2 past
    points), i.e. at a segment's first frame.
    """
    p = samples["past_slope"].to_numpy(dtype=float)
    return np.where(np.isfinite(p), p, 0.0)


# --------------------------------------------------------------------------- #
# Metrics + cluster bootstrap
# --------------------------------------------------------------------------- #
def mae(pred: np.ndarray, target: np.ndarray) -> float:
    """Mean absolute error over finite pairs (fail loud on shape mismatch)."""
    pred = np.asarray(pred, dtype=float)
    target = np.asarray(target, dtype=float)
    if pred.shape != target.shape:
        raise ValueError(f"pred {pred.shape} != target {target.shape}")
    m = np.isfinite(pred) & np.isfinite(target)
    if not m.any():
        return float("nan")
    return float(np.mean(np.abs(pred[m] - target[m])))


def cluster_bootstrap_ci(
    metric_fn,
    bubble_of: np.ndarray,
    n_boot: int,
    *,
    seed: int = 0,
) -> tuple[float, float]:
    """95% CI resampling whole bubbles. ``metric_fn(row_idx) -> float`` (NaN ok)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(bubble_of)
    by_bubble = {b: np.nonzero(bubble_of == b)[0] for b in uniq}
    vals: list[float] = []
    for _ in range(n_boot):
        samp = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([by_bubble[b] for b in samp])
        v = metric_fn(idx)
        if v is not None and np.isfinite(v):
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def paired_delta_ci(
    pred: np.ndarray,
    ref: np.ndarray,
    target: np.ndarray,
    bubble_of: np.ndarray,
    n_boot: int,
    *,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Paired cluster-bootstrap of ``MAE(pred) - MAE(ref)`` (same resampled bubbles).

    Returns ``(delta_point, ci_lo, ci_hi)``. ``pred`` BEATS ``ref`` iff the whole CI
    is < 0 (improvement outside the CI). This is the correct "beats persistence"
    test — marginal-CI overlap is only a conservative proxy.
    """
    def _delta(idx):
        return mae(pred[idx], target[idx]) - mae(ref[idx], target[idx])

    point = _delta(np.arange(len(target)))
    lo, hi = cluster_bootstrap_ci(_delta, bubble_of, n_boot, seed=seed)
    return (point, lo, hi)


@dataclass
class BaselineResult:
    horizon: int
    test_foam: str
    subset: str            # "all" | "quiescent" | "dynamic"
    method: str
    n_samples: int
    n_bubbles: int
    mae: float
    ci_lo: float
    ci_hi: float
    delta_vs_persist: float = 0.0    # MAE(method) - MAE(persistence); <0 = better
    delta_ci_lo: float = 0.0
    delta_ci_hi: float = 0.0
    beats_persist: bool = False      # True iff delta CI entirely < 0


def evaluate_baselines(
    trusted: pd.DataFrame,
    cfg: PipelineConfig,
    *,
    seed: int = 0,
) -> pd.DataFrame:
    """Full Stage-1 baseline table under leave-one-foam-out.

    For each horizon × held-out foam × subset (all/quiescent/dynamic) × method
    (persistence, global_mean, per_bubble_linear): MAE (px²/s) of the areal-rate
    prediction with a cluster-bootstrap 95% CI (resampling ``bubble_uid``).
    ``global_mean`` is fit on the *training* foams only.
    """
    seg_flags = segment_dynamic_flags(trusted, cfg).set_index("seg_uid")["dynamic"].to_dict()
    folds = lofo_folds(trusted)
    out: list[dict] = []
    for h in cfg.eval.rollout_horizons:
        samples = make_horizon_samples(trusted, h)
        if samples.empty:
            continue
        samples = samples.assign(dynamic=samples["seg_uid"].map(seg_flags).astype(bool))
        for fold in folds:
            test_foam = fold["test_foam"]
            tr = samples[samples["foam"].isin(fold["train_foams"])]
            te_all = samples[samples["foam"] == test_foam]
            if te_all.empty:
                continue
            train_mean = float(tr["target_dadt"].mean()) if len(tr) else 0.0
            for subset in ("all", "quiescent", "dynamic"):
                te = te_all if subset == "all" else te_all[te_all["dynamic"] == (subset == "dynamic")]
                if te.empty:
                    continue
                target = te["target_dadt"].to_numpy(dtype=float)
                bub = te["bubble_uid"].to_numpy()
                ref = predict_persistence(te)
                preds = {
                    "persistence": ref,
                    "global_mean": predict_global_mean(te, train_mean),
                    "per_bubble_linear": predict_per_bubble_linear(te),
                }
                for method, pred in preds.items():
                    point = mae(pred, target)
                    ci = cluster_bootstrap_ci(
                        lambda idx, p=pred: mae(p[idx], target[idx]),
                        bub, cfg.eval.n_bootstrap, seed=seed)
                    if method == "persistence":
                        d_pt, d_lo, d_hi = 0.0, 0.0, 0.0
                    else:
                        d_pt, d_lo, d_hi = paired_delta_ci(
                            pred, ref, target, bub, cfg.eval.n_bootstrap, seed=seed)
                    out.append(vars(BaselineResult(
                        h, test_foam, subset, method, int(len(te)),
                        int(pd.Series(bub).nunique()), point, ci[0], ci[1],
                        d_pt, d_lo, d_hi, bool(method != "persistence" and d_hi < 0))))
    return pd.DataFrame(out)
