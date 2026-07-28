# -*- coding: utf-8 -*-
"""label.py — correction-based ground-truth labeling in Napari.

Pre-seeds the labels layer with the CURRENT temporal marker-propagation
segmentation (foam_gnn.propagate) for the exact requested frame, so you correct
its errors instead of drawing ~150-300 bubbles from scratch. This is standard
correction-based annotation, and it introduces a real bias toward the seeding
method (see the "AUDIT MODE" note below and docs/groundtruth_labeling.md) —
disclosed, not hidden.

Run from the foam_gnn/ directory:  python label.py
(edit SET / EXP / FRAME below first, or set them via env vars — see below)
"""
import os
import sys
from pathlib import Path

import imageio.v3 as iio
import napari
import numpy as np

from foam_gnn.config import PipelineConfig
from foam_gnn.gt_preseed import (
    LABEL_FRAMES,
    SEED_BLANK,
    SEED_PROPAGATED,
    SEED_UNKNOWN_LEGACY,
    STATUS_INSPECTED,
    compute_or_load_preseed,
    corrected_path,
    frame_status,
    frame_tag,
    raw_frame_path,
    upsert_manifest_row,
)

# ============ EDIT THESE FOR EACH FRAME (or set env vars GT_SET/GT_EXP/GT_FRAME) ==
SET = os.environ.get("GT_SET", "eval")
EXP = os.environ.get("GT_EXP", "exp1")
FRAME_IDX = int(os.environ.get("GT_FRAME", "0"))   # ABSOLUTE frame index, e.g. 49
# ===================================================================================
if os.environ.get("GT_LIST"):
    print("Planned (set, exp, frame) triples — docs/groundtruth_labeling.md:")
    for _s, _e, _f, _note in LABEL_FRAMES:
        print(f"  {_s:5s} {_e} f{_f:03d}  {_note}")
    sys.exit(0)

GT_ROOT = Path("groundtruth")
DATA_ROOT = "data"
CFG = PipelineConfig()

if (SET, EXP, FRAME_IDX) not in {(s, e, f) for s, e, f, _ in LABEL_FRAMES}:
    print(f"WARNING: ({SET}, {EXP}, f{FRAME_IDX:03d}) is not in the planned LABEL_FRAMES "
          f"list (docs/groundtruth_labeling.md). Proceeding anyway — check for a typo.")

frame_str = frame_tag(FRAME_IDX)
src = raw_frame_path(GT_ROOT, SET, EXP, FRAME_IDX)
out = corrected_path(GT_ROOT, SET, EXP, FRAME_IDX)
out.parent.mkdir(parents=True, exist_ok=True)

if not src.exists():
    sys.exit(f"Raw frame not found: {src}\n"
             f"Run dev/export_label_frames.py first to export it.")

img = iio.imread(src)
if img.ndim == 3:
    img = img[..., 0]

# ── resume > pre-seed > blank (# DECISION: never clobber in-progress work) ───────
# ...BUT a file marked `inspected_not_corrected` is NOT work in progress: it is an
# untouched pre-seed from a frame that was opened and abandoned. Resuming from it would
# silently restart you on a STALE (and, for pre-2026-07-15 frames, defective) pre-seed
# instead of the current one. Treat it as absent and re-seed.
_status = frame_status(GT_ROOT, SET, EXP, FRAME_IDX)
if out.exists() and _status == STATUS_INSPECTED:
    print(f"NOTE: {out.name} is marked '{STATUS_INSPECTED}' in the manifest — it holds an "
          f"untouched pre-seed, not hand-corrected work, so it is being RE-SEEDED from the "
          f"current segmenter rather than resumed. (The old file is left on disk.)")

if out.exists() and _status != STATUS_INSPECTED:
    labels = iio.imread(out).astype(np.uint16)
    # provenance is PRESERVED (not rewritten) if a manifest row already exists for this
    # frame; this fallback only fires if it doesn't (e.g. pre-dates this provenance
    # system) -- an honest "we don't actually know", not a silent guess.
    seed_method, preseed_source = SEED_UNKNOWN_LEGACY, ""
    print(f"RESUMING — {int(labels.max())} bubbles already in {out}")
