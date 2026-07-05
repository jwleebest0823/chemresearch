"""
foam_gnn.stability
==================
Select the **trusted-identity** subset of bubbles for downstream physics, and the
gate diagnostics that decide whether a radial-gradient test on that subset is even
interpretable.

Assumptions / what this is and is NOT
-------------------------------------
* "Trusted" means **the tracker follows this bubble's identity reliably** — it is
  NOT "big bubble". We never threshold on instantaneous area, so small trusted
  bubbles are kept and the *instantaneous* size distribution is not left-truncated.
* BUT persistence selection is **survivorship selection**: bubbles that vanish fast
  (skewing small) are dropped. So the trusted set is NOT an unbiased sample for
  absolute coarsening (⟨R⟩, β) — never report those from it. It is valid for a
  *within-set* radial comparison, and only if survivorship does not confound radius
  (see :func:`stability_gates`, Condition 1).
* Only bubbles present in the initial segmentation (``bubble_id <= frame0_max_id``)
  are eligible: every later ID is a reorganization-birth artifact ("bubbles never
  appear"). A trusted segment is a maximal consecutive run of a frame-0 ID with no
  frame gap, no merge, and a continuous area trajectory, length ≥
  ``min_persist_frames``.

Shapes / dtypes
---------------
``node_table`` : tidy ``pd.DataFrame`` with columns
    ``frame | time_seconds | bubble_id | area | n_sides | distance_to_evap_edge
      | cx | cy`` (cx/cy are registered/common-frame px).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .graph import build_session_graphs
from .segmentation import SegmentationResult
from .tracking import TrackingResult

__all__ = [
    "NODE_TABLE_COLUMNS",
    "build_node_table",
    "StableSelection",
    "select_stable_tracks",
    "stability_gates",
]

NODE_TABLE_COLUMNS = ["frame", "time_seconds", "bubble_id", "area", "n_sides",
                      "distance_to_evap_edge", "cx", "cy"]


def build_node_table(
    results: list[SegmentationResult],
    tracking: TrackingResult,
    cfg: PipelineConfig,
    *,
    times_seconds: list[float] | None = None,
) -> pd.DataFrame:
    """Flatten per-frame graphs to a tidy per-(frame, bubble) table.

    Reuses :func:`foam_gnn.graph.build_session_graphs` so ``n_sides`` and
    ``distance_to_evap_edge`` are computed exactly as in the CSV export. ``cx``/``cy``
    are the **registered** (common-frame) centroids (drift removed) so that
    "stationary" means physically stationary.
    """
    graphs = build_session_graphs(results, tracking, cfg, times_seconds=times_seconds)
    rows: list[dict] = []
    for t, G in enumerate(graphs):
        tsec = float(G.graph["time_seconds"])
        for bid, a in G.nodes(data=True):
            rows.append({
                "frame": t, "time_seconds": tsec, "bubble_id": int(bid),
                "area": float(a["area"]), "n_sides": int(a["n_sides"]),
                "distance_to_evap_edge": float(a["distance_to_evap_edge"]),
                "cx": float(a["centroid_x"]), "cy": float(a["centroid_y"]),
            })
    return pd.DataFrame(rows, columns=NODE_TABLE_COLUMNS)


@dataclass
class StableSelection:
    """Output of :func:`select_stable_tracks`.

    trusted_rows : node-table rows belonging to a trusted segment, tagged
        ``segment_id``. One row per (frame, bubble) in a kept segment.
    segments : one row per trusted segment — ``bubble_id, segment_id, start_frame,
        end_frame, n_frames, dist_mid, dist_spread, dist_jitter_frac, moved_px``.
    eligible_survival : one row per eligible (frame-0) bubble — ``bubble_id,
        survived, n_trusted_frames, dist0`` (distance at frame 0). Feeds the
        survival-vs-distance confound gate.
    stats : counts / fractions (count and AREA retained).
    """

    trusted_rows: pd.DataFrame
    segments: pd.DataFrame
    eligible_survival: pd.DataFrame
    stats: dict = field(default_factory=dict)


def _merge_break_frames(tracking: TrackingResult) -> dict[int, set[int]]:
    """Frames at which a merge changes a bubble's identity/area (break points)."""
    out: dict[int, set[int]] = {}
    for e in tracking.events:
        if e.kind != "merge":
            continue
        for bid in e.bubble_ids:                    # survivor + merged parents
            out.setdefault(int(bid), set()).add(int(e.frame))
    return out


