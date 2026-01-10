# Coaching Knowledge Base Structure

This folder contains Michael's lifetime of running knowledge, encoded for AI retrieval.

## Purpose
When the AI generates race plans, insights, or advice, it retrieves relevant sections from this knowledge base to ensure recommendations align with Michael's philosophy.

## How It Works
1. **Documents are chunked** and indexed for semantic search
2. **When generating plans**, the AI retrieves relevant sections
3. **Knowledge is layered**: General principles → Race-specific → Athlete-specific

## Folder Structure

```
KNOWLEDGE_BASE/
├── 00_STRUCTURE.md           ← You are here
├── 01_PHILOSOPHY.md          ← Core coaching beliefs
├── 02_PERIODIZATION.md       ← Training phase structure
├── 03_WORKOUT_TYPES.md       ← When to use each workout
├── 04_RECOVERY.md            ← Recovery protocols
├── 05_RACE_PREP.md           ← Race-specific preparation
├── 06_RED_FLAGS.md           ← Warning signs and when to back off
├── 07_NUTRITION_TIMING.md    ← Fueling strategies
├── 08_MENTAL_GAME.md         ← Psychology of racing
├── races/
│   ├── boston.md             ← Boston Marathon specifics
│   ├── tokyo.md              ← Tokyo Marathon specifics
│   ├── berlin.md             ← Berlin Marathon specifics
│   └── ...
└── distances/
    ├── 5k.md                 ← 5K training principles
    ├── 10k.md                ← 10K training principles
    ├── half_marathon.md      ← Half marathon principles
    ├── marathon.md           ← Marathon principles
    └── ultra.md              ← Ultra principles
```

## How to Add Knowledge

Each document should follow this template:

```markdown
# [Topic Title]

## Summary
[2-3 sentence summary for quick retrieval]

## Key Principles
- [Principle 1]
- [Principle 2]
- [Principle 3]

## Details
[Expanded explanation]

## When to Apply
[Specific situations where this knowledge applies]

## Common Mistakes
[What people often get wrong]

## Michael's Notes
[Personal observations and insights from experience]
```

## Priority for Population

Fill these first (highest impact):
1. `01_PHILOSOPHY.md` - Your core beliefs about training
2. `02_PERIODIZATION.md` - How you structure training phases
3. `05_RACE_PREP.md` - Race-specific preparation
4. `races/boston.md` - Since it's the most iconic major

## Integration with System

This knowledge base feeds into:
- **Race plan generation** - AI retrieves relevant principles
- **Insight generation** - Advice uses your voice and philosophy
- **Correlation interpretation** - Explains "why" behind patterns
- **Recovery recommendations** - Your protocols, not generic advice


