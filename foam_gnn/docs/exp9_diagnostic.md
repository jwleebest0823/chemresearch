# exp9 (Foam E) diagnostic — does higher magnification unlock the radial test?

**Answer: No.** exp9 is genuinely higher magnification (the foam fills ~50% of the
frame vs Foam A ~22%, exp8 ~6%), and its per-frame segmentation is clean, but it is
a **coarse, rapidly-coarsening foam with few, temporally-unstable large bubbles**.
It has the **worst churn-per-bubble of any foam** and **zero** near-edge trusted
bubbles — the radial hypothesis is *not* testable on it. Trust the measurement, not
the eye: exp9 looks pristine and is the worst on the number that matters.

## Magnification proxy (the setup)
| foam | foam fraction of frame @f000 | frame-0 bubbles | ≈ px/bubble |
|---|---|---|---|
| **A** (exp1) | ~22% | 142 | ~2,000 |
| **D** (exp8) | ~6% | 26 | ~3,000 |
| **E** (exp9)** | **~50%** | 34 (@h=8) | **~19,000** (~10× Foam A) |

exp9 has ~10× more pixels per bubble than Foam A — but ~4× **fewer** bubbles. It is
a *coarse* foam imaged large, not a *fine* foam finally resolved.

## Segmentation transfer — params do NOT transfer; re-tuned (# DECISION)
The Foam-A `h_maxima=4.0` **over-segments** exp9's large bubbles: false interior
watershed splits inflate the count 141@f000 (real ≈ 34). Sweep → **`h_maxima=8`**
removes the false splits (n@f000 141→34, Plateau 3-way 0.989→1.000) and is clean at
early/mid/late (34/13/7 bubbles, Plateau **1.00** everywhere; overlays in
`qc/exp9/seg_exp9_h8_*`). exp9 is segmented with the `H_MAXIMA` override; the global
default stays 4.0 for the Foam-A/C regime. Small edge bubbles ARE segmented (not
missed) — this is not exp8's under-segmentation problem.

## THE CHURN & NEAR-EDGE COMPARISON (the numbers that decide it)
Full 99-frame runs, current tracker (keep_larger); exp9 at h=8:

| metric | Foam A (exp1) | Foam D (exp8) | **Foam E (exp9)** |
|---|---|---|---|
| frame-0 bubbles | 142 | 26 | 34 |
| **reorg-births per real bubble** | **9.75** | 19.08 | **20.68** ← WORST |
| merges | 791 | 181 | 241 |
| trusted bubbles / eligible | 80 / 142 | 6 / 26 | **4 / 34** |
| **trusted fraction of eligible** | **0.56** | 0.23 | **0.12** ← WORST |
| **trackable area fraction** | **0.29** | 0.02 | **0.00** ← WORST |
| **near-edge trusted-bubble count** | **11** | 0 | **0** |
| stability gate | proceed | confounded | **underpowered** |

Radial-bin occupancy (near-edge bin 0 → far): Foam A `{0:11,1:47,2:29,3:20,4:17,5:19,6:3,7:3}`
vs Foam E `{3:1,4:2,7:1}` — **4 trusted bubbles total, none near the edge.**

## Why clean single frames still churn
Per-frame Plateau is 1.00, yet reorg-births/bubble is the highest of all foams.
Two intrinsic causes, neither fixable by parameters:
1. **Coarse + fast:** only 34 bubbles, coarsening 34→7 over the session (241 merges).
   Rapid topological turnover means few bubbles survive ≥5 frames with a continuous
   area (only 4 do), and the near-edge ones merge away first.
2. **Large textured interiors are temporally unstable:** the big bubbles carry
   internal shading (quasi-2D confinement/illumination); the watershed's interior
   distance-maxima jitter frame-to-frame, so a bubble that is one clean region at
   frame *t* can split/relabel at *t+1* → reorganization-births. Small uniform
   bubbles are paradoxically more *temporally* stable than large shaded ones.

## Radial test — NOT run (per the pre-registered conditional)
exp9 is worse than Foam A on every trackability metric; gate = underpowered; 0
near-edge trusted bubbles. Running the radial test would produce a guaranteed
underpowered null. **Not run.**

## What this means for the radial hypothesis
Neither low magnification (exp8: fine foam, under-resolved → 0 near-edge) nor high
magnification (exp9: coarse foam, temporally-unstable large bubbles → 0 near-edge)
unlocks it. **Higher magnification alone did not resolve the churn.** The radial
test needs a foam that is *simultaneously* fine (many bubbles), well-resolved
(stable segmentation), slowly-coarsening (bubbles persist), AND with a populated
near-edge — no available foam (A/C/D/E) satisfies all four. **Foam A remains the
only foam reaching "proceed"** (11 near-edge trusted), yet even there the radial
test was a null within noise (Module-4 session: Spearman ρ=+0.096, CI covers 0).
The bottleneck is not a single imaging knob; it is the joint fine-and-stable-and-
persistent-near-edge requirement.
