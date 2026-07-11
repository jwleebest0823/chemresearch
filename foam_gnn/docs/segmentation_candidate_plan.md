# Segmentation research plan — candidate methods (design only, for review)

**The failure to fix, stated precisely.** Current segmentation (FFT grid-notch +
marker-controlled watershed) is fine per-frame on the bubbles it resolves (~99%
Plateau-consistent junctions) but **temporally unstable on small and near-edge
bubbles**: ~10–20 reorganization-births per real bubble, so only ~15% of foam area is
reliably trackable and that 15% is the quiescent interior. Two distinct sub-failures:
- **(F1) detection floor** — the smallest / lowest-contrast / near-edge bubbles are
  missed or merged in a *single* frame (a per-frame accuracy problem);
- **(F2) temporal identity** — even *detected* bubbles are re-split / relabeled between
  frames, minting new ids (a temporal-consistency problem).

A method only helps the project if it improves **F2 for small near-edge bubbles**
(measured by `seg_temporal`: trusted-area coverage and reorg-birth rate in the
`(small, near-edge)` cell), validated per-frame against GT (`seg_eval`). Per-frame
accuracy alone (F1) is necessary but not sufficient — Gates 1–3 already showed the
interior-quiescent 15% carries no signal.

## Candidate assessment (against THIS failure, not generic merit)

### 1. Temporal marker-propagation watershed  ·  attacks F2 directly  ·  no GT
Seed frame *t+1*'s watershed from frame *t*'s **stable-ID labels**, warped by the
inter-frame drift the tracker already computes (`frame_offsets`). Identity is then
propagated *by construction*: a bubble that persists keeps its marker, so it cannot be
spuriously re-split/relabeled — directly removing reorganization-births. Merges appear
as two markers flooding one film-less region; genuine new bubbles are the unseeded
remainder.
- **Why it targets the failure:** F2 is *exactly* "identity not carried across frames";
  marker propagation carries it. Reuses existing watershed + drift → lowest effort.
