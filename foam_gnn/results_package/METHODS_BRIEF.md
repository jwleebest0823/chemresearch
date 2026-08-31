# Methods brief

One page, in pipeline order. Details and every `# DECISION` justification live in the
repository under `docs/`.

## Imaging

Quasi-2D soap-foam rafts between plates, brightfield, illuminated from below. 8-bit
grayscale, 1024×1280 px. Colour is a non-physical sensor cast and is discarded — no film
thickness is inferable from intensity. Frame interval 30 s (Foams A, C) or 10 s (Foam F).
No pixel-size calibration, so areas are px² and rates px²/s; the physics of interest is
scale-free. Foam A is one raft in two runs separated by a 2.5-min gap; identities are
never matched across that gap. Foam C is one raft; Foam F is an independent raft.

## Detection

**Cellpose-SAM, zero-shot** — no foam-specific training. Inference on GPU (Colab);
~13 s/frame, versus ~64 min/frame on the available CPU, which is why it is run externally
and the label maps imported.

**One post-processing step.** Raw Cellpose also segments the background plate into
blobs (on one frame, 335 of 377 "objects" were plate). Objects are kept only if ≥50% of
their pixels fall inside an independently computed **foam mask** — edge-density map →
Li threshold → morphological close → largest connected component → fill holes, taken from
the raw image and never from Cellpose's output, so it cannot be tuned to flatter the
detector. The criterion is a majority vote and is inert between 0.10 and 0.90 (measured),
i.e. not a tuned threshold.

Detection was **not** expanded to tile the foam. That was implemented and rejected: the
hand labels leave 25% of foam interior unlabelled (it is film and Plateau border), so
expansion moved areas and neighbour counts *away* from truth and cost 0.12 F1.

## Tracking

Per-frame detections are linked into identities by overlap and centroid/area cost, with:
merges inheriting the larger parent's identity (never minting a new one); a dormancy
window so a one-frame detection dropout is not a death; and retroactive retirement of
identities whose separation does not persist. **Neighbour graphs use gap-bridged
adjacency**: each unlabelled pixel within a per-frame, scale-adaptive distance is assigned
to its *nearest* label before adjacency is measured, so two bubbles sharing a thin film
count as neighbours. Over-bridging is structurally impossible — nearest-label assignment
means an intervening bubble always separates two non-neighbours.

## Trusted set

Physics is fitted only on identities the tracker follows reliably: bubbles present in the
first frame, in runs of ≥5 consecutive frames with no gap, no merge, and no large
area jump. A **dropout-and-recovery filter** additionally removes V-shaped area traces
(a large drop that returns to its prior value within two frames) — a real bubble cannot
lose 40% of its area and get it back. This is survivorship selection by construction and
is not an unbiased sample for absolute coarsening rates; it is valid for the within-set
comparisons reported.

## Estimating K, and why least squares was rejected

The model `dA/dt = K·(n − 6)` is a line **through the origin** (a hexagon neither grows
nor shrinks), so K is a through-origin slope. Least squares weights every measurement by
`(n − 6)²`, which on this data gave **1.2% of rows 48% of the fit weight** — those rows
being giant flickering bubbles — and flipped K's sign at short horizon.

**Shipped estimator: the median of the per-point slopes, `median(y/x)`** — the natural
robust analogue of a through-origin fit, since each point contributes one independent
slope through the origin. Benchmarked against a known K = 0.35 over 200 replicates: at
the contamination rate measured in the data, least squares was biased −0.093 with an
inter-replicate spread of 1.04 (i.e. unusable at a quantity of size 0.35), while the
robust estimator was unbiased with spread 0.009. Theil–Sen is reported as an independent
cross-check and agrees throughout. Least squares is still reported alongside, so the
difference is visible rather than hidden.

## Uncertainty and out-of-sample testing

Every confidence interval is a **cluster bootstrap resampling whole bubbles**, not
individual rows: a bubble's measurements are correlated across frames, and resampling
rows would fake significance. 200 resamples, 95% percentile intervals.

Every comparative claim is **out-of-sample**. K is fitted on one epoch or session and
scored on a held-out one; model comparisons use leave-one-**foam**-out, with a foam's
sessions never split across train and test. "Beats persistence" is a paired bootstrap on
the *difference* in error under the same resampled bubbles, and requires the whole
interval to favour the model — interval overlap alone is only a weak proxy.

## Reproducibility

167 automated tests. The 14 ground-truth masks are checksum-verified unmodified at the
end of every session. All figures and tables in this package regenerate from
`build_results_package.py`.
