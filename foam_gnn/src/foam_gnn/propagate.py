"""
foam_gnn.propagate
==================
**Temporal marker-propagation watershed** — a temporally-coupled segmenter that
attacks the project's binding failure directly: *temporal identity stability of
small and near-edge bubbles*, not per-frame boundary quality (Plateau is already
~99%).

The idea
--------
Segment frame 0 normally, then segment every later frame by seeding its watershed
from the **previous frame's stable-ID label map**, warped by the measured
inter-frame drift. Each persistent bubble contributes exactly **one marker carrying
its own id**, so:

* a bubble **cannot spuriously split** into two ids (one marker → one basin), and
* a bubble **cannot be re-minted** as a new id (its marker keeps the old id).

These are precisely the two events that produced the ~10–20 reorganization-births
per bubble. The two *genuine* topology changes are still allowed:

* **merge** — detected *after* watershed: if the shared boundary between two
  previously-separate bubbles no longer carries a film ridge, the film has burst;
  the boundary is dissolved and the smaller id is absorbed (``keep_larger``), and a
  ``merge`` event is emitted.
* **disappearance (T2)** — a bubble whose interior has collapsed below a seed-area
  floor is not re-seeded; its id ends and a ``T2_disappear`` event is emitted.

**Adaptive markers** seed genuinely new / newly-resolved small bubbles at their
*local* scale (``peak_local_max`` on the distance transform with a small separation
and dt floor) rather than a single global ``h_maxima``, so small bubbles are not
missed.

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

    __slots__ = ("clean", "foam", "dist_to_edge", "film", "interior", "dt")

    def __init__(self, clean, foam, dist_to_edge, film, interior, dt):
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
                       interior, dt.astype(np.float32))


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


def _seed_frame0(layers: FrameLayers, cfg: PipelineConfig):
    """Frame-0 markers = global h_maxima seeds (splits touching bubbles) + one seed for
    every interior blob a global h_maxima misses (small bubbles)."""
    seg = cfg.seg
    base = h_maxima(layers.dt, seg.h_maxima) * layers.foam
    markers, n_base = ndi.label(base)
    markers = markers.astype(np.int32)
    extra, _ = _unseeded_blob_seeds(layers.interior, layers.dt, markers,
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


def _pair_border_film(labels: np.ndarray, film: np.ndarray) -> dict[tuple[int, int], tuple[float, int]]:
    """Mean film ridge value and pixel count along each adjacent label pair's border.

    Returns ``{(lo, hi): (mean_film, n_border_px)}`` using 4-connectivity.
    """
    maxid = int(labels.max())
    if maxid == 0:
        return {}
    sums: dict[tuple[int, int], float] = {}
    cnts: dict[tuple[int, int], int] = {}

    def acc(a, b, fa, fb):
        m = (a > 0) & (b > 0) & (a != b)
        if not m.any():
            return
        aa, bb = a[m], b[m]
        lo = np.minimum(aa, bb)
        hi = np.maximum(aa, bb)
        fv = 0.5 * (fa[m] + fb[m])
        key = lo.astype(np.int64) * (maxid + 1) + hi.astype(np.int64)
        for k, v in zip(key, fv):
            sums[k] = sums.get(k, 0.0) + float(v)
            cnts[k] = cnts.get(k, 0) + 1

    acc(labels[:, :-1], labels[:, 1:], film[:, :-1], film[:, 1:])
    acc(labels[:-1, :], labels[1:, :], film[:-1, :], film[1:, :])
    out: dict[tuple[int, int], tuple[float, int]] = {}
    for k, n in cnts.items():
        lo, hi = divmod(int(k), maxid + 1)
        out[(lo, hi)] = (sums[k] / n, n)
    return out


class _UF:
    def __init__(self):
        self.p: dict[int, int] = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


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


def segment_track_propagated(images: list[np.ndarray], cfg: PipelineConfig) -> tuple[list[SegmentationResult], TrackingResult]:
    """Temporal marker-propagation segmentation + tracking of one session.

    Parameters
    ----------
    images : ordered uint8 (H, W) frames of ONE contiguous tracking run.

    Returns
    -------
    (results, tracking) : per-frame ``SegmentationResult`` (labels in stable-ID
        space) and a ``TrackingResult`` with ``id_maps`` (stable), ``correspondence``,
        ``events`` (birth/merge/T2), ``frame_offsets``, and ``diagnostics``
        (``frame0_max_id``, ``n_births_remaining``, ``n_merge_events`` …).
    """
    import pandas as pd

    if not images:
        raise ValueError("no images")
    seg, pcfg = cfg.seg, cfg.propagate

    layers0 = compute_frame_layers(images[0], cfg)
    raw0 = watershed(layers0.film, _seed_frame0(layers0, cfg), mask=layers0.foam)
    L = _area_filter_relabel(raw0, seg.min_bubble_area_px)
    frame0_max = int(L.max())
    id_next = frame0_max + 1

    id_maps = [L]
    results = [SegmentationResult(L, layers0.foam, layers0.dist_to_edge, int(L.max()),
                                  meta={"backend": "propagate"})]
    events: list[TopologicalEvent] = []
    corr_rows: list[dict] = []
    for lab, (area, cx, cy) in _region_props(L).items():
        corr_rows.append({"frame": 0, "bubble_id": lab, "label_in_frame": lab,
                          "area_px": area, "cx": cx, "cy": cy})
    frame_offsets = [(0.0, 0.0)]
    cum_x = cum_y = 0.0
    diag = {"n_births_remaining": 0, "n_merge_events": 0, "n_T2": 0}
    prev_layers = layers0

    for t in range(1, len(images)):
        layers = compute_frame_layers(images[t], cfg)
        dy, dx = _estimate_drift(prev_layers.foam, layers.foam, cfg)
        cum_x += dx
        cum_y += dy
        frame_offsets.append((cum_x, cum_y))
        Lw = ndi.shift(L, shift=(dy, dx), order=0, mode="constant", cval=0).astype(np.int32)

        maxid = int(Lw.max())
        raw_seed = np.where(layers.interior, Lw, 0).astype(np.int32)
        bnd_zone = ndi.binary_dilation(find_boundaries(Lw, mode="outer"),
                                       iterations=pcfg.erode_seed_px)
        eroded = np.where(~bnd_zone, raw_seed, 0).astype(np.int32)
        er_area = _counts(eroded, maxid)
        raw_area = _counts(raw_seed, maxid)

        markers = eroded.copy()
        prev_ids = [int(i) for i in np.unique(L) if i > 0]
        seeded: set[int] = set()
        for i in prev_ids:
            if er_area[i] >= pcfg.min_seed_area_px:
                seeded.add(i)
            elif raw_area[i] >= pcfg.min_seed_area_px:      # small bubble: skip erosion
                markers[raw_seed == i] = i
                seeded.add(i)
            # else: seed collapsed -> genuine disappearance (handled below)

        extra, id_next2 = _unseeded_blob_seeds(layers.interior, layers.dt, markers,
                                               id_next, pcfg.new_seed_min_area_px)
        markers = np.where(extra > 0, extra, markers)

        Lt = watershed(layers.film, markers, mask=layers.foam).astype(np.int32)

        # ── merge post-process: dissolve filmless borders between PRE-EXISTING ids ──
        pair_film = _pair_border_film(Lt, layers.film)
        uf = _UF()
        for (lo, hi), (mean_film, n) in pair_film.items():
            if lo in seeded and hi in seeded and n >= pcfg.merge_min_border_px \
                    and mean_film < pcfg.merge_film_thresh:
                uf.union(lo, hi)
        # apply unions: survivor = largest-area member (keep_larger; tie -> max id)
        groups: dict[int, list[int]] = {}
        for i in seeded:
            groups.setdefault(uf.find(i), []).append(i)
        area_now = _counts(Lt, int(Lt.max()))
        remap = np.arange(int(Lt.max()) + 1, dtype=np.int32)
        merged_this_frame: set[int] = set()
        for members in groups.values():
            if len(members) < 2:
                continue
            survivor = max(members, key=lambda i: (area_now[i] if i < len(area_now) else 0, i))
            for i in members:
                if i != survivor:
                    remap[i] = survivor
                    merged_this_frame.add(i)
            cxym = _region_props((Lt == survivor).astype(np.int32)).get(1, (0, 0.0, 0.0))
            events.append(TopologicalEvent(
                frame=t, kind="merge", bubble_ids=tuple(sorted(members)),
                meta={"survivor": survivor, "merged_ids": [i for i in members if i != survivor],
                      "last_seen_frame": t - 1, "cx": cxym[1], "cy": cxym[2]}))
            diag["n_merge_events"] += 1
        if merged_this_frame:
            Lt = remap[Lt]

        # ── drop tiny NEW basins (below new_seed_min_area) -> background ──
        present = {int(i) for i in np.unique(Lt) if i > 0}
        new_ids = {i for i in present if i >= id_next}          # minted this frame
        area_final = _counts(Lt, int(Lt.max()))
        for i in list(new_ids):
            if area_final[i] < pcfg.new_seed_min_area_px:
                Lt[Lt == i] = 0
                present.discard(i)
                new_ids.discard(i)

        # ── events: births + disappearances ──
        props = _region_props(Lt)
        for i in sorted(new_ids):
            if i in props:
                events.append(TopologicalEvent(frame=t, kind="birth", bubble_ids=(i,),
                                               meta={"cx": props[i][1], "cy": props[i][2],
                                                     "cause": "adaptive_new_seed"}))
                diag["n_births_remaining"] += 1
        for i in prev_ids:
            if i not in present and i not in merged_this_frame:
                events.append(TopologicalEvent(frame=t, kind="T2_disappear", bubble_ids=(i,),
                                               meta={"last_seen_frame": t - 1}))
                diag["n_T2"] += 1

        id_next = id_next2
        for lab, (area, cx, cy) in props.items():
            corr_rows.append({"frame": t, "bubble_id": lab, "label_in_frame": lab,
                              "area_px": area, "cx": cx, "cy": cy})
        id_maps.append(Lt)
        results.append(SegmentationResult(Lt, layers.foam, layers.dist_to_edge, len(props),
                                          meta={"backend": "propagate"}))
        L = Lt
        prev_layers = layers

    max_id = max((int(m.max()) for m in id_maps), default=0)
    diag.update(frame0_max_id=frame0_max, max_bubble_id=max_id,
                invariant_B_holds=bool(max_id <= frame0_max),
                n_frames=len(images))
    tracking = TrackingResult(
        id_maps=id_maps, events=events, correspondence=pd.DataFrame(corr_rows),
        n_tracks=max_id, frame_offsets=frame_offsets, diagnostics=diag)
    return results, tracking
