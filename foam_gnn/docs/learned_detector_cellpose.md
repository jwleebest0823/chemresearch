# Learned detector (Cellpose) — promising on Foam A, but BLOCKED on compute

## Task 3 first, as briefed: the dense foams are NOT fixed — because the test could not be run

**The decisive experiment (run a learned detector over exp3's full sequence and check the
count trend, the fragmentation guard, ⟨n⟩ and n₀) was not performed.** It is blocked by a
hard compute limit, measured rather than assumed:

* This machine is **CPU-only** (`torch 2.13.0+cpu`, `torch.cuda.is_available() == False`,
  12 cores).
* **Cellpose 3.x — the version with the `cyto3` / `cyto2` / `nuclei` models the brief names
  — cannot run here at all.** It pins `numpy<2.1`, and Python 3.13 on Windows has no stable
  `numpy<2.1` wheel; pip falls back to an experimental MINGW-W64 build that prints
  *"CRASHES ARE TO BE EXPECTED"* and **segfaults** (exit 139) on the first `model.eval()`.
* **Cellpose 4.2.1.1 (Cellpose-SAM) does run**, with `numpy 2.4.6`. But it is a ViT and on
  CPU it costs, measured on real exp1 f000 crops:

  | crop | pixels | wall time | objects |
  |---|---|---|---|
  | 256×256 | 0.66e5 | **414.0 s** | 31 |
  | 512×512 | 2.62e5 | **956.9 s** | 89 |

  Fitting `cost ≈ a + b·px` gives a = 233 s, b = 276 s per 1e5 px, so a full
  **1024×1280 frame ≈ 3,850 s ≈ 64 minutes**. Thread count is not the limit — forcing 12
  threads instead of the default 6 changed a 256² eval from 445 s to 397 s (11%).

  | required work | frames | **projected CPU time** |
  |---|---|---|
  | Task 1 baseline (14 Foam A GT + 3 Foam C) | 17 | **~18 hours** |
  | Task 3 decisive test (exp3 full sequence) | 99 | **~105 hours (4.4 days)** |
  | Task 2 fine-tuning | — | several × inference cost |

**So Task 3 is unanswered, and Tasks 2 and 5 with it.** Running a reduced configuration and
presenting it as the answer is exactly what the brief forbids, so I did not.

## What WAS measured: excellent on Foam A, poor on Foam C

A bounded probe: zero-shot Cellpose-SAM on a **512×512 crop** of each foam, scored against
the hand-labelled ground truth for the same crop. This is a **probe, not the baseline** —
the project's bar (F1 0.9030) is pooled over 14 *full* frames.

### Foam A (exp1 f000, 512×512 crop, 91 GT bubbles)

| | precision | recall | **F1** | 95% CI |
|---|---|---|---|---|
| **zero-shot Cellpose-SAM @ IoU 0.5** | 0.978 | 0.956 | **0.9667** | **[0.9388, 0.9889]** |
| zero-shot @ IoU 0.5, border objects excluded | 0.959 | 0.959 | 0.959 | — |
| zero-shot @ IoU 0.75 | 0.843 | 0.824 | 0.833 | — |
| *current watershed pipeline (14 full frames, pooled)* | *0.925* | *0.882* | *0.9030* | — |

**Zero-shot, with no fine-tuning and no foam-specific tuning of any kind, Cellpose-SAM
scores F1 0.967 on this crop against the tuned pipeline's 0.903 pooled.** The CI is clear
of 0.903. At the stricter IoU 0.75 it drops to 0.833, i.e. its boundaries are less precise
than its detections — expected for a model that has never seen a soap film.

This is a genuine signal that the hypothesis behind the session is right: a model that
recognises object *appearance* does not need the intensity-gradient thresholding that
shatters on bright interiors. But **one crop of one frame is not the baseline**, and no
claim about Foam A regression or improvement should rest on it.

### Foam C (exp3 f000, 512×512 crop, 224 GT bubbles) — transfer is POOR

| | precision | recall | **F1** | 95% CI | objects |
|---|---|---|---|---|---|
| **zero-shot Cellpose-SAM @ IoU 0.5** | 0.675 | 0.696 | **0.6857** | **[0.6437, 0.7271]** | 231 (GT 224) |
| zero-shot @ IoU 0.75 | 0.524 | 0.540 | 0.532 | — | — |
| *Foam A crop, same model, same settings* | *0.978* | *0.956* | *0.9667* | *[0.9388, 0.9889]* | *89 (GT 91)* |

**Zero-shot transfer collapses from F1 0.967 on Foam A to 0.686 on Foam C** — a drop of
0.28 with non-overlapping CIs. The domain shift is real and large, exactly as anticipated
in Task 4.

Two details worth separating, because they point in opposite directions:

* **The object COUNT is nearly right**: 231 detected against 224 labelled (+3%). Cellpose
  is *not* shattering the frame the way the watershed does — it is not producing the
  fragmentation signature. That is the encouraging half.
