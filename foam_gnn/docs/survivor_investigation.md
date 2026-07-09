# Do small bubbles survive to the end? (mentor side-investigation)

**Short answer: essentially no.** Coarsening wins, exactly as predicted — small
bubbles merge or vanish early. The handful of small bubbles that *appear* to be
present in the final frames are almost entirely **segmentation-flicker /
reorganization-birth artifacts**, not real survivors. Requiring a genuine,
reliably-tracked identity leaves **one** long-lived small bubble in Foam A and
**zero** in the representative Foam C session — and the one real survivor sits in
the **interior**, not near the evaporation edge.

## Definition (stated up front, chosen NOT to bias toward finding survivors)
`# DECISION`
* **Small** is *relative and per-frame*: a bubble is "small at frame *t*" when its
  area is below the **P33** (bottom third) of that frame's area distribution.
  Per-frame + relative so a fixed-size bubble automatically becomes "small" as its
  neighbours coarsen (the physically interesting case), with no absolute px cutoff
  biasing the count. (P25 reported alongside for sensitivity.)
* **Small for most of its life**: below-P33 in ≥ 50 % of the frames it appears in.
* **Long-lived**: its stable id is still present in the **final ~10 %** of the
  session (frames 89–98 of a 99-frame run).
* **Reliable survivor** (the crux): a long-lived small candidate whose identity is
  *also* covered by a **trusted segment** — `foam_gnn.stability`: frame-0 origin,
  ≥ 5 continuous frames, no merge, continuous area — that itself reaches the
  final-10 % window. Everything else is flagged **flicker-suspect**.

Why the tiering matters: a bubble id that first appears late is a
**reorganization birth** ("bubbles never appear" — every id above the frame-0 max
is a segmentation-churn artifact), *not* a bubble that survived from the start.

## Results

| | Foam A (`exp1_run0`) | Foam C (`exp3`) |
|---|---|---|
| frames / final-window start | 99 / frame 89 | 99 / frame 89 |
| frame-0 bubbles | 142 | 315 |
| bubbles present in final 10 % | 225 | 865 |
| **naive** small candidates (P33) | 90 | 436 |
| …of which frame-0 origin | **1** | **0** |
| **reliable small survivors** | **1** (id 118) | **0** |

**~99 % of the naive "small survivors" are flicker.** On Foam A, 90 candidates
collapse to 1 real one; on Foam C, 436 collapse to 0. The naive count is dominated
by short-lived reorganization births that momentarily occupy the final frames.

### The one real survivor — Foam A bubble 118
Genuinely long-lived and small:
* present **continuously in frames 0–95** (96/99, zero gaps), no merge;
* area ≈ 1,770 px² → 2,200 px² (min 930), i.e. it stays a few-thousand-px² bubble
  while neighbours coarsen past 10 k — so it is increasingly "small" *relative* to
  the frame, which is exactly the anomalous-persistence case the mentor asked about;
* distance-to-evaporation-edge ≈ **107 px** (stable 109 → 105): an **interior**
  bubble.

The overlay (`qc/survivors/exp1_overlay.png`) shows id 118 in lime at frame 0
(a small bubble, lower-centre) and still present at frame 95, ringed by bubbles
that have coarsened around it. The red flicker-suspect candidates are peripheral
reorganization births.

### Spatial distribution — survivors are central, not near-edge
Distance-to-evap-edge (px; **larger = closer to centre**), final-window means:

| population | n | p25 | median | p75 |
|---|---|---|---|---|
| Foam A — all bubbles in final window | 225 | 26 | 66 | 141 |
| Foam A — reliable survivor (id 118) | 1 | — | **111** | — |
| Foam C — all bubbles in final window | 865 | 56 | 121 | 208 |
| Foam C — reliable survivors | 0 | — | — | — |

The single trustworthy long-lived small bubble sits well into the interior
(111 px vs a 66 px median). There is **no reliable near-edge small-survivor
population** in either session. `qc/survivors/exp3_overlay.png` shows the Foam C
null directly: the final frame is covered in red flicker-suspect candidates and
**zero** lime survivors.

## What this means
1. **For the mentor's question:** small bubbles do not reliably survive to the end
   — they coarsen away early, and apparent survivors are overwhelmingly tracking
   artifacts. A rare genuine exception exists (Foam A id 118), but it is a single
   interior bubble, not a population.
2. **For the near-edge / radial hypothesis:** the reliably-trackable long-lived
   small bubbles are *interior*, not near the evaporation edge. This is consistent
   with the recurring project finding — near-edge small bubbles are the hardest to
   track (they merge/vanish first), so they are absent from the trusted set. The
   survivor investigation does **not** supply the near-edge population a radial
   test needs.

*Reproduce:* `python dev/survivors.py` (reads the cached segmentations under
`qc/cache/{exp1,exp3}`; writes `qc/survivors/`). Foams A (`exp1_run0`) and C
(`exp3`, representative session) analysed.
