# Scale-aware hybrid seeding — tested, swept, and **not shipped**

This implements and evaluates the fix I recommended at the end of
`docs/foamc_fragmentation.md` §5: *h_maxima for large bubbles, one-marker-per-blob only
for small ones.* **It does not work.** I built it, plus two stronger variants and an
at-source alternative, swept every parameter, and none satisfies the dual constraint.
No code in `src/` changed. This document is the evidence and the recommendation.

Driver reproducing every number: `dev/hybrid_seeding_sweep.py`.

## 0. Verdict up front
| design | Foam A (F1 / count vs GT) | Foam C trend | robust? | ship? |
|---|---|---|---|---|
| **A** h_maxima only | ❌ F1 0.696–0.800 (vs 0.870–0.941) | ✅ falls | ✅ | no |
| **B** hybrid ∪ size cap *(as specified)* | ❌ F1 0.76–0.79, +19% count | ❌ rises | ✅ (insensitive) | no |
| **C** shattered-basin suppression | ✅ only at N≥8 | ✅ only at N≤3 | ❌ sign flips at N=3→4 | no |
| **D** at-source (Sato scale) | ✅ only at current scales | ❌ rises at every scale | — | no |

The Foam A and Foam C requirements are satisfied by **disjoint** parameter ranges in
every design. There is no setting that meets both, so there is nothing to ship.

**A caveat that governs the whole document:** Foam C has **no ground truth**. Its
requirement is only that the count must *fall* through a coarsening sequence, and the
h_maxima counts are used as an independent *reference*, never as truth.

## 1. Design A — h_maxima seeding only
The purest form of "use h_maxima for large bubbles". It gets the **count** roughly right
on Foam A but finds the **wrong partition**:

| exp1 frame | GT | h_maxima count | **F1@0.5** | current F1 |
|---|---|---|---|---|
| f000 | 124 | 126 | **0.696** | 0.870 |
| f049 | 84 | 85 | **0.722** | 0.871 |
| f097 | 63 | 76 | **0.763** | 0.921 |
| f148 | 46 | 57 | **0.738** | 0.899 |
| f024 | 99 | 98 | **0.761** | 0.880 |
| f073 | 70 | 86 | **0.782** | 0.921 |
| f120 | 52 | 58 | **0.800** | 0.941 |

Foam C: 274 → 245 → 222 → 228 → 212 (f000/24/49/73/97) — essentially physical. **So
h_maxima fixes Foam C and costs 0.10–0.20 F1 on Foam A.** Right number of bubbles, wrong
bubbles: it simultaneously under-segments some regions and over-segments others, which
cancels in the count and destroys the matching. This alone rules out any design in which
h_maxima *replaces* the blob seeding.

## 2. Design B — the hybrid exactly as specified, with the mandatory sweep
h_maxima seeds **∪** one seed per unseeded interior blob whose area is below a
scale-adaptive cap. `# DECISION`: the cap is `q ×` the *median h_maxima basin area in
that same frame* — the frame's own estimate of a typical bubble — so it is not a pixel
constant and transfers across magnification.

| | q=0.05 | q=0.1 | q=0.2 | q=0.4 | q=0.8 |
|---|---|---|---|---|---|
| exp1 f000 (GT 124) | 147 / 0.77 | 147 / 0.77 | 148 / 0.76 | 148 / 0.76 | 148 / 0.76 |
| exp1 f049 (GT 84) | 92 / 0.78 | 93 / 0.78 | 94 / 0.79 | 94 / 0.79 | 94 / 0.79 |
| exp1 f097 (GT 63) | 82 / 0.79 | 82 / 0.79 | 82 / 0.79 | 82 / 0.79 | 82 / 0.79 |
| **exp3 f000** | 498 | 538 | 551 | 554 | 554 |
| **exp3 f049** | 980 | 1128 | 1193 | 1204 | 1204 |
| **exp3 f097** | 1020 | 1186 | 1241 | 1258 | 1260 |

**It fails both requirements at every q.** Foam A is over-segmented by ~19% with F1 down
to 0.76–0.79, and Foam C still rises (498 → 1020 even at the most aggressive cap).

Note the sweep result is the *opposite* of last session's knife-edge failure: a 16×
change in q moves Foam A by <1% and Foam C f097 by 24% — the parameter is **robust and
robustly wrong**. The reason is mechanistic and worth recording:

