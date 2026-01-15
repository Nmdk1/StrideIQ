# StrideIQ Research & Reference Knowledge Base

## Purpose

This directory contains research references, algorithms, datasets, and analytical methods that inform StrideIQ's development. The goal is **not** to copy products, but to extract **scientific methods** that enable precise, repeatable, actionable insights.

## Core Philosophy

```
NOT: Collect data → Apply generic model → Show score → Hope user engages
YES: Collect data → Find YOUR causal patterns → Surface when pattern predicts outcome → Recommend specific action
```

## Directory Structure

```
RESEARCH/
├── 00_REFERENCE_INDEX.md          # This file
├── 01_DATASETS.md                 # Research datasets (incl. Figshare 10M+ records)
├── 02_ALGORITHMS.md               # Computational methods to implement
├── 03_OPEN_SOURCE_TOOLS.md        # Useful libraries and code patterns
├── 04_HRV_RESEARCH.md             # HRV interpretation (counter-conventional findings)
└── 05_CORRELATION_METHODOLOGY.md  # Rigorous causation methodology
```

## Key Resources

### Primary Dataset
**Figshare Long-Distance Running Dataset**
- 10+ million training events
- 36,000+ athletes worldwide
- 2019-2020 training data
- See: `01_DATASETS.md`

### Critical Algorithm Priority
1. Efficiency Factor Trending (Runalyze)
2. Pre-Race State Fingerprinting (Custom)
3. TSB/ATL/CTL Training Load (fit.ly)
4. Critical Speed Model (GoldenCheetah)
5. Pace Decay Analysis (Custom)

See: `02_ALGORITHMS.md`

### User-Validated Finding
> "My best races were after the evening of my lowest HRV"

This contradicts conventional app wisdom. StrideIQ must discover individual patterns, not impose population norms.

See: `04_HRV_RESEARCH.md`

## Quick Reference: What Tests Must an Insight Pass?

| Test | Question | Failure Mode |
|------|----------|--------------|
| **Repeatability** | Does this pattern hold across multiple instances? | One-off coincidence |
| **Mechanism** | Is there a plausible physiological explanation? | Spurious correlation |
| **Actionability** | Can the athlete DO something with this? | Interesting but useless |
| **Falsifiability** | Can we test if this is wrong? | Unfounded belief |
| **Individuality** | Does this hold for THIS athlete, not just "athletes"? | Population-level noise |

---

*Last updated: January 2026*