- **Risks:** error accumulation (a bad frame propagates forward — mitigate with a
  per-frame re-detection pass and confidence reset); does **not** fix F1 (a bubble never
  detected can't be propagated), so near-edge bubbles the boundary mask drops stay lost;
  needs careful marker bookkeeping at merges/T2 deaths.
- **Cost:** low (days). **GT:** none (unsupervised). **Supervision:** none.

### 2. Adaptive-scale watershed markers  ·  attacks F1 (small bubbles)  ·  no GT
A single global `h_maxima` cannot seed both large and small bubbles (exp9 showed one
`h` over-segments large / under-segments small). Local, scale-adaptive seeding (h by
local distance-transform scale; multiscale h-maxima; contrast-normalized small-bubble
markers) raises small-bubble detection.
- **Why:** improves F1 in the dense/small regime, which *indirectly* lowers churn
  (more consistent detection ⇒ fewer flips).
- **Risks:** the smallest near-edge bubbles are at the imaging/contrast limit —
  diminishing returns; still per-frame (no F2 guarantee). Best as a *marker source* for
  #1, not standalone.
- **Cost:** low. **GT:** none. **Supervision:** none.

### 3. Cellpose / StarDist (learned per-frame instance segmentation)  ·  F1  ·  GT to fine-tune
Foam bubbles are morphologically cell-like (convex, tessellating); Cellpose (flow
fields) and StarDist (star-convex polygons) are built for crowded round objects and
give **instance labels directly** (no watershed-merge step). Pretrained models run
zero-shot; both fine-tune on small datasets.
- **Why:** strongest per-frame small-bubble **detection** (F1) — learned features beat
  hand-tuned ridge+watershed on low contrast. StarDist's polygon prior suits early
  convex bubbles; degrades for late polygonal dry foam (still roughly star-convex from
  the centroid).
- **Risks:** brightfield low-contrast films differ from the fluorescence/H&E data these
  were trained on → zero-shot transfer uncertain; **per-frame only → no F2** (must be
  paired with #1 for temporal identity); late-stage polygonal bubbles violate shape
  priors.
- **Cost:** medium (inference cheap; fine-tune + integration moderate). **GT:** zero-shot
  none; **fine-tune needs GT** (see GT budget note). **Supervision:** semi.

### 4. SAM2 video propagation  ·  attacks F2 by design  ·  no training (prompts)
SAM2 adds memory-based mask propagation across video — prompt an object once, it tracks
the mask forward. This is conceptually the closest match to F2.
- **Why:** temporal propagation is the thing we lack; strong learned boundaries.
- **Risks (high):** (a) designed for a *modest* number of prompted objects, not ~200
  auto-discovered bubbles — auto-prompting + re-seeding births is real engineering;
  (b) coarsening **violates SAM2's object-permanence assumption** — merges/T2 deaths may
  hallucinate persisting bubbles or fail; (c) small low-contrast bubbles are the weak
  spot of SAM-family appearance models; (d) heavy compute. Plain SAM (image) is worse:
  point/box prompts per bubble are impractical and "everything" mode over/under-segments
  small low-contrast objects.
- **Cost:** high (engineering + GPU). **GT:** zero-shot for inference; fine-tuning SAM is
  heavy. **Supervision:** none-to-heavy. → **scoped pilot only** (short clip), not a
  commitment.

### 5. μSAM / SAM fine-tune  ·  F1(+F2 via μSAM tracking)  ·  needs GT
micro-sam adds microscopy-tuned automatic instance segmentation + an annotation loop +
(experimental) tracking. Fine-tunes SAM on small microscopy sets.
- **Why:** foundation-model prior + microscopy tuning could lift F1 on our modality with
  few labels; μSAM's tracking touches F2.
- **Risks:** SAM fine-tuning is data-hungry relative to Cellpose; our GT budget is
  marginal; integration heavier than Cellpose.
- **Cost:** medium-high. **GT:** needs it. **Supervision:** semi. → after Cellpose if that
  underperforms.

### 6. FoamQuant  ·  domain-matched reference  ·  mostly no GT
Purpose-built foam analysis (segmentation + bubble tracking with T1/T2 handling), but
its heritage is largely **3D X-ray tomography of wet foams**, a different modality from
2D brightfield.
- **Why:** the only foam-specific option; its tracking encodes the right topology.
- **Risks:** modality mismatch (3D/tomography vs 2D brightfield low-contrast) → its 2D
  segmentation may not transfer; integration/uncertain fit.
- **Cost:** medium (evaluation). **GT:** none for its classical tools. → **reference
  baseline**, low commitment.

## Ranked recommendation
1. **Temporal marker-propagation watershed (+ #2 adaptive small-bubble markers).**
   Highest ROI: attacks F2 directly, no GT, builds on existing code. This is the first
   move and may raise `(small, near-edge)` coverage materially on its own. `# DECISION`.
2. **Cellpose (then StarDist) — zero-shot, then fine-tune on GT.** The per-frame small-
   bubble **detection** floor (F1). Feed its instance labels into the #1 propagation loop
   so detection (F1) and identity (F2) are fixed by the right tool each. Evaluate zero-shot
   first (no GT), fine-tune only if zero-shot is close.
3. **SAM2 video — scoped pilot** on one short dense clip, to measure whether temporal
   propagation survives coarsening topology and 200-object prompting before any
   commitment. Escalate only if 1–2 leave the `(small, near-edge)` cell empty.
4. **FoamQuant — reference baseline**; **μSAM — fallback** if Cellpose/StarDist
   underperform on our modality.

Everything is scored on the **same harness**: `seg_eval` (per-frame precision/recall/F1,
IoU, split/merge — stratified by size × edge-distance, at multiple IoU) on the labeled
frames, and `seg_temporal` (trusted-area coverage + reorg-birth rate, stratified) on all
frames, all **leave-one-foam-out** (fit/tune on one foam's GT, report on the other).

## Ground-truth budget note (a real tension to decide)
The ~15–20 labeled frames are currently scoped as an **evaluation** set (every metric
above is a test metric). If we also **fine-tune** Cellpose/StarDist/μSAM, those frames
must split into train vs test **by foam** (LOFO), which both shrinks the test set and
risks train/test leakage if a foam appears in both. Options: (a) keep all GT as *test*
and use only unsupervised methods (#1, #2, zero-shot #3/#4/#6) — cleanest; (b) label an
additional dedicated *train* set (another ~15–20 frames on one foam) so evaluation stays
untouched. **Recommendation:** start unsupervised (#1/#2) — no GT tension at all — and
decide on (b) only if a learned method is needed. Note: 15–20 frames with *every* bubble
labeled is thousands of instances, ample for Cellpose-style fine-tuning per-frame, but
the **frame/foam** count (not instance count) is what limits generalization and LOFO.

**STOP — awaiting approval of this plan before implementing any new segmentation method.**