> **A size cap cannot separate fragments from small bubbles, because the fragments are
> the smaller population.** A large bubble cut into 98 pieces produces 98 *tiny* blobs.
> Any cap loose enough to admit genuine small bubbles admits the fragments too; at
> q=0.05 it is already excluding real bubbles while 1020 fragments survive.

This is the core reason the assigned design cannot work, independent of tuning.

## 3. Design C — shattered-basin suppression (the strongest variant)
Since h_maxima seeds *hurt* Foam A (§1, §2), the only structurally sound use of h_maxima
is as a **detector of shattering**, not as a seed source. `# DECISION`: keep
one-marker-per-blob everywhere — the rule that preserves Foam A and that fixed the
ratchet — and drop blob seeds **only inside an h_maxima basin holding more than N
eligible blobs**, replacing them with that basin's single h_maxima seed. `N=∞` reproduces
the shipped segmenter exactly, so this degrades to current behaviour rather than
replacing it, and the one-marker-per-region invariant is preserved by construction
(every kept blob gets one marker; every suppressed basin gets one).

**Foam A — count / F1 (basins suppressed):**

| frame | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=∞ (current) |
|---|---|---|---|---|---|---|---|
| f000 (GT 124) | 105 / 0.786 (65) | 111 / 0.817 (29) | 114 / 0.832 (19) | 116 / 0.850 (11) | 118 / 0.851 (6) | 121 / 0.865 (1) | **122 / 0.870 (0)** |
| f049 (GT 84) | 73 / 0.803 (36) | 75 / 0.818 (20) | 76 / 0.850 (11) | 79 / 0.859 (7) | 80 / 0.866 (1) | 79 / 0.871 (0) | **79 / 0.871 (0)** |
| f097 (GT 63) | 58 / 0.893 (24) | 58 / 0.893 (13) | 58 / 0.909 (7) | 63 / 0.921 (2) | 63 / 0.921 (0) | 63 / 0.921 (0) | **63 / 0.921 (0)** |

**Foam C exp3 — count:**

| frame | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=∞ |
|---|---|---|---|---|---|---|---|
| f000 | 290 | 305 | 328 | 351 | 374 | 399 | 554 |
| f049 | 255 | 304 | 339 | 374 | 385 | 455 | 1185 |
| f097 | 233 | 275 | 346 | 385 | 429 | 487 | 1230 |
| **trend** | ✅ falls | ✅ falls | ❌ rises | ❌ rises | ❌ rises | ❌ rises | ❌ rises |

**The two requirements need disjoint ranges.** Foam A holds its F1 only at N≥8; Foam C
becomes physical only at N≤3. At the best Foam-C setting, N=3, Foam A **undercounts by
10–11%** (111 vs 124, 75 vs 84, 58 vs 63) and loses ~0.05 F1 — well outside "within a few
percent".

### 3.1 Robustness — it fails, and in the worst possible way
N is integer-valued, so the smallest perturbation available is already ±33%. Around the
best Foam-C setting N=3:

| | N=2 | **N=3** | N=4 |
|---|---|---|---|
| exp3 f000 | 290 (−5%) | **305** | 328 (+8%) |
| exp3 f049 | 255 (−16%) | **304** | 339 (+12%) |
| exp3 f097 | 233 (−15%) | **275** | **346 (+26%)** |
| exp1 f000 | 105 (−5%) | **111** | 114 (+3%) |
| **Foam C trend** | falls ✅ | **falls ✅** | **rises ❌** |

A single step from N=3 to N=4 swings Foam C f097 by **+26%** (over the ±20% bar) and,
decisively, **flips the sign of the physics** — the count trend goes from falling to
rising. A parameter whose one-unit change inverts the qualitative conclusion is
knife-edge in the strongest sense. **Not shipped**, for the same reason I refused the two
candidates last session.

### 3.2 The regions-per-reference metric — improves, but reveals the real problem
| frame | variant | regions | median | p90 | **max** |
|---|---|---|---|---|---|
| exp3 f049 | current | 1185 | 2.0 | 11 | **98** |
| exp3 f049 | N=8 | 455 | 1.0 | 4 | **8** |
| exp3 f049 | N=3 | 304 | 1.0 | 3 | **4** |
| exp3 f097 | current | 1230 | 2.5 | 9 | **99** |
| exp3 f097 | N=8 | 487 | 2.0 | 5 | **8** |
| exp3 f097 | N=3 | 275 | 1.0 | 2 | **3** |

