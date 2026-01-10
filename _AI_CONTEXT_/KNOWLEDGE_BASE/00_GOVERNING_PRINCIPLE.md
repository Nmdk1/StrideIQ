# Governing Principle: Athlete-First Plan Design

**Source:** Michael Shaffer  
**Date:** January 7, 2026  
**Status:** CORE PRINCIPLE - Governs all plan generation

---

## The Principle

> "The books are the foundation, but training philosophy has evolved beyond them. We need to **suit plans to athletes, not suit athletes to plans.**"

---

## What This Means

### The Books Are Building Blocks, Not Blueprints

- Sources A through H = **foundational knowledge**
- They provide workout types, periodization concepts, pace calculations
- They are **correct but incomplete**—they describe what works in general, not what works for YOU

### The Athlete Is The Blueprint

- The athlete's data, history, responses, and constraints define the plan
- Book principles are **selected and adapted** based on what the individual needs
- No athlete should be forced into a template

### Evolution Beyond The Books

Training philosophy has moved past:
- "Pick a plan and follow it"
- "You're a Source A runner" or "You're a Source B runner"
- One-size-fits-all periodization
- Fixed plans that don't adapt to the individual

Training philosophy has moved toward:
- Individual response patterns discovered from data
- Dynamic adjustment based on what's actually working
- Blending methodologies based on athlete characteristics
- Plans that evolve with the athlete

---

## How This Governs The AI

### When Generating Plans

1. **Start with the athlete**, not the methodology
2. **Query what's working** for this individual (correlation engine data)
3. **Select building blocks** from knowledge base that match this athlete's patterns
4. **Construct the plan** around the athlete's constraints, goals, and responses
5. **Adapt continuously** based on outcomes

### When Retrieving From Knowledge Base

- Treat book entries as **options**, not mandates
- Weight entries by relevance to THIS athlete's profile
- Allow blending across methodologies freely
- Never say "Source A recommends X" — say "Based on your response patterns, X fits you"

### When An Athlete Doesn't Fit A Book's Model

- This is EXPECTED, not exceptional
- The athlete is not wrong; the book's model is limited
- Adapt the principles; don't force the athlete

---

## Contrast With Traditional Coaching Software

| Traditional Approach | This System |
|---------------------|-------------|
| "Pick a cookie-cutter plan" | "Here's what your data says you need" |
| Fixed plans you follow | Adaptive plans that follow you |
| Athlete adjusts to plan | Plan adjusts to athlete |
| Methodology-branded | Methodology-agnostic |
| "Trust the process" | "Trust your data" |

---

## Implementation Notes

- This principle overrides any specific book recommendation
- When in conflict, athlete data wins over book principle
- The AI should explain WHY a recommendation fits THIS athlete, not cite which source it came from
- Methodology sources stay internal (per existing Methodology Opacity Architecture)

---

## The Test

Before any recommendation, the AI should be able to answer:
> "Why does this fit THIS athlete specifically?"

If the answer is "because a book says so" — it's wrong.
If the answer is "because this athlete's data shows X, and this approach addresses X" — it's right.
