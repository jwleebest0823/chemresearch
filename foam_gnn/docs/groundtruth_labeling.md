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
├── manifest.csv                 # provenance of every labeled frame (COMMITTED)
├── eval/exp1/ f000.png ...      # 16-bit hand-CORRECTED label masks (COMMITTED)
├── eval/exp3/ f000.png ...
├── train/exp4/ f000.png ...
├── tolabel/{eval,train}/*.png   # raw frame exports for Napari (gitignored, regenerable)
└── preseed/{eval,train}/<exp>/*.png   # cached automatic pre-seeds (gitignored, regenerable)
```
Only the hand-corrected masks under `eval/`, `train/` and `manifest.csv` are committed
to git — `tolabel/` and `preseed/` are caches regenerable from gitignored `data/` via
`dev/export_label_frames.py` / `dev/preseed_labels.py`.
`manifest.csv` columns (required by the loader: `exp, frame_index, path`; the rest are
written automatically by `label.py`, not filled in by hand):
```
set,exp,frame_index,path,labeler,date,notes,seed_method,preseed_source
eval,exp1,0,eval/exp1/f000.png,JW,2026-07-11,dense early frame,propagated_segmenter_correction,cache
eval,exp1,1,eval/exp1/f001.png,JW,2026-07-11,consecutive with f000,propagated_segmenter_correction,cache
```
`path` is relative to `groundtruth/`. `frame_index` is the **absolute** index within
the experiment (matches `qc/cache/<exp>/f<idx>.npz` and the pipeline's frame numbering).
The `set` column tags each frame `eval` or `train` (see the split below). Two more
columns, `seed_method` and `preseed_source`, are written automatically by `label.py`
— see **Correction-based annotation** below; they are provenance, not something you
fill in by hand.

## Correction-based annotation — methodology and its bias (read this)
Hand-labeling ~30 frames fully from scratch (each has 150–300+ bubbles) is
**infeasible** — 40+ hours of work. `label.py` instead uses standard **correction-based
annotation**: it pre-seeds the Napari labels layer with the CURRENT temporal
marker-propagation segmentation (`foam_gnn.propagate`) for that exact frame, and you
correct its errors (delete false regions, split/merge, add missed bubbles) rather than
draw every bubble by hand.

**This is a real methodological caveat, stated plainly, not buried:** correction-based
ground truth is **biased toward the seeding method**. An annotator correcting a
segmentation is less likely to notice an error the segmenter makes *consistently*
(there's no proposed region there to look at) than one drawing independently —
"rubber-stamping". The bias is worst exactly on the population this project depends
on: bubbles the propagated segmenter **misses entirely**, especially small ones near
the evaporation edge. **Any evaluation or paper using this GT must disclose that it is
correction-based, seeded from `foam_gnn.propagate`, not drawn independently.**

Two mitigations (neither removes the bias, both are load-bearing):
1. **Provenance is recorded per-frame.** `label.py` writes `seed_method` (
   `propagated_segmenter_correction` / `blank_manual` / `unknown_legacy_resume`) and
   `preseed_source` (`cache` / `computed`) to `manifest.csv` automatically, and
   **preserves** the original value across every later resume-and-correct session (it
   is set once, on first save, never silently overwritten).
2. **Audit mode.** In Napari, press **`V`** (the built-in "toggle selected layer
   visibility" binding) to **hide the pre-seed entirely** and see the bare raw frame.
   Use this deliberately to hunt for bubbles the segmenter never proposed — especially
   small, near-edge ones — before/in addition to correcting the seeded labels. Press
   `V` again to bring the labels back.

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

## Napari workflow — `label.py`
0. **One-time setup:** `python dev/export_label_frames.py` exports the 30 raw frames
   to `groundtruth/tolabel/{eval,train}/`, then `python dev/preseed_labels.py`
   pre-computes and caches the propagated-segmenter seed for every one of them to
   `groundtruth/preseed/{eval,train}/<exp>/f<idx>.png` (segments each session prefix
   once; ~10–15 min per Foam-C session, faster for Foam A — run it once up front so
   `label.py` opens instantly instead of re-segmenting on every launch).
1. Edit the three lines at the top of `label.py` (`SET`, `EXP`, `FRAME_IDX`) — or set
   env vars `GT_SET` / `GT_EXP` / `GT_FRAME` — to the frame you're labeling. Run
   `GT_LIST=1 python label.py` to print the full planned list.  Then: `python label.py`
   (run from the `foam_gnn/` directory).
2. Napari opens with the labels layer **pre-seeded** from the cached (or, if missing,
   freshly computed) propagated segmentation — see **Correction-based annotation**
   above. **Correct it**: delete false regions, split/merge, and — using audit mode
   (`V`) — add bubbles the seed missed entirely. The printed on-launch cheat sheet
   covers the exact keybindings and correction recipes (erase/paint/fill/picker/new
   label/undo/audit toggle).
3. Close the window — it **saves automatically** to `groundtruth/<set>/<exp>/f<idx>.png`
   and writes/updates the `manifest.csv` row (path, provenance, and any `GT_LABELER` /
   `GT_DATE` / `GT_NOTES` env vars you set) for you. Re-running `label.py` on the same
   frame **resumes** from the saved corrected mask (never re-seeds, never loses work).

## Validation
`foam_gnn.seg_eval.load_gt_frame` fails loud on wrong shape, non-integer or negative
labels, and warns (`n_tiny`) on labels below `SegEvalConfig.gt_min_bubble_area_px`
(possible annotation specks). Run `dev/check_gt.py` after labeling to validate every
manifest row before evaluation.