It improves dramatically — but the *diagnostic* value here is larger than the fix value.
**At N=8 the catastrophic tail is gone (max 98 → 8) at essentially zero Foam A cost, and
Foam C still rises 399 → 455 → 487, still ~2.3× the h_maxima reference.** So the
over-segmentation is **not concentrated in a few shattered bubbles** — removing those
entirely does not make the trend physical. It is **broad and distributed**: a median of
~2 regions per bubble across the whole frame. That is a different disease from the one
`docs/foamc_fragmentation.md` §2 emphasised (the max of 98), and it is why a seeding-level
rule cannot cure it.

## 4. Design D — fix at source (Sato ridge scale), seeding unchanged
If the `interior = film < threshold` decomposition is broadly wrong, the ridge filter is
the natural suspect. Sweeping its scales, seeding untouched:

| | (1.0,) | (1.0, 2.0) | **(1,2,3) current** | (2.0, 3.0) | (2,3,4) |
|---|---|---|---|---|---|
| exp1 f000 (GT 124) | 157 / 0.541 | 120 / 0.861 | **122 / 0.870** | 122 / 0.870 | 126 / 0.800 |
| exp1 f049 (GT 84) | 20 / 0.019 | 76 / 0.875 | **79 / 0.871** | 78 / 0.864 | 78 / 0.840 |
| exp1 f097 (GT 63) | 11 / 0.054 | 63 / 0.921 | **63 / 0.921** | 61 / 0.935 | 62 / 0.896 |
| exp3 f000 | 663 | 596 | 554 | 607 | 576 |
| exp3 f049 | 835 | 1091 | 1185 | 1523 | 1436 |
| exp3 f097 | 761 | 1077 | 1230 | 1626 | 1597 |
| **Foam C trend** | ❌ | ❌ | ❌ | ❌ | ❌ |

**Every scale set rises on Foam C.** The single-scale (1.0,) option flattens the trend
most but annihilates Foam A (F1 0.019 at f049). The current (1,2,3) is at or near the
Foam A optimum already. **The ridge scale is not the knob** — this rules out the cheapest
version of `foamc_fragmentation.md` §5 option 2.

## 5. What this means, and what to try next
Four designs across two different layers (seeding and ridge detection) all fail the same
way: **any change large enough to make Foam C physical damages Foam A.** Combined with
§3.2 — the excess is distributed at ~2× everywhere, not concentrated — the honest reading
is that Foam C's interiors are not recoverable by re-arranging markers on top of this
`interior` mask. The hand-built ridge/threshold cascade is being asked to work at a
contrast and density it was never calibrated for, and Foam A is the only foam that
calibration was ever validated against.

Recommendation, in the order I would do it:

1. **Scope the claim, keep the guard.** The fragmentation guard already fails loud on
   Foam C from frame ~11. Leave it active and state in the paper that segmentation is
   GT-validated on Foam A only, and that Foam C mid/late frames are not currently
   measurable. This costs nothing and is already true.
2. **Get a real Foam C target.** Label `eval/exp3/f000` and `f001` (554 / 525 regions —
   the only visually trustworthy Foam C preseeds). Every Foam C number in this document
   is measured against an h_maxima *reference* whose own accuracy is unknown; without GT
   we cannot tell a 2× over-segmentation from a 2× under-detection by h_maxima. This is
   the cheapest way to convert the whole Foam C discussion from inference to measurement.
3. **A learned per-frame detector** (candidate #2 in `segmentation_candidate_plan.md`).
   This is the real fix: it does not rely on a hand-tuned ridge/threshold cascade, and it
   is now supported by four independent failed attempts to make the cascade transfer.
   Foam A's 14 GT frames plus a Foam C pair would be the training set.

I would **not** spend more effort on marker-level rules. The parameter sweeps above are
the argument: the failure is not in how markers are placed.

## 6. Integrity checks
* **The 14 human Foam A GT masks were not touched** — `src/` was never modified and the
  git tree was clean throughout. SHA-256 recorded for all 19 committed human masks; e.g.
  `eval/exp1/f000.png = 4c9ed952…`, `eval/exp1/f097.png = 4c65c3d0…`,
  `train/exp1/f024.png = b8416bfc…`.
* **The fragmentation guard remains active** (`raise`, ratio 1.50, patience 3) and still
  fires on Foam C at frame 11. Nothing here weakened it.
* **No Foam C preseeds were regenerated** — that step was conditional on a working fix.
* Full test suite: 141 passed (unchanged; no source was modified).
