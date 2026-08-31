"""
foam_gnn.propagate
==================
**Identity-propagating segmentation** — a temporally-coupled segmenter that attacks
the project's binding failure directly: *temporal identity stability of small and
near-edge bubbles*, not per-frame boundary quality (Plateau is already ~99%).

The idea (v2 — after the ratchet defect; see docs/propagation_ratchet_defect.md)
--------------------------------------------------------------------------------
**v1 propagated GEOMETRY and that was a one-way ratchet.** Seeding frame *t+1* from
frame *t*'s label map let a marker come to own several bubbles, and nothing could
ever split it apart, so under-segmentation compounded monotonically (Foam A:
385 → 104 bubbles while an independent per-frame segmentation of the same frames
found 219; one label swallowed up to 34 bubbles by frame 12).

**v2 propagates IDENTITY onto geometry that is re-derived every frame**, under one
invariant:

> **Every interior blob receives exactly one marker.**

A marker therefore cannot span two bubbles, so swallowing is structurally impossible
and splits happen automatically. Identity is then assigned per blob by pixel overlap
with the drift-warped previous stable map:

* one dominant previous id            → that id (**identity preserved** — the point of propagation)
* ≥2 previous ids share one blob      → **merge** (``keep_larger`` by previous area);
  the loser goes **dormant**, and the merge event is only emitted after it survives
  ``probation_frames`` (so merge-flicker costs nothing)
* one previous id spans ≥2 blobs      → **split**: it keeps its best-overlap blob and
  the others are resolved as below
* no previous id                      → new bubble

**Geometry vs identity (the key decision).** Geometry splits are *ungated* — two blobs
separated by film in this frame ARE two regions. Only the *identity* decision is gated,
since only it can manufacture churn: **resurrect** a dormant id first (costs zero
churn), else require either a strong separating ridge (``split_film_thresh`` >
``interior_thresh``, a hysteresis band that stops borderline films oscillating between
merge and split) or ``probation_frames`` of persistence before minting a new id. A
provisional id whose separation does not survive probation is retired **retroactively**,
so it never appears as a reorganization birth.

A **collapse guard** compares the region count to the independent interior-blob count
every frame and fails loud on the ratchet signature.

Output
------
:func:`segment_track_propagated` returns ``(results, tracking)`` in the SAME types
as the independent pipeline (:class:`~foam_gnn.segmentation.SegmentationResult` list
+ :class:`~foam_gnn.tracking.TrackingResult`), so ``foam_gnn.seg_temporal`` /
``stability`` / ``graph`` consume it unchanged — the comparison against the Task-3
baseline is apples-to-apples.

Shapes: images uint8 ``(H, W)``; label maps int32 ``(H, W)`` in **stable-ID** space.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.morphology import h_maxima
from skimage.registration import phase_cross_correlation
from skimage.segmentation import find_boundaries, watershed

from .config import PipelineConfig
from .guards import check_array
from .segmentation import SegmentationResult, compute_foam_mask, preprocess
from .tracking import TopologicalEvent, TrackingResult

__all__ = ["FrameLayers", "compute_frame_layers", "segment_track_propagated"]


class FrameLayers:
    """Per-frame intermediate maps shared by seeding + watershed."""

    __slots__ = ("clean", "foam", "dist_to_edge", "film", "interior", "dt", "raw")

    def __init__(self, clean, foam, dist_to_edge, film, interior, dt, raw=None):
        self.raw = raw
        self.clean = clean
        self.foam = foam
        self.dist_to_edge = dist_to_edge
        self.film = film
        self.interior = interior
        self.dt = dt


def compute_frame_layers(img: np.ndarray, cfg: PipelineConfig) -> FrameLayers:
    """Preprocess one frame into (clean, foam, dist_to_edge, film[0,1], interior, dt)."""
    check_array("propagate.img", img, ndim=2, dtype=np.uint8)
    seg = cfg.seg
    clean = preprocess(img, cfg.preproc)
    foam, dist = compute_foam_mask(img, cfg.boundary)
    if foam.sum() == 0:
        raise RuntimeError("foam mask empty: boundary detection failed for this frame")
    film = sato(clean.astype(np.float64), sigmas=seg.sato_sigmas, black_ridges=True)
    film = (film - film.min()) / (float(np.ptp(film)) + 1e-9)
    interior = ndi.binary_opening((film < seg.interior_thresh) & foam, structure=np.ones((3, 3)))
    dt = ndi.gaussian_filter(ndi.distance_transform_edt(interior), seg.dt_smooth_sigma)
    return FrameLayers(clean, foam, dist.astype(np.float32), film.astype(np.float32),
                       interior, dt.astype(np.float32), raw=img)


def _counts(labels: np.ndarray, maxid: int) -> np.ndarray:
    return np.bincount(labels.ravel(), minlength=maxid + 1)


def _unseeded_blob_seeds(interior, dt, seed_markers, start_id, min_area):
    """One marker per interior connected-component that has NO seed yet.

    This is the ADAPTIVE small-bubble rule done right: an interior blob (a filmless
    region = one bubble, films excluded) either already contains a seed (large bubble
    with an h_maxima seed, or a propagated bubble's core) → skip, or it does not (a
    small bubble a global h_maxima misses, or a genuinely new bubble) → give it ONE
    seed at its distance-transform maximum. One-per-blob CANNOT over-segment a large
    bubble (its blob is already seeded) — the failure mode of per-dt-peak seeding.

    Returns ``(point_marker_map int32 labeled start_id.., next_id)``.
    """
    markers = np.zeros(dt.shape, np.int32)
    lab, n = ndi.label(interior)
    if n == 0:
        return markers, start_id
    seeded_blobs = {int(v) for v in np.unique(lab[seed_markers > 0]) if v > 0}
    nid = start_id
    for blob, sl in enumerate(ndi.find_objects(lab), start=1):
        if sl is None or blob in seeded_blobs:
            continue
        m = lab[sl] == blob
        if int(m.sum()) < min_area:
            continue
        sub = dt[sl] * m
        iy, ix = np.unravel_index(int(np.argmax(sub)), sub.shape)
        markers[sl[0].start + iy, sl[1].start + ix] = nid
        nid += 1
    return markers, nid


def _seed_frame0(layers: FrameLayers, cfg: PipelineConfig, interior: np.ndarray | None = None):
    """Frame-0 markers = global h_maxima seeds (splits touching bubbles) + one seed for
    every interior blob a global h_maxima misses (small bubbles).

    ``interior`` overrides ``layers.interior`` — pass the TIGHT-masked interior so the
    generous foam mask's flat background rim is not seeded as a bubble.
    """
    seg = cfg.seg
    inter = layers.interior if interior is None else interior
    base = h_maxima(layers.dt, seg.h_maxima) * (layers.foam if interior is None else interior)
    markers, n_base = ndi.label(base)
    markers = markers.astype(np.int32)
    extra, _ = _unseeded_blob_seeds(inter, layers.dt, markers,
                                    n_base + 1, seg.min_bubble_area_px)
    return np.where(extra > 0, extra, markers)


def _area_filter_relabel(labels: np.ndarray, min_area: int) -> np.ndarray:
    """Drop regions below ``min_area`` and relabel remaining to contiguous 1..K int32."""
    out = np.zeros(labels.shape, np.int32)
    k = 0
    for r in range(1, int(labels.max()) + 1):
        m = labels == r
        if int(m.sum()) >= min_area:
            k += 1
            out[m] = k
    return out


def _estimate_drift(foam_prev: np.ndarray, foam_curr: np.ndarray, cfg) -> tuple[float, float]:
    """(dy, dx) to shift a frame-(t-1) map into frame-t coordinates (phase corr)."""
    pcfg = cfg.propagate
    try:
        shift, _err, _phase = phase_cross_correlation(
            foam_curr.astype(np.float32), foam_prev.astype(np.float32),
            upsample_factor=pcfg.drift_upsample)
        dy, dx = float(shift[0]), float(shift[1])
    except Exception:
        return 0.0, 0.0
    if not (np.isfinite(dy) and np.isfinite(dx)) or max(abs(dy), abs(dx)) > pcfg.drift_max_px:
        return 0.0, 0.0
    return dy, dx


def _region_props(labels: np.ndarray) -> dict[int, tuple[int, float, float]]:
    """{id: (area, cx, cy)} native centroids, via find_objects (bbox-limited)."""
    out: dict[int, tuple[int, float, float]] = {}
    objs = ndi.find_objects(labels)
    for lab, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sub = labels[sl] == lab
        area = int(sub.sum())
        if area == 0:
            continue
        ys, xs = np.nonzero(sub)
        out[lab] = (area, float(xs.mean() + sl[1].start), float(ys.mean() + sl[0].start))
    return out


def _tight_flood_mask(layers: FrameLayers, dilate_px: int) -> np.ndarray:
    """Foam mask tightened to a hull of the detected interiors (bleed fix).

    ``compute_foam_mask`` is deliberately generous (measured <= 11.2 px past the
    outermost interior); watershed assigns EVERY masked pixel to a label, so that rim
    became label territory on background. Flooding on ``foam & fill_holes(dilate(
    interior, r))`` keeps the films (which are not "interior") while dropping the
    background rim. bool (H, W).
    """
    hull = ndi.binary_fill_holes(ndi.binary_dilation(layers.interior, iterations=dilate_px))
    return layers.foam & hull


def _blob_prev_overlaps(blobs: np.ndarray, n_blobs: int, Lw: np.ndarray) -> dict[int, dict[int, int]]:
    """``{blob_label: {previous_stable_id: overlap_px}}`` in one vectorized pass."""
    maxid = int(Lw.max())
    if n_blobs == 0 or maxid == 0:
        return {}
    m = (blobs > 0) & (Lw > 0)
    if not m.any():
        return {}
    key = (blobs[m].astype(np.int64) - 1) * (maxid + 1) + Lw[m].astype(np.int64)
    cnt = np.bincount(key, minlength=n_blobs * (maxid + 1))
    out: dict[int, dict[int, int]] = {}
    for k in np.nonzero(cnt)[0]:
        b, i = divmod(int(k), maxid + 1)
        out.setdefault(b + 1, {})[i] = int(cnt[k])
    return out


def _pair_ridge(blobs: np.ndarray, film: np.ndarray, slices, b1: int, b2: int,
                dilate: int = 3) -> float:
    """Mean film ridge on the interface between two interior blobs (NaN if disjoint).

    Cropped to the union bounding box. Used for the split hysteresis: a blob boundary
    only guarantees film >= interior_thresh, so a *confident* split needs a stronger
    ridge than that (see PropagateConfig.split_film_thresh).
    """
    s1, s2 = slices[b1 - 1], slices[b2 - 1]
    if s1 is None or s2 is None:
        return float("nan")
    y0 = max(min(s1[0].start, s2[0].start) - dilate - 1, 0)
    y1 = min(max(s1[0].stop, s2[0].stop) + dilate + 1, blobs.shape[0])
    x0 = max(min(s1[1].start, s2[1].start) - dilate - 1, 0)
    x1 = min(max(s1[1].stop, s2[1].stop) + dilate + 1, blobs.shape[1])
    sub = blobs[y0:y1, x0:x1]
    m1 = ndi.binary_dilation(sub == b1, iterations=dilate)
    m2 = ndi.binary_dilation(sub == b2, iterations=dilate)
    inter = m1 & m2
    if not inter.any():
        return float("nan")
    return float(film[y0:y1, x0:x1][inter].mean())


def _intensity_threshold(layers: FrameLayers, cfg: PipelineConfig) -> float | None:
    """Per-frame gas/liquid split: ``intensity_gate_frac`` x Otsu(raw within foam).

    Returns None when the gate is disabled or cannot be computed (fail-safe: callers
    then apply no gate rather than silently discarding regions).
    """
    frac = cfg.propagate.intensity_gate_frac
    if frac <= 0.0 or layers.raw is None:
        return None
    from skimage.filters import threshold_otsu

    vals = layers.raw[layers.foam]
    if vals.size < 16 or float(np.ptp(vals)) < 1e-6:
        return None
    try:
        return float(threshold_otsu(vals)) * float(frac)
    except Exception:
        return None



def _reject_plateau_borders(labels: np.ndarray, layers: FrameLayers,
                            cfg: PipelineConfig) -> np.ndarray:
    """Drop whole regions that are LIQUID (Plateau borders), keeping GAS (bubbles).

    The Sato ridge filter responds to thin films but not to the fat triangular
    interstices where three bubbles meet, so those pass ``film < interior_thresh`` and
    are emitted as bubbles (measured: ~2 spurious regions per real bubble, precision
    0.347 against hand-labeled ground truth). A bubble interior is gas and BRIGHT; a
    Plateau border is liquid and DARK, so a per-region mean-intensity gate separates
    them. Threshold = ``intensity_gate_frac`` x Otsu(raw within foam), per frame.

    Returns the label map with rejected regions set to 0 (NOT relabeled — ids are
    stable identities and must not be renumbered). Fail-safe: if the raw frame is
    unavailable, Otsu is degenerate, or the gate is disabled, returns ``labels``
    unchanged rather than silently discarding data.
    """
    thr = _intensity_threshold(layers, cfg)
    if thr is None or labels.max() == 0:
        return labels
    ids = list(range(1, int(labels.max()) + 1))
    means = ndi.mean(layers.raw, labels, ids)
    drop = [i for i, m in zip(ids, np.atleast_1d(means)) if np.isfinite(m) and m < thr]
    if not drop:
        return labels
    out = labels.copy()
    out[np.isin(labels, drop)] = 0
    return out


def segment_track_propagated(
    images: list[np.ndarray],
    cfg: PipelineConfig,
) -> tuple[list[SegmentationResult], TrackingResult]:
    """Identity-propagating segmentation of one contiguous run (ratchet-free).

    Algorithm (see the module docstring and docs/propagation_ratchet_defect.md)
    ---------------------------------------------------------------------------
    Per frame: decompose the current frame's ``interior`` into blobs, give **every blob
    exactly one marker** (the invariant that makes the ratchet structurally impossible),
    and assign that marker an *identity* by pixel overlap with the drift-warped previous
    stable map. Geometry is therefore re-derived from the current frame every frame;
    only identity is inherited. Splits are ungated in geometry and gated in identity
    (resurrect a dormant id -> else probation -> else mint a new id).

    Parameters
    ----------
    images : ordered uint8 ``(H, W)`` frames of ONE contiguous tracking run.

    Returns
    -------
    (results, tracking)
        ``results`` : per-frame :class:`SegmentationResult` with labels in stable-ID
        space. ``tracking`` : :class:`TrackingResult` with ``id_maps``,
        ``correspondence`` (rebuilt from the FINAL maps, after retroactive retirement
        of probation ids), ``events`` (birth / merge / T2_disappear), ``frame_offsets``
        and ``diagnostics`` — including ``blob_ratio_min`` and the per-frame
        ``n_regions``/``n_blobs`` series behind the collapse guard.

    Raises
    ------
    RuntimeError
        If the collapse guard trips (region count falls below
        ``collapse_guard_ratio`` x the independent interior-blob count for
        ``collapse_guard_patience`` consecutive frames) and ``collapse_guard="raise"``.
    """
    import pandas as pd

    if not images:
        raise ValueError("no images")
    seg, pcfg = cfg.seg, cfg.propagate
    if not (0.0 <= pcfg.collapse_guard_ratio <= 1.0):
        raise ValueError(f"collapse_guard_ratio must be in [0,1], got {pcfg.collapse_guard_ratio}")
    if pcfg.split_film_thresh <= seg.interior_thresh:
        raise ValueError(
            f"split_film_thresh ({pcfg.split_film_thresh}) must exceed "
            f"interior_thresh ({seg.interior_thresh}) or splits/merges oscillate")

    # ── frame 0: the independent segmentation defines the initial identities ──
    layers0 = compute_frame_layers(images[0], cfg)
    flood0 = _tight_flood_mask(layers0, pcfg.tight_mask_dilate_px)
    # DECISION: `interior` must be intersected with the TIGHT mask, not just the
    # flooding. `interior` = (film < thresh) & foam, and the generous foam mask's flat
    # background rim is film-free -> it would register as an interior blob and be
    # seeded as a bubble on every frame. Masking here fixes the bleed at its source.
    interior0 = layers0.interior & flood0
    # DECISION: frame 0 obeys the SAME one-marker-per-blob invariant as every other
    # frame. Seeding it differently (h_maxima + unseeded blobs) left frame 0
    # under-segmented relative to its own blobs, and the invariant then correctly but
    # noisily split that apart over the next frames — a transient storm of "births"
    # that is an artifact of the inconsistent frame-0 rule, not real topology.
    markers0, _ = _unseeded_blob_seeds(interior0, layers0.dt, np.zeros(interior0.shape, np.int32),
                                       1, seg.min_bubble_area_px)
    L = _area_filter_relabel(
        _reject_plateau_borders(watershed(layers0.film, markers0, mask=flood0), layers0, cfg),
        seg.min_bubble_area_px)
    frame0_max = int(L.max())
    id_next = frame0_max + 1

    id_maps: list[np.ndarray] = [L]
    results = [SegmentationResult(L, layers0.foam, layers0.dist_to_edge, int(L.max()),
                                  meta={"backend": "propagate_v2"})]
    events: list[TopologicalEvent] = []
    frame_offsets: list[tuple[float, float]] = [(0.0, 0.0)]
    cum_x = cum_y = 0.0

    dormant: dict[int, dict] = {}          # id -> {frame, sl, mask, parent}
    provisional: dict[int, dict] = {}      # id -> {parent, since, frames[]}
    pending_merge: dict[int, dict] = {}    # loser id -> {survivor, frame}
    pending_death: dict[int, int] = {}     # vanished id -> frame it vanished
    diag = {"n_births_remaining": 0, "n_merge_events": 0, "n_T2": 0,
            "n_splits": 0, "n_resurrections": 0, "n_probation_retired": 0}
    n_regions_series: list[int] = [int(L.max())]
    _b0lab, _b0n = ndi.label(interior0)
    _b0a = np.bincount(_b0lab.ravel())
    _b0e = _b0a[1:] >= seg.min_bubble_area_px
    _thr0 = _intensity_threshold(layers0, cfg)
    if _thr0 is not None and _b0n > 0:
        _b0m = np.atleast_1d(ndi.mean(layers0.raw, _b0lab, list(range(1, _b0n + 1))))
        _b0e = _b0e & (np.nan_to_num(_b0m, nan=0.0) >= _thr0)
    n_blobs_series: list[int] = [int(_b0e.sum())]
    sep_durations: list[int] = []          # split->remerge, for measuring W
    prev_layers = layers0
    below = 0
    ratio0: float | None = None
    n_min = int(L.max())          # running minimum region count (fragmentation guard)
    above = 0

    for t in range(1, len(images)):
        layers = compute_frame_layers(images[t], cfg)
        dy, dx = _estimate_drift(prev_layers.foam, layers.foam, cfg)
        cum_x += dx
        cum_y += dy
        frame_offsets.append((cum_x, cum_y))
        Lw = ndi.shift(L, shift=(dy, dx), order=0, mode="constant", cval=0).astype(np.int32)
        flood = _tight_flood_mask(layers, pcfg.tight_mask_dilate_px)

        interior = layers.interior & flood        # tight-masked (see frame-0 note)
        blobs, n_blobs = ndi.label(interior)
        blob_slices = ndi.find_objects(blobs)
        blob_area = np.bincount(blobs.ravel(), minlength=n_blobs + 1)
        # Blobs too small to be a bubble are never seeded; the guard's reference is
        # these ELIGIBLE blobs. NOTE the reference is deliberately NOT intensity-gated:
        # a spurious Plateau-border region grows from a small BRIGHT speck, so its blob
        # core looks like a bubble and only the post-watershed region reveals it as
        # liquid. The guard therefore compares against a reference that includes those,
        # and uses a RELATIVE criterion (below) so a constant rejection rate is not
        # mistaken for a collapse.
        n_blobs_eligible = int((blob_area[1:] >= seg.min_bubble_area_px).sum())
        overlaps = _blob_prev_overlaps(blobs, n_blobs, Lw)
        prev_area = _counts(L, int(L.max()))

        # eroded cores of the warped previous labels (used as markers where big enough)
        bnd = ndi.binary_dilation(find_boundaries(Lw, mode="outer"), iterations=pcfg.erode_seed_px)
        eroded = np.where(~bnd, np.where(interior, Lw, 0), 0).astype(np.int32)

        # ── 1. candidate claims per blob ────────────────────────────────────────
        claims: dict[int, list[tuple[int, int]]] = {}      # prev id -> [(blob, px)]
        blob_assign: dict[int, int] = {}                    # blob -> assigned id
        unclaimed: list[int] = []
        merge_losers: dict[int, int] = {}                   # loser -> survivor
        for b in range(1, n_blobs + 1):
            if blob_area[b] < seg.min_bubble_area_px:
                continue
            ov = overlaps.get(b, {})
            cands = [(i, px) for i, px in ov.items() if px >= pcfg.claim_min_px]
            if not cands:
                unclaimed.append(b)
                continue
            if len(cands) >= 2:
                # MERGE: >=2 previously distinct ids now share one filmless region.
                # keep_larger by PREVIOUS area (physical continuity of the big bubble).
                survivor = max(cands, key=lambda c: (int(prev_area[c[0]]) if c[0] < len(prev_area) else 0, c[0]))[0]
                for i, _px in cands:
                    if i != survivor:
                        merge_losers[i] = survivor
                blob_assign[b] = survivor
                claims.setdefault(survivor, []).append((b, dict(cands)[survivor]))
            else:
                i, px = cands[0]
                blob_assign[b] = i
                claims.setdefault(i, []).append((b, px))

        # ── 2. SPLIT: one id claiming several blobs keeps only its best blob ─────
        split_offs: list[tuple[int, int, int]] = []         # (blob, parent id, kept blob)
        for i, blist in claims.items():
            if len(blist) < 2:
                continue
            blist.sort(key=lambda bp: -bp[1])
            keep_blob = blist[0][0]
            for b, _px in blist[1:]:
                blob_assign.pop(b, None)
                split_offs.append((b, i, keep_blob))
                diag["n_splits"] += 1

        # ── 3. identity for split-offs and unclaimed blobs ──────────────────────
        #      resurrect (zero churn) -> probation (faint ridge) -> new id
        def _resurrect(b: int) -> int | None:
            best, best_ov = None, 0.0
            for did, d in dormant.items():
                sub = blobs[d["sl"]] == b
                if not sub.any():
                    continue
                ov = float((sub & d["mask"]).sum())
                frac = ov / max(float(blob_area[b]), 1.0)
                if frac >= pcfg.resurrect_min_overlap_frac and ov > best_ov:
                    best, best_ov = did, ov
            return best

        for b, parent, keep_b in split_offs:
            rid = _resurrect(b)
            if rid is not None:
                blob_assign[b] = rid
                dormant.pop(rid, None)
                pending_merge.pop(rid, None)          # merge was flicker -> cancel it
                pending_death.pop(rid, None)          # ...as was the disappearance
                diag["n_resurrections"] += 1
                continue
            ridge = _pair_ridge(blobs, layers.film, blob_slices, b, keep_b)
            blob_assign[b] = id_next
            if np.isfinite(ridge) and ridge >= pcfg.split_film_thresh:
                events.append(TopologicalEvent(frame=t, kind="birth", bubble_ids=(id_next,),
                                               meta={"cause": "split_confirmed_strong_ridge",
                                                     "parent": parent, "ridge": float(ridge)}))
                diag["n_births_remaining"] += 1
            else:
                # faint separation -> serve probation; the id is NOT counted as a
                # reorganization birth unless the separation survives W frames.
                provisional[id_next] = {"parent": parent, "since": t, "frames": []}
            id_next += 1

        for b in unclaimed:
            rid = _resurrect(b)
            if rid is not None:
                blob_assign[b] = rid
                dormant.pop(rid, None)
                pending_merge.pop(rid, None)
                pending_death.pop(rid, None)
                diag["n_resurrections"] += 1
            else:
                blob_assign[b] = id_next
                events.append(TopologicalEvent(frame=t, kind="birth", bubble_ids=(id_next,),
                                               meta={"cause": "new_interior_blob"}))
                diag["n_births_remaining"] += 1
                id_next += 1

        # ── 4. ONE MARKER PER BLOB (the invariant) ──────────────────────────────
        markers = np.zeros(blobs.shape, np.int32)
        for b, i in blob_assign.items():
            sl = blob_slices[b - 1]
            if sl is None:
                continue
            bm = blobs[sl] == b
            core = bm & (eroded[sl] == i)
            if int(core.sum()) >= pcfg.min_seed_area_px:
                markers[sl][core] = i
            else:
                sub = layers.dt[sl] * bm
                iy, ix = np.unravel_index(int(np.argmax(sub)), sub.shape)
                markers[sl[0].start + iy, sl[1].start + ix] = i
        if not markers.any():
            raise RuntimeError(f"frame {t}: no markers placed (interior empty?)")

        Lt = _reject_plateau_borders(
            watershed(layers.film, markers, mask=flood).astype(np.int32), layers, cfg)

        # ── 5. drop sub-minimum NEW/provisional regions ─────────────────────────
        present = {int(i) for i in np.unique(Lt) if i > 0}
        area_now = _counts(Lt, int(Lt.max()))
        for i in list(present):
            if i > frame0_max and area_now[i] < pcfg.new_seed_min_area_px:
                Lt[Lt == i] = 0
                present.discard(i)
                provisional.pop(i, None)

        # ── 6. bookkeeping: merges, dormancy, probation, deaths ─────────────────
        for loser, survivor in merge_losers.items():
            sl = ndi.find_objects((Lw == loser).astype(np.int32))
            if sl and sl[0] is not None:
                dormant[loser] = {"frame": t, "sl": sl[0],
                                  "mask": (Lw[sl[0]] == loser), "parent": survivor}
            pending_merge.setdefault(loser, {"survivor": survivor, "frame": t})

        for loser, pm in list(pending_merge.items()):
            if t - pm["frame"] >= pcfg.probation_frames:
                events.append(TopologicalEvent(
                    frame=pm["frame"], kind="merge", bubble_ids=(loser, pm["survivor"]),
                    meta={"survivor": pm["survivor"], "merged_ids": [loser],
                          "last_seen_frame": pm["frame"] - 1}))
                diag["n_merge_events"] += 1
                pending_merge.pop(loser)

        for did in [d for d, v in dormant.items() if t - v["frame"] > pcfg.resurrect_window]:
            dormant.pop(did)

        for pid, info in list(provisional.items()):
            if pid in present:
                info["frames"].append(t)
                if t - info["since"] + 1 >= max(pcfg.probation_frames, 1):
                    events.append(TopologicalEvent(
                        frame=info["since"], kind="birth", bubble_ids=(pid,),
                        meta={"cause": "split_confirmed_probation", "parent": info["parent"]}))
                    diag["n_births_remaining"] += 1
                    provisional.pop(pid)
            else:
                # separation did not survive probation -> flicker. Retire the id and
                # give its pixels back to the parent RETROACTIVELY, so it never counts
                # as a reorganization birth.
                sep_durations.append(len(info["frames"]))
                for f in info["frames"]:
                    id_maps[f][id_maps[f] == pid] = info["parent"]
                diag["n_probation_retired"] += 1
                provisional.pop(pid)

        # DECISION: a bubble that vanishes goes DORMANT rather than dying immediately —
        # detection flicker (one frame where its interior fails to resolve) must not be
        # a death, or the bubble has to re-mint a new id when it reappears, which is
        # churn of exactly the kind this design exists to avoid. The death is committed
        # only after `resurrect_window` frames with no reclaim.
        prev_ids = [int(i) for i in np.unique(L) if i > 0]
        for i in prev_ids:
            if i not in present and i not in merge_losers and i not in dormant:
                sl = ndi.find_objects((Lw == i).astype(np.int32))
                if sl and sl[0] is not None:
                    dormant[i] = {"frame": t, "sl": sl[0], "mask": (Lw[sl[0]] == i), "parent": None}
                    pending_death[i] = t
                else:                                    # no footprint left at all
                    events.append(TopologicalEvent(frame=t, kind="T2_disappear",
                                                   bubble_ids=(i,),
                                                   meta={"last_seen_frame": t - 1}))
                    diag["n_T2"] += 1
        for i, t_gone in list(pending_death.items()):
            if i in present:                              # reclaimed -> never died
                pending_death.pop(i)
            elif t - t_gone >= pcfg.resurrect_window:
                events.append(TopologicalEvent(frame=t_gone, kind="T2_disappear",
                                               bubble_ids=(i,),
                                               meta={"last_seen_frame": t_gone - 1}))
                diag["n_T2"] += 1
                pending_death.pop(i)

        # ── 7. REGRESSION GUARD: region count vs the independent blob count ─────
        n_reg = int(len(present))
        n_regions_series.append(n_reg)
        n_blobs_series.append(n_blobs_eligible)
        # DECISION: the guard fires on a RELATIVE decline, not an absolute floor. The
        # ratchet signature is regions progressively LOSING ground against what the
        # frame affords; a steady fraction (e.g. because Plateau-border regions are
        # rejected by design) is not a defect. Referencing frame 0's ratio makes the
        # guard invariant to any constant filtering while still catching the ratchet.
        ratio = n_reg / n_blobs_eligible if n_blobs_eligible else 1.0
        if ratio0 is None:
            ratio0 = ratio if ratio > 0 else 1.0
        below = below + 1 if ratio < pcfg.collapse_guard_ratio * ratio0 else 0
        if below >= pcfg.collapse_guard_patience and pcfg.collapse_guard != "off":
            msg = (f"COLLAPSE GUARD: at frame {t} the region/eligible-blob ratio "
                   f"({ratio:.2f}, {n_reg} regions vs {n_blobs_eligible} blobs) has been "
                   f"below {pcfg.collapse_guard_ratio:.0%} of its frame-0 value "
                   f"({ratio0:.2f}) for {below} consecutive frames. This is the ratchet "
                   f"signature (markers progressively swallowing bubbles). See "
                   f"docs/propagation_ratchet_defect.md.")
            if pcfg.collapse_guard == "raise":
                raise RuntimeError(msg)
            import warnings
            warnings.warn(msg, RuntimeWarning, stacklevel=2)

        # ── FRAGMENTATION GUARD: a coarsening foam cannot GAIN bubbles ─────────
        # (the collapse guard above only sees the opposite failure). A sustained rise
        # above the running minimum means interiors are breaking into pieces.
        if n_reg > pcfg.fragmentation_guard_ratio * max(n_min, 1):
            above += 1
        else:
            above = 0
        n_min = min(n_min, n_reg)
        if above >= pcfg.fragmentation_guard_patience and pcfg.fragmentation_guard != "off":
            fmsg = (f"FRAGMENTATION GUARD: at frame {t} the region count ({n_reg}) has "
                    f"exceeded {pcfg.fragmentation_guard_ratio:.2f}x the running minimum "
                    f"({n_min}) for {above} consecutive frames. A coarsening foam cannot "
                    f"gain bubbles, so this means bubble interiors are fragmenting into "
                    f"multiple regions. See docs/foamc_fragmentation.md.")
            if pcfg.fragmentation_guard == "raise":
                raise RuntimeError(fmsg)
            import warnings
            warnings.warn(fmsg, RuntimeWarning, stacklevel=2)

        id_maps.append(Lt)
        results.append(SegmentationResult(Lt, layers.foam, layers.dist_to_edge, n_reg,
                                          meta={"backend": "propagate_v2"}))
        L = Lt
        prev_layers = layers

    # ── correspondence is rebuilt from the FINAL maps (after retroactive retires) ──
    corr_rows: list[dict] = []
    for f, m in enumerate(id_maps):
        for lab, (area, cx, cy) in _region_props(m).items():
            corr_rows.append({"frame": f, "bubble_id": lab, "label_in_frame": lab,
                              "area_px": area, "cx": cx, "cy": cy})

    ratios = [r / b if b else 1.0 for r, b in zip(n_regions_series, n_blobs_series)]
    max_id = max((int(m.max()) for m in id_maps), default=0)
    diag.update(frame0_max_id=frame0_max, max_bubble_id=max_id, n_frames=len(images),
                n_regions_series=n_regions_series, n_blobs_series=n_blobs_series,
                blob_ratio_min=float(min(ratios)) if ratios else float("nan"),
                blob_ratio_last=float(ratios[-1]) if ratios else float("nan"),
                separation_durations=sep_durations,
                n_provisional_open=len(provisional),
                n_regions_min=n_min)
    tracking = TrackingResult(
        id_maps=id_maps, events=events, correspondence=pd.DataFrame(corr_rows),
        n_tracks=max_id, frame_offsets=frame_offsets, diagnostics=diag)
    return results, tracking
