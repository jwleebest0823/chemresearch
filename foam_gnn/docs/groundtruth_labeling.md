# Ground-truth labeling — format & protocol

This is the spec for the hand-labeled frames that feed `foam_gnn.seg_eval`. Follow it
exactly so the loader/validator accepts the masks without manual fixups.

## File format (# DECISION)
- **One integer label per bubble**, `0` = background / film / outside-foam.
- Save each labeled frame as a **lossless 16-bit PNG** (8-bit would clip past 255
  bubbles; dense early frames have 150–300). TIFF is also accepted. Label values need
  not be contiguous — the loader relabels to `1..K`.
- **Label the RAW frame** (the grayscale image the pipeline ingests), so GT and the
  predicted segmentation share native pixel coordinates and match by overlap.
- **Every bubble, including the smallest and the near-edge ones.** Those are the whole
  point — a mask that skips the hard bubbles defeats the evaluation. If a bubble is
  ambiguous, label your best guess and note the frame in `manifest.csv`.

## Directory layout
```
foam_gnn/groundtruth/
├── manifest.csv                 # provenance of every labeled frame
├── exp1/ f000.png f001.png ...  # 16-bit label masks, filename = abs frame index
├── exp3/ f000.png ...
└── ...
```
`manifest.csv` columns (required: `exp, frame_index, path`; optional: `labeler, date,
notes`):
```
exp,frame_index,path,labeler,date,notes
exp1,0,exp1/f000.png,JW,2026-07-11,dense early frame
exp1,1,exp1/f001.png,JW,2026-07-11,consecutive with f000
```
`path` is relative to `groundtruth/`. `frame_index` is the **absolute** index within
the experiment (matches `qc/cache/<exp>/f<idx>.npz` and the pipeline's frame numbering).
The `set` column tags each frame `eval` or `train` (see the split below).

## Which frames to label — ~30 frames, split into EVAL and TRAIN
Two disjoint sets so a learned method (Cellpose/StarDist/μSAM fine-tune) can train
without ever touching the evaluation frames:
* **EVAL (~16, held out, NEVER trained on)** — the scoring set for every method.
* **TRAIN (~14, separate)** — only for fine-tuning a supervised method.

**Disjointness (# DECISION):** kept **session-disjoint on Foam C** (eval = `exp3,exp5`;
train = `exp4,exp6,exp7`) so no Foam-C session appears in both. Foam A has only one
session (`exp1`), so its train/eval frames are **frame-disjoint and well-separated**
instead. The primary evaluation discipline is still **leave-one-foam-out** (fit on one
foam's labeled frames, report on the other); the set split is an extra guard so no frame
is both fit and scored. Goals within each set: **consecutive pairs** (so the temporal
split/merge metric can be validated between `t` and `t+1`) spread across the coarsening
timeline (dense → coarse).

### EVAL set (16 frames)
| foam | exp | frames | why |
|---|---|---|---|
| A | exp1 | 0, 1 | dense early (run0); pair |
| A | exp1 | 49, 50 | mid (run0); pair |
| A | exp1 | 97, 98 | late/coarse (run0); pair |
| A | exp1 | 148, 149 | run1 mid; pair |
| C | exp3 | 0, 1 | Foam C dense early; pair |
| C | exp3 | 49, 50 | Foam C mid; pair |
| C | exp3 | 97, 98 | Foam C late; pair |
| C | exp5 | 49, 50 | different session, mid; pair |

### TRAIN set (14 frames) — disjoint sessions (C) / disjoint frames (A)
| foam | exp | frames | why |
|---|---|---|---|
| A | exp1 | 24, 25 | run0, between eval frames; pair |
| A | exp1 | 73, 74 | run0, between eval frames; pair |
| A | exp1 | 120, 121 | run1; pair |
| C | exp4 | 0, 1 | train-only session; pair |
| C | exp4 | 49, 50 | train-only session; pair |
| C | exp6 | 49, 50 | train-only session; pair |
| C | exp7 | 49, 50 | train-only session; pair |

Consecutive pairs are the important part. `dev/export_label_frames.py` writes the EVAL
frames to `groundtruth/tolabel/eval/` and TRAIN frames to `groundtruth/tolabel/train/`,
with a `set` column in the manifest template.

## Napari workflow
1. Open the raw frame (from `groundtruth/tolabel/<exp>_f<idx>.png`) as an **Image**.
2. Add a **Labels** layer; paint one integer per bubble (use the fill/brush; increment
   the label id per bubble). Zoom in for the small/near-edge bubbles.
3. Save the Labels layer as PNG (`File ▸ Save Selected Layer…`, or
   `imageio.imwrite(path, labels_layer.data.astype('uint16'))`) to
   `groundtruth/<exp>/f<idx>.png`.
4. Add the row to `manifest.csv`.

## Validation
`foam_gnn.seg_eval.load_gt_frame` fails loud on wrong shape, non-integer or negative
labels, and warns (`n_tiny`) on labels below `SegEvalConfig.gt_min_bubble_area_px`
(possible annotation specks). Run `dev/check_gt.py` (provided) after labeling to
validate every manifest row before evaluation.