* **But per-object correspondence is poor**: only 156 of 224 GT bubbles match at IoU 0.5.
  It finds about the right number of objects and draws a third of them differently from the
  human. On a dense foam it is placing boundaries in the wrong places, not miscounting.

**A comparison that must not be made naively.** The current watershed scores F1 0.967 on
exp3 f000 against this same GT — apparently identical to Cellpose's Foam A number. That
watershed score is **inflated by construction**: the Foam C GT was produced by *deleting*
regions from the watershed's own output, so its recall is 1.0 by definition
(`docs/foamc_detection_accuracy.md`). Cellpose had no part in building that GT, so **its
0.696 recall is a genuine independent measurement while the watershed's 1.000 is a
tautology.** The two numbers are not comparable, and the watershed's apparent superiority
on Foam C is an artifact of how the labels were made.

**What this crop cannot settle:** whether Cellpose fixes the *fragmentation over time*.
On f000 both detectors produce roughly the right count (Cellpose 231 vs GT 224; watershed
574 vs GT 537 on the full frame). Foam C's defect appears later in the sequence, as the
count climbs. Only the full-sequence sweep — the blocked Task 3 — can answer it.



## Task 4 — domain shift, stated in advance and then measured
**Expectation stated plainly:** I did not expect clean transfer. The training data the brief
offers is 14 frames of one *sparse* foam; the targets are dense foams a human could not
label. Cellpose's pretraining is cell microscopy, not foam, so bubbles-as-cells is a
plausible but untested analogy, and the dense-foam regime (hundreds of small, low-contrast,
tightly packed objects) is the harder end of its distribution.

**What was actually measured confirms that expectation.** Zero-shot transfer to Foam A is
excellent (F1 0.967) and to Foam C is poor (F1 0.686), with non-overlapping CIs. Since the
Foam A frames are the *only* training data available, and Foam A is precisely where the
model already performs, **fine-tuning on them is unlikely to close the Foam C gap** — it
would add supervision where the model is already strong and none where it is weak. The
labelling bottleneck that blocked Foam C for a human blocks the learned route the same way:
there is no Foam C supervision to fine-tune on.

That said, the encouraging half stands — Cellpose gets Foam C's object *count* right (+3%)
without the fragmentation signature, so its failure mode is boundary placement rather than
shattering. Whether that translates into a physical count-vs-time curve is the blocked
Task 3 question.

## Environment damage and repair — recorded because it nearly went unnoticed
Installing Cellpose into the project interpreter **downgraded numpy 2.4.6 → 2.0.2**, and
that 2.0.2 is the experimental MINGW-W64 build. The project's own dependency pin
(`foam-gnn requires numpy==2.4.6`) was violated silently by pip's resolver.

Repaired: numpy force-reinstalled to 2.4.6 in the project interpreter, and Cellpose moved
to an **isolated venv** (`C:\Users\jwlee\cpv`, kept at a short path because the deep
scratchpad path exceeded Windows MAX_PATH and broke the torch install). Verified after
repair: **151 tests pass** and the GT digest is unchanged.

`# DECISION` — Cellpose runs in the isolated venv and writes `.npy` masks; all scoring
happens in the project interpreter. The two environments never share a process, so the
project's numpy pin can never be perturbed by the detector work again.

Versions: `cellpose 4.2.1.1`, `numpy 2.4.6`, `torch 2.13.0+cpu` (isolated venv);
project interpreter unchanged at `numpy 2.4.6`, `torch 2.13.0+cpu`.

## Recommendation — what to do next, costed

1. **Get GPU access.** This is the whole blocker. On a mid-range CUDA GPU Cellpose-SAM runs
   roughly 50–100× faster than this CPU, putting the full Task 1 baseline at ~15–25 minutes
   and the decisive Task 3 sweep at ~1–2 hours. Everything in this brief becomes routine.
   Nothing else in the plan needs to change.
2. **If GPU is not available, do not pursue Cellpose-SAM on CPU** — 105 hours for one
   sequence is not a workable iteration loop.
3. **A cheap CPU-viable alternative worth one session:** train a small U-Net (boundary +
   interior heads) from scratch on the 6 training frames, in the project's existing torch.
   Inference would be ~1–2 s/frame rather than 64 min, making the full Task 3 sweep minutes.
   It gives up Cellpose's pretraining, which is precisely what made the zero-shot number
   above strong, so it is a worse bet on quality — but it is the only learned detector that
   fits this hardware.

**The hypothesis is not refuted and is now better supported than before this session** — it
simply cannot be tested on the decisive foams with the compute available.

## Caveats that survive regardless
* **Foam C has ground truth only at f000/f001, and it is deletion-only**
  (`docs/foamc_detection_accuracy.md`): recall against it is 1.0 by construction. Any Foam C
  detection number — including the probe above — inherits that limitation, and **any
  replication claim built on Foam C would remain GT-unvalidated for its mid/late frames**,
  which is where the modeling data lives.
* Nothing here changes the Foam A results. The trusted set, K values and Gate 3 conclusions
  in `docs/gates_v4_repairs.md` stand untouched.
* The 14 GT masks were not modified — digest verified before and after.