def select_stable_tracks(
    node_table: pd.DataFrame,
    tracking: TrackingResult,
    cfg: PipelineConfig,
) -> StableSelection:
    """Split each eligible bubble's history into trusted segments.

    A break is placed at: a frame gap (>1), a merge frame for that bubble, or a
    ``|Δ log area| > area_jump_tol`` step. Runs of ≥ ``min_persist_frames`` frames
    survive. No instantaneous-size threshold is applied.
    """
    for c in NODE_TABLE_COLUMNS:
        if c not in node_table.columns:
            raise ValueError(f"node_table missing column {c!r}")
    if np.isinf(node_table["area"].to_numpy(dtype=float)).any():
        raise ValueError("node_table.area contains Inf")

    scfg = cfg.stability
    if scfg.origin_rule != "frame0":
        raise ValueError(f"unsupported origin_rule {scfg.origin_rule!r}")
    frame0_max = int(tracking.diagnostics.get("frame0_max_id", 0))
    tol, n_min = scfg.area_jump_tol, scfg.min_persist_frames
    merge_breaks = _merge_break_frames(tracking)

    eligible = node_table[node_table["bubble_id"] <= frame0_max]
    seg_rows: list[dict] = []
    trusted_blocks: list[tuple[np.ndarray, int]] = []   # (row indices, segment_id)
    surv_rows: list[dict] = []
    seg_id = 0
    for bid, g in eligible.groupby("bubble_id"):
        g = g.sort_values("frame")
        frames = g["frame"].to_numpy()
        area = g["area"].to_numpy(dtype=float)
        idx = g.index.to_numpy()
        mbreak = merge_breaks.get(int(bid), set())
        # break indices: start a new run whenever continuity is violated
        starts = [0]
        for i in range(1, len(frames)):
            gap = frames[i] - frames[i - 1] != 1
            merged = int(frames[i]) in mbreak
            jump = abs(np.log(max(area[i], 1e-9) / max(area[i - 1], 1e-9))) > tol
            if gap or merged or jump:
                starts.append(i)
        starts.append(len(frames))

        n_trusted_frames = 0
        for s, e in zip(starts[:-1], starts[1:]):
            if e - s < n_min:
                continue
            sl = slice(s, e)
            rows_idx = idx[sl]
            trusted_blocks.append((rows_idx, seg_id))
            gg = g.loc[rows_idx]
            dist = gg["distance_to_evap_edge"].to_numpy(dtype=float)
            cx, cy = gg["cx"].to_numpy(dtype=float), gg["cy"].to_numpy(dtype=float)
            moved = float(np.hypot(cx.max() - cx.min(), cy.max() - cy.min()))
            dmean = float(dist.mean())
            seg_rows.append({
                "bubble_id": int(bid), "segment_id": seg_id,
                "start_frame": int(frames[s]), "end_frame": int(frames[e - 1]),
                "n_frames": int(e - s), "dist_mid": dmean,
                "dist_spread": float(dist.max() - dist.min()),
                "dist_jitter_frac": float(dist.std() / dmean) if dmean > 0 else float("nan"),
                "moved_px": moved,
            })
            n_trusted_frames += int(e - s)
            seg_id += 1

        dist0 = float(g.iloc[0]["distance_to_evap_edge"])
        surv_rows.append({"bubble_id": int(bid), "survived": n_trusted_frames > 0,
                          "n_trusted_frames": n_trusted_frames, "dist0": dist0})

    if trusted_blocks:
        all_idx = np.concatenate([b for b, _ in trusted_blocks])
        seg_ids = np.concatenate([np.full(len(b), sid) for b, sid in trusted_blocks])
        trusted_rows = node_table.loc[all_idx].copy()
        trusted_rows["segment_id"] = seg_ids
    else:
        trusted_rows = node_table.iloc[0:0].copy()
        trusted_rows["segment_id"] = pd.Series(dtype=int)
    segments = pd.DataFrame(seg_rows, columns=[
        "bubble_id", "segment_id", "start_frame", "end_frame", "n_frames",
        "dist_mid", "dist_spread", "dist_jitter_frac", "moved_px"])
    eligible_survival = pd.DataFrame(surv_rows, columns=["bubble_id", "survived",
                                                         "n_trusted_frames", "dist0"])

    total_rows = len(node_table)
    total_area = float(node_table["area"].sum())
    trusted_area = float(trusted_rows["area"].sum()) if len(trusted_rows) else 0.0
    n_unique = int(node_table["bubble_id"].nunique())
    n_trusted_bubbles = int(segments["bubble_id"].nunique()) if len(segments) else 0
    stats = {
        "n_eligible_bubbles": int(len(eligible_survival)),
        "n_trusted_bubbles": n_trusted_bubbles,
        "n_segments": int(len(segments)),
        "n_unique_bubbles_total": n_unique,
        "frac_bubbles_trusted": n_trusted_bubbles / n_unique if n_unique else 0.0,
        "frac_rows_trusted": len(trusted_rows) / total_rows if total_rows else 0.0,
        "frac_area_trusted": trusted_area / total_area if total_area else 0.0,
    }
    return StableSelection(trusted_rows, segments, eligible_survival, stats)