else:
    try:
        seeded, preseed_source = compute_or_load_preseed(
            DATA_ROOT, GT_ROOT, SET, EXP, FRAME_IDX, CFG, use_cache=True)
        labels = seeded.astype(np.uint16)
        seed_method = SEED_PROPAGATED
        n_seed = int(labels.max())
        print(f"PRE-SEEDED from the propagated segmenter ({preseed_source}) — "
              f"{n_seed} candidate bubbles. CORRECT this, don't just accept it — "
              f"see the AUDIT MODE note below.")
        if preseed_source == "computed":
            print("  (no cache found — computed on the fly, which is slow; this frame is "
                  "now cached for next time. Consider running dev/preseed_labels.py once "
                  "up front for all 30 frames.)")
    except Exception as exc:  # pragma: no cover - interactive fallback, not unit-tested
        print(f"WARNING: pre-seeding failed ({exc!r}) — falling back to a BLANK canvas. "
              f"You are labeling this frame entirely from scratch.")
        labels = np.zeros(img.shape[:2], dtype=np.uint16)
        seed_method, preseed_source = SEED_BLANK, ""

viewer = napari.Viewer(title=f"{SET}/{EXP}/{frame_str}")
img_layer = viewer.add_image(img, name="foam", colormap="gray")
lbl = viewer.add_labels(labels, name="bubbles")
lbl.mode = "fill"
lbl.selected_label = int(labels.max()) + 1
viewer.layers.selection.active = lbl   # so the built-in 'V' visibility toggle hits "bubbles"

print(f"""
=================== LABELING: {SET}/{EXP}/{frame_str} ===================
Label EVERY bubble, especially the tiny ones and the ones hugging the outer
edge — those are exactly the population this project depends on, and exactly
what a correction pass is most likely to miss (see AUDIT MODE below).

--- KEYBINDINGS (napari {napari.__version__} defaults; Preferences > Shortcuts if these
    don't match your version) ---
  1 / E   erase mode        (brush paints background/0)
  2 / P   paint mode        (brush paints the selected label)
  4 / F   fill mode         (bucket-fill the CONNECTED region under the cursor)
  5 / L   picker mode       (click a bubble to SET selected_label to its value)
  M       new label         (jump selected_label to the next unused value)
  - / =   step selected label down / up by 1
  [ / ]   shrink / grow brush size
  B       toggle "preserve labels" (ON = brush/fill only touch background,
          never overwrite an existing label — safe default when ADDING a
          missed bubble; turn OFF for merge/split, where you WANT to
          overwrite an existing label)
  V       *** AUDIT MODE *** toggle the "bubbles" layer's visibility —
          press it to see the BARE image with no overlay, and hunt for
          bubbles the pre-seed never proposed at all (esp. small / near-edge
          ones — the seeding method's blind spot). Press again to restore.
  Ctrl+Z / Ctrl+Shift+Z    undo / redo
  scroll  zoom;  hold Space  temporary pan
  to jump the selected label to a specific number: click the numeric spinbox
  in the top-left "bubbles" layer controls and type it directly.

--- CORRECTION RECIPES ---
  Delete a false region:      picker (5) on background -> selected_label=0,
                               then fill (4) click inside the false region.
  Split a wrongly-merged bubble: paint (2) with "preserve labels" OFF, draw a
                               thin background (0) line across the middle to
                               separate it into two disconnected pieces; press
                               M for a fresh label; fill (4) click ONE piece
                               (fill only affects the connected region under
                               the cursor, so only that piece gets relabeled).
  Merge a wrongly-split bubble:  picker (5) the part to KEEP -> selected_label
                               set; fill (4) click the OTHER part to absorb it.
  Add a missed bubble:        M for a fresh label, "preserve labels" ON, then
                               paint (2) or fill (4) the bubble.

Close the window when done — it saves automatically to:
  {out}
====================================================================
""")

napari.run()

final = viewer.layers["bubbles"].data.astype(np.uint16)
iio.imwrite(out, final)
n_final = len(np.unique(final)) - (1 if 0 in np.unique(final) else 0)
print(f"Saved {out}  ({n_final} bubbles)")

man_path = upsert_manifest_row(
    GT_ROOT, SET, EXP, FRAME_IDX,
    seed_method=seed_method or "", preseed_source=preseed_source,
    labeler=os.environ.get("GT_LABELER", ""), date=os.environ.get("GT_DATE", ""),
    notes=os.environ.get("GT_NOTES", ""))
print(f"Recorded provenance in {man_path} "
      f"(seed_method preserved from first save if this is a resume).")
