# Garmin Connect Developer Program — Compliance Requirements

**Status:** Approved. Agreement accepted February 2026.

**This document extracts the contractual obligations that directly affect
how StrideIQ is built. Every agent working on Garmin integration, data
display, AI features, or privacy must read this before writing code.**

---

## 1. AI Transparency Statement (MANDATORY — Section 15.10)

**This is the highest priority compliance item.** StrideIQ processes Garmin
data through AI systems (LLMs for coach briefing, moment narratives,
morning voice, correlation narration, coach chat with 24 tools). The
agreement REQUIRES:

### What the privacy policy must include:

1. **Clear disclosure** of the nature and purpose of AI processing:
   - What data is processed (activity streams, HR, pace, cadence, sleep,
     HRV, stress scores — whatever Garmin provides)
   - What AI systems process it (coaching intelligence, narrative
     generation, correlation analysis, personalized insights)
   - Why (to provide personalized training intelligence and coaching)

2. **Explicit consent** from each user BEFORE any AI processing begins:
   - Not a buried checkbox. Conspicuous.
   - Must be obtained before the first Garmin data sync triggers any
     LLM call or AI pipeline

3. **Easy withdrawal mechanism:**
   - User must be able to withdraw AI processing consent at any time
   - Must be easy (not buried in settings behind three menus)
   - Withdrawal must actually stop AI processing of their data

4. **Updates:** Privacy policy must be updated when laws or Garmin
   policies change

### Builder action required:

- [ ] Update privacy policy at `strideiq.run/privacy` with AI
      Transparency Statement
- [ ] Add consent flow to onboarding (before first Garmin sync)
- [ ] Add consent withdrawal option to Settings page
- [ ] Ensure AI pipelines check consent status before processing
      Garmin-sourced data

**Do NOT ship Garmin integration until this is in place.** Violating
Section 15.10 triggers automatic termination of the developer program
(Section 9.4).

---

## 2. Attribution Requirements (Section 6.1, 6.2, 6.4)

Any screen that displays Garmin-sourced data must include Garmin
attribution per their brand guidelines.

### Rules:

- Follow brand guidelines at:
  https://developer.garmin.com/brand-guidelines/overview/
- Attribution is required on any content retrieved from Garmin Connect
  and displayed in StrideIQ
- Do NOT modify, stretch, recolor, or distort Garmin logos or marks
- Do NOT use Garmin branding in a way that suggests Garmin endorses
  StrideIQ (Section 5.1(c))

### Builder action required:

- [ ] Review Garmin brand guidelines
- [ ] Add appropriate attribution to any screen displaying Garmin data
      (activity detail, home page hero if data source is Garmin, progress
      metrics derived from Garmin, training load)
- [ ] Store data source per activity so attribution can be conditional
      (Garmin data gets Garmin attribution, Strava data gets Strava
      attribution)

---

## 3. New Display Format Notice (Section 6.6)

**30 days' prior written notice** required before introducing new content
formats, user interfaces, or display mechanisms that incorporate Garmin
Brand Features or display Garmin-sourced data.

### What this means:

Any new way of displaying Garmin data — a new chart type, a new page,
a new visualization — requires emailing `connect-support@developer.garmin.com`
with:
- Representative samples or mockups
- Description of how the proposed use complies with branding and
  attribution requirements

30 calendar days before launch.

### Builder action required:

- [ ] Before shipping any NEW visualization of Garmin data (not
      modifications to existing ones), check whether it requires the
      30-day notice
- [ ] Add this as a step in the deployment checklist for features that
      display Garmin-sourced data

### Currently affected features (may need retroactive notice):

- Run Shape Canvas (stream data visualization)
- MiniPaceChart on home page (effort-colored pace line)
- Training Load PMC chart (if fed by Garmin data)
- Any future Garmin-specific data displays (HRV trends, sleep staging,
  Body Battery)

---

## 4. Data Use Restrictions (Section 4.1, 5.2)

### What you CAN do:

- Display Garmin data in StrideIQ to the athlete who owns it
- Format and transform data for display (e.g., convert velocity to
  pace, compute effort intensity from HR)
- Process data through AI systems (with consent per Section 15.10)
- Charge for StrideIQ's intelligence service (you're selling insights,
  not Garmin data)

### What you CANNOT do:

- Sell, lease, or share raw Garmin data with third parties (Section 5.2(e))
- Build an API that lets other apps access Garmin data through
  StrideIQ (Section 5.2(o))