def stability_gates(sel: StableSelection, cfg: PipelineConfig) -> dict:
    """Pre-condition gates that decide if a radial test is interpretable.

    Computes (Condition 1) survival-vs-distance Spearman with a bootstrap CI —
    if strong, near-edge bubbles are systematically under-retained and a null
    radial result is CONFOUNDED, not "no gradient"; (Condition 2) the
    distance-to-edge jitter of ~stationary trusted bubbles; radial-bin occupancy;
    and (D1) the trusted-bubble-count power gate. Returns a decision string plus
    the numbers behind it — the analysis is halted/flagged, never silently run.
    """
    from scipy.stats import spearmanr

    scfg, ecfg = cfg.stability, cfg.eval
    surv = sel.eligible_survival
    reasons: list[str] = []

    # ── D1 / power gate ──────────────────────────────────────────────────── #
    n_trusted = sel.stats["n_trusted_bubbles"]
    underpowered = n_trusted < scfg.min_trusted_bubbles
    if underpowered:
        reasons.append(f"only {n_trusted} trusted bubbles (< {scfg.min_trusted_bubbles})")

    # ── Condition 1: survival vs distance-to-edge ────────────────────────── #
    rho_surv = ci_surv = float("nan")
    confounded = False
    if len(surv) >= 5 and surv["survived"].nunique() > 1:
        d = surv["dist0"].to_numpy(dtype=float)
        s = surv["survived"].to_numpy(dtype=float)
        rho_surv = float(spearmanr(d, s).correlation)
        rng = np.random.default_rng(0)
        boot = []
        for _ in range(ecfg.n_bootstrap):
            j = rng.integers(0, len(d), len(d))
            if np.unique(s[j]).size > 1 and np.unique(d[j]).size > 1:
                boot.append(spearmanr(d[j], s[j]).correlation)
        ci_surv = (float(np.nanpercentile(boot, 2.5)), float(np.nanpercentile(boot, 97.5))) \
            if boot else (float("nan"), float("nan"))
        confounded = abs(rho_surv) > scfg.survival_confound_rho
        if confounded:
            reasons.append(f"survival correlates with distance (Spearman ρ={rho_surv:+.2f})")

    # ── Condition 2: x-axis (distance) reliability ───────────────────────── #
    seg = sel.segments
    stationary = seg[seg["moved_px"] <= cfg.track.max_displacement_px] if len(seg) else seg
    median_jitter = float(stationary["dist_jitter_frac"].median()) if len(stationary) else float("nan")
    noisy_xaxis = bool(np.isfinite(median_jitter) and median_jitter > scfg.distance_jitter_frac)
    if noisy_xaxis:
        reasons.append(f"distance-to-edge jitter {median_jitter:.2f} > {scfg.distance_jitter_frac}")

    # ── radial-bin occupancy (near-edge representation) ──────────────────── #
    occupancy = {}
    near_edge_empty = False
    if len(seg):
        dmax = float(seg["dist_mid"].max())
        edges = np.linspace(0.0, dmax + 1e-9, ecfg.radial_bins + 1)
        b = np.digitize(seg["dist_mid"].to_numpy(dtype=float), edges) - 1
        b = np.clip(b, 0, ecfg.radial_bins - 1)
        occupancy = {int(k): int(v) for k, v in zip(*np.unique(b, return_counts=True))}
        near_edge_empty = occupancy.get(0, 0) < scfg.min_bubbles_per_bin

    decision = "proceed"
    if underpowered or (len(seg) and near_edge_empty):
        decision = "underpowered"
    if confounded:
        decision = "confounded"

    return {
        "decision": decision, "reasons": reasons,
        "n_trusted_bubbles": n_trusted, "underpowered": underpowered,
        "survival_distance_rho": rho_surv, "survival_distance_ci": ci_surv,
        "confounded": confounded,
        "distance_jitter_median_frac": median_jitter, "noisy_xaxis": noisy_xaxis,
        "radial_bin_occupancy": occupancy, "near_edge_underrepresented": near_edge_empty,
    }
