# Training Disruption Reference Note

Purpose: quick internal reference for future building and optimization. This note is intentionally opinionated toward StrideIQ product value, not generic endurance-literature summary.

## Bottom line

`Feely et al.` is the actionable paper here.

It is useful because it studies the performance cost of training disruption, not the average "best" marathon template. That maps to athlete decision support, expectation calibration, comeback handling, and interruption-aware coaching.

`Muniz-Pumares et al.` and `Doherty et al.` are useful only as boundary/context papers:
- `Muniz` tells you what large populations trend toward.
- `Doherty` tells you which training variables broadly correlate with faster times.
- Neither should be turned into hard N=1 coaching rules.

## Most useful paper: Feely et al.

### Why it matters

This paper is about disruption cost, timing, and asymmetry. That is much closer to a real coaching or intelligence surface than "faster marathoners do more easy running."

### What the paper actually found

From `292,323` runners, `509,979` marathons, and `15,697,711` logged activities:

- Over `50%` of runners experienced short disruptions of `<=6` days.
- A `7-13 day` longest disruption was associated with about a `4.25%` finish-time penalty versus the same runner's undisrupted marathon.
- Longer disruptions cost more.
- Late disruptions hurt more than early disruptions.
- A `21-27 day` disruption `3-7 weeks` before race day was associated with an almost `10%` finish-time penalty, versus about `6%` for a similar-length disruption earlier in the block.
- Faster runners were hit harder than slower runners.
- Males, younger runners, and faster runners showed greater disruption cost than females, older runners, and slower runners.

### Why that matters for StrideIQ

This is not valuable because it says "consistency matters." Everyone already knows that.

It is valuable because it gives a defensible prior for interruption-aware intelligence:

- "This interruption likely changed expected race-day performance."
- "The timing of this interruption matters, not just the duration."
- "A late-block interruption is not interchangeable with an early-block interruption."
- "The same missed time may cost different athletes differently."

That is a much better product surface than generic mileage advice.

## Product use that fits StrideIQ

Good uses:

- disruption-cost prior for race expectation recalibration
- interruption-aware coaching language after illness, injury, travel, or life breaks
- comeback/ramp guidance that acknowledges timing and likely lost fitness
- founder review surfaces that compare predicted cost vs actual athlete response over time
- future N=1 refinement: "for this athlete, missed-time cost appears milder/steeper than population prior"

Bad uses:

- turning population slowdown percentages into deterministic athlete truth
- assuming all no-run gaps are injury gaps
- treating Strava silence as guaranteed non-training
- building rigid rules like "7 days off means X workout reduction"
- using this to overprotect athletes and suppress productive stress automatically

## Important limitations

The paper itself has limitations that matter for product design:

- It only sees logged Strava activity.
- It cannot identify why the disruption happened.
- It cannot distinguish injury from illness from motivation from unlogged training.
- It only includes runners who actually made it to a marathon, which likely understates the real cost of severe late disruptions because some athletes would have withdrawn.

For StrideIQ that means:

- use this as a prior, not a verdict
- combine it with athlete-specific context
- prefer probabilistic phrasing over false certainty
- refine with N=1 outcome history whenever available

## Why Muniz is secondary, not central

`Muniz-Pumares et al.` is useful mainly as a population-shape paper.

It found that across `119,452` runners and `151,813` marathons, faster groups tended to carry much more total volume, mostly by increasing `Z1`, while `Z2` and `Z3` stayed relatively stable. That is directionally sensible, but it naturally converges toward a homogeneous low-risk conclusion at population scale.

That is fine as a guardrail against obviously stupid advice. It is not the core of what StrideIQ should surface.

## Why Doherty is tertiary

`Doherty et al.` is a broad association paper, useful mainly to confirm that common training variables do matter at the population level.

Across `85` studies and `137` cohorts, it found negative associations between marathon finish time and variables such as weekly distance, longest run, number of `>=32 km` runs, hours per week, and training pace. Useful as background. Not enough for athlete-specific coaching logic on its own.

## StrideIQ design implication

If this literature informs product work, the winning move is not:

"tell athletes to do more easy running because the population did."

It is:

"understand when training was interrupted, how close it was to the goal event, what type of interruption it likely was, what the likely performance cost is, and whether this athlete historically rebounds faster or slower than population expectation."

That is much closer to a real intelligence layer.

## Citations

1. Feely C, Lawlor A, Smyth B, Caulfield B. *Estimating the cost of training disruptions on marathon performance.* Frontiers in Sports and Active Living. 2023. DOI: [10.3389/fspor.2022.1096124](https://doi.org/10.3389/fspor.2022.1096124)  
   Full text: [Frontiers](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2022.1096124/full)

2. Muniz-Pumares D, Hunter B, Meyler S, Maunder E, Smyth B. *The training intensity distribution of marathon runners across performance levels.* Sports Medicine. 2025. DOI: [10.1007/s40279-024-02137-7](https://doi.org/10.1007/s40279-024-02137-7)  
   Abstract/source page: [Springer](https://link.springer.com/article/10.1007/s40279-024-02137-7)

3. Doherty C, Keogh A, Davenport J, Lawlor A, Smyth B, Caulfield B. *An evaluation of the training determinants of marathon performance: A meta-analysis with meta-regression.* Journal of Science and Medicine in Sport. 2020;23(2):182-188. DOI: [10.1016/j.jsams.2019.09.013](https://doi.org/10.1016/j.jsams.2019.09.013)  
   Indexed record: [PubMed](https://pubmed.ncbi.nlm.nih.gov/31704026/)

## Source access note

In this session, `Feely` full text and `Muniz` abstract/source page were directly accessible. `Doherty` was identifiable and citable via indexed record/title/DOI, but detailed notes here should be treated as abstract-level/background use unless we pull the full paper in a later research pass.