- Display advertising for products that compete with Garmin on pages
  showing Garmin data (Section 5.2(t))
- Use Garmin data for credit evaluation, insurance, or employment
  purposes (Section 5.4)
- Scrape or spider Garmin services (Section 5.2(j))
- Reverse engineer the API (Section 5.2(i))
- Claim that Garmin endorses StrideIQ (Section 5.1(c))

---

## 5. Data Pushed TO Garmin (Section 4.6)

If StrideIQ ever pushes data to Garmin Connect (e.g., workout plans via
Training API, activity annotations), that data becomes Garmin's property.
They can copy, modify, distribute, sublicense, and use it for any purpose
with no obligation to StrideIQ.

### Builder action required:

- [ ] Before building any write-back to Garmin (Training API workout
      push, etc.), discuss with the founder whether sharing that data
      with Garmin is acceptable
- [ ] Do NOT push proprietary StrideIQ intelligence (coaching insights,
      correlation findings, N=1 analysis) to Garmin without explicit
      founder approval

---

## 6. Information Shared WITH Garmin (Section 8.3)

Anything StrideIQ tells Garmin — in support emails, developer portal
communications, feedback — is explicitly non-confidential. Garmin can
use it freely.

### Rule:

- Do NOT share details about StrideIQ's intelligence architecture,
  N=1 correlation engine, coaching methodology, or competitive
  differentiation in any communication with Garmin
- Keep support requests technical and minimal: "Our API call to
  endpoint X returns error Y" — not "We're building an N=1 intelligence
  platform that does Z"

---

## 7. API Stability (Section 3.2)

Garmin can update or modify the API at any time. StrideIQ must adapt at
its own cost. Continued use after an update constitutes acceptance.

### Builder action required:

- [ ] Build the Garmin integration behind an abstraction layer
      (adapter pattern) so API changes don't require rewriting the
      intelligence pipeline
- [ ] Garmin data models should map to StrideIQ's internal models at
      the ingestion boundary, not throughout the codebase
- [ ] Monitor Garmin developer communications for API change notices

---

## 8. Security Requirements (Section 5.1(f-h))

- Maintain security program no less rigorous than accepted industry
  practices
- Meet or exceed Garmin's Minimum Security Requirements (check their
  docs for specifics)
- Notify Garmin within 24 hours of identifying security weaknesses
  that threaten Garmin systems or data: `security@garmin.com` AND
  call +1 913.440.3500
- Notify Garmin within 24 hours of any confirmed data breach affecting
  systems that interface with Garmin

### Builder action required:

- [ ] Ensure Garmin data is encrypted at rest and in transit
- [ ] Ensure API keys and tokens are stored securely (not in code,
      not in .env files committed to git)
- [ ] Document incident response procedure for breaches involving
      Garmin data

---

## 9. End User Agreement (Section 5.3)

StrideIQ must have a written agreement with each user that contains
protections and limitations of liability for the benefit of Garmin that
are at least as protective as those in the Garmin developer agreement.

### Builder action required:

- [ ] Review StrideIQ Terms of Service to ensure they include
      appropriate liability limitations that protect Garmin
- [ ] Ensure ToS covers user responsibilities for data accuracy,
      prohibited uses, etc.

---

## Compliance Checklist Summary

**Before Garmin integration goes live:**

- [ ] Privacy policy updated with AI Transparency Statement
- [ ] User consent flow for AI processing (onboarding)
- [ ] Consent withdrawal mechanism (Settings)
- [ ] AI pipelines check consent before processing Garmin data
- [ ] Garmin attribution on data display screens
- [ ] Brand guidelines reviewed and followed
- [ ] Garmin data encrypted at rest and in transit
- [ ] API keys/tokens secured
- [ ] Abstraction layer for Garmin API calls
- [ ] Terms of Service reviewed for Garmin-protective clauses
- [ ] 30-day display format notice sent for existing visualizations
      (if using Garmin data)

**Ongoing:**

- [ ] 30-day notice before new Garmin data display formats
- [ ] Keep communications with Garmin minimal and non-proprietary
- [ ] Monitor for API updates
- [ ] Update privacy policy when laws or Garmin policies change
- [ ] 24-hour breach notification procedure documented and tested

---

## Reference

Full agreement text: Garmin Connect Developer Program Agreement v7
Accepted: February 2026
Key contacts:
- General: `connect-support@developer.garmin.com`
- Security incidents: `security@garmin.com` + call +1 913.440.3500
- Brand guidelines: https://developer.garmin.com/brand-guidelines/overview/
