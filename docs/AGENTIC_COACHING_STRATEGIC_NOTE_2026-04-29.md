# Agentic Coaching Strategic Note — April 29, 2026

**Status:** Strategy note. Not a build authorization.  
**Read first:** `docs/FOUNDER_OPERATING_CONTRACT.md`  
**Related:** `docs/FRESH_EYES_BRIEF_2026-04-29_COACH_V2.md`, `docs/PRODUCT_MANIFESTO.md`, `docs/PRODUCT_STRATEGY_2026-03-03.md`

## Core Distinction

StrideIQ has been building a responsive coach: the athlete sends a message, the coach reads a packet, the coach responds. That is not the final product shape promised by the manifesto. It is a proving ground.

An agentic coach is different. It has standing context, runs in the background, prepares analysis before the athlete asks, and eventually shows up at meaningful moments on its own initiative within permissioned bounds.

This distinction matters because agentic coaching is probably the right destination for StrideIQ, but it is not the immediate rescue plan for Coach V2 quality failures.

## Current Crisis

The current Coach V2 failure is not mainly that chat is reactive. The observed April 27 production failure was more concrete:

- Same-turn pasted evidence was not parsed or used correctly.
- V2 fell back repeatedly with `packet_assembly_error`, so the canary was partly V1 fallback output.
- Race-day template structure dominated the actual reasoning task.
- The coach accepted corrections linguistically before correcting the underlying interpretation.

If this coach starts speaking unprompted before those failures are fixed, the product gets worse: wrong and intrusive instead of merely wrong on demand.

## Strategic Read

Agentic coaching is the destination, not the fix.

Responsive V2 must first prove that the coach can reason, parse evidence, suppress uncertainty, avoid template dominance, and handle correction/fallback honestly. Once that is reliable, agentic behavior becomes the product shape that makes the N=1 fingerprint thesis valuable.

The Product Strategy already points here: Proactive Coach, Pre-Race Fingerprint, Personal Injury Fingerprint, and Personal Operating Manual only become emotionally powerful when the system can act on learned patterns without requiring the athlete to know what to ask.

## Build Path

1. **Fix responsive V2 first.**
   The coach must reliably handle same-turn evidence, current packet data, corrections, and fallback integrity before it earns more surfaces.

2. **Add silent agentic preparation.**
   No outbound messages yet. The system prepares race dossiers, weekly coach notes, recent-pattern summaries, likely-question prep, and plan-adjustment hypotheses in the background. This improves responsive chat while building toward the final product shape.

3. **Add reviewed proactive surfacing.**
   Generate proposed outreach internally: "Coach would have said this today." Founder/admin approves, rejects, or edits. This tests timing and judgment without risking athlete trust.

4. **Ship opt-in proactive coach.**
   Rare, high-signal, permissioned outreach only. The coach earns the right to interrupt.

5. **Operationalize pencil-plan adaptation.**
   The coach proposes changes to the upcoming week based on what actually happened. The athlete approves, rejects, or edits. The system learns preferences but does not take control.

## Trust Budget

Agentic coaching needs a conservative trust budget:

- Most background observations should produce no athlete-facing action.
- Outbound speech must be rare and earned.
- Injury, recovery, race-week, and plan-change messages need stricter gates than normal chat.
- The athlete owns decisions. The system informs, proposes, and learns.
- Silence remains preferable to low-confidence interruption.

## First Useful Agentic Slice

The first useful slice is **silent upstream preparation**, not notifications.

Examples:

- Build a race-week dossier before the athlete asks about the race.
- Summarize the last week of training into private coach notes.
- Detect likely plan-adjustment questions before the next week starts.
- Prepare "what changed since last conversation" context.
- Record candidate proactive observations but do not send them yet.

This slice directly helps the current responsive coach because it lets the model answer from prepared work instead of trying to reason from a giant packet in one turn.

## Decision

Do not pivot away from responsive coaching. Responsive coaching is still the quality gate.

Do not treat agentic coaching as the current fix. It adds risk before the coach is trustworthy.

Do preserve agentic coaching as the intended product destination. Once responsive V2 is stable, this is the layer that turns StrideIQ from a chat interface into the coach promised by the manifesto.
