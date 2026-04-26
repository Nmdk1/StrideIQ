# StrideIQ Marketing & PSEO Review — April 16, 2026

This is a review of the public surface of StrideIQ as it exists on the site today: the landing page (`apps/web/app/page.tsx` and its section components), the public calculator pages under `apps/web/app/tools/`, the editorial pages (`/about`, `/mission`), and the SEO plumbing (metadata, structured data, sitemap, robots). Every claim below cites the file it came from. No claim is based on an assumption about what the product "should be" — only what the site says today versus what the internal product documents and code say the product actually is.

One production bug in the PSEO surface is flagged as must-fix in Section 3. Everything else is voice, claim integrity, and positioning.

## Section 1 — The shape of the public surface

The landing page is composed of eight sections rendered in order: Hero, QuickValue, FreeTools, HowItWorks, WhyGuidedCoaching, Pricing, FAQ, Footer (`apps/web/app/page.tsx`). Metadata is set at both the layout root (`apps/web/app/layout.tsx`) and per-page level, with canonical URLs, OpenGraph, Twitter cards, Organization and WebApplication JSON-LD. Structured data is also attached to each calculator page (SoftwareApplication, BreadcrumbList, FAQPage schemas).

The calculator hub (`/tools`) links to five tool families: Training Pace Calculator, Age-Grading Calculator, Heat-Adjusted Pace, Race Equivalency, and Boston Qualifying. Each family has a hub page with tool, answer capsule, how-it-works narrative, FAQ block, and related-tool footer. Three of these families (Training Paces, Age Grading, Race Equivalency, BQ) have dynamic per-slug PSEO pages generated from JSON data files (`data/goal-pace-tables.json`, `data/age-gender-tables.json`, `data/equivalency-tables.json`, `data/bq-tables.json`). The sitemap (`apps/web/app/sitemap.ts`) enumerates all of these programmatically and emits a priority-weighted URL list. Robots (`apps/web/app/robots.ts`) correctly disallows every authenticated surface.

The editorial pages are two: `/about` (first-person founder story with pillars and a personal photo) and `/mission` (third-person manifesto with a "New Masters" taxonomy block). A single story slug (`/stories/father-son-state-age-group-records`) is hardcoded as the entire story surface.

As a PSEO architecture this is competent. The sitemap is data-driven, the structured data is present on every tool page, and the internal linking between calculators, hubs, and goal-specific slug pages is reasonable. What does not hold up is the voice, and two of the claims that show up in this voice actively contradict the product's own internal rules.

## Section 2 — Voice: the landing departs from the manifesto

The single best sentence StrideIQ owns — "Your body has a voice" — appears only in the meta description (`apps/web/app/layout.tsx` line 17 and `app/page.tsx` line 14). It does not appear on the rendered page. The Hero opens with the brand mark, a tagline ("Deep Intelligence. Zero Fluff."), and three stacked phrases: "Evidence-backed running intelligence," "Shows what works, what doesn't, and what to do next," and a supporting line about training paces, trend signals, and coach guidance (`Hero.tsx` lines 52–70). The tagline is fine. The three phrases underneath it could run under any of five AI coaching competitors without editing.

Below the value prop is the subhead "AI Running Coach" in all-caps orange (`Hero.tsx` lines 73–75). This is the weakest positioning available to the product. The `PRODUCT_STRATEGY_2026-03-03.md` document opens with sixteen priority-ranked concepts whose shared thesis is that the moat is the correlation engine producing true, specific, actionable findings about a single human. The Pre-Race Fingerprint, the Personal Operating Manual, the Injury Fingerprint, the Proactive Coach — none of these are ordinary "AI coach" features; they are the product's defensible differentiation. Labeling the hero "AI Running Coach" puts StrideIQ in the same mental bucket as Runna, Humango, Athletica, and TrainingPeaks AI, where it loses on pricing and feature breadth. The hero subhead should do the opposite: name the thing only StrideIQ does.

The `QuickValue` strip under the hero is three numbers: "3 Training Calculators," "360° Complete View," "24/7 Correlation Analysis" (`QuickValue.tsx` lines 9–25). These are three different kinds of claim at three different scales — a utility count, a marketing abstraction, and a product claim — and none of them speak to the product's actual shape. "3" is a weirdly small number for a product that advertises a correlation engine; a prospective customer scanning this strip wonders what the ceiling is. "360° Complete View" is SaaS cliché and not verifiable. "24/7 Correlation Analysis" is closer to truthful but lumps the async briefing pipeline in with a TV infomercial phrase.

The `HowItWorks` component is three steps ("Connect Your Watch," "Complete the interview," "Receive training that evolves") that describe Runna, Humango, Athletica, and StrideIQ equally well (`HowItWorks.tsx` lines 22–55). Step 3 makes one specific claim — "No templates. No scores. Adaptation based on your efficiency trends." — and that claim has a problem, discussed in Section 3.

The `WhyGuidedCoaching` section is the most brand-hostile content on the site. It frames StrideIQ explicitly against human coaches ("AI Running Coach vs Human Running Coach," `WhyGuidedCoaching.tsx` lines 52–91), with a price comparison against human coaches and a bullet list ("Never sleeps, never forgets, never has an off day"). The problem is not that the comparison is wrong — it is that this picks a fight the product does not need to pick, and that the founder's own strategy document lists Concept #15 as a "Personal Coach Tier" product that would put human coaches inside the funnel. The target audience for StrideIQ — competitive amateurs and masters athletes — respects coaches and often works with them. Framing the product as a substitute for human coaching turns off exactly that audience. It also contradicts the `about` page, which is careful and humble.

The `/about` page is the strongest surface on the site (`apps/web/app/about/page.tsx`). It is first-person, specific, grounded, and uses the founder's actual story: the US Medical Scientific history, the self-reported injury from a plan that didn't know him, the pillar architecture (N=1, Evidence Contract, Plans You Can Understand, Beginner-to-Elite). Everything that is wrong with the Hero and the competitive section is right on the About page. The voice that belongs on the Hero is the voice that exists on About.

The `/mission` page (`apps/web/app/mission/page.tsx`) is weaker than About. "Elite-level analysis," "world-class performance at any age," "silent, brilliant assistant," and the eight-tier masters taxonomy ("Centurion Prime 100+") read as branding theater to the competitive runners the product is built for. The "Taxonomy: The New Masters" block is the kind of content that competitive masters athletes see as condescending — calling a 50-year-old a "Grandmaster" is the opposite of what the page intends. There is nothing wrong with the age-grading commitment; there is a lot wrong with the naming. The Mission page also contains the `efficiency` claim problem from the `HowItWorks` section and adds a new one: the use of an external Unsplash image (`https://images.unsplash.com/photo-1545558014-8692077e9b5c`, line 25) that leaks referrer, hurts page speed, and visually mismatches the calm discipline of the About page's actual photo.

## Section 3 — Claim audit: three public claims that contradict the internal contract

This is the most important section. The site makes three specific claims that conflict with the product's own internal rules as stated in `apps/api/services/n1_insight_generator.py` (the OUTPUT_METRIC_REGISTRY / Athlete Trust Safety Contract), `docs/FOUNDER_OPERATING_CONTRACT.md`, and the coach system prompt in `apps/api/services/coaching/core.py`. Any of these is enough to create a trust rupture on the day an athlete asks the coach about what the landing page said.

**Claim 1 — "Adaptation based on your efficiency trends."** This appears twice: in `HowItWorks.tsx` line 14 ("No templates. No scores. Adaptation based on your efficiency trends.") and in the Mission page line 70 ("measurable efficiency"). The Athlete Trust Safety Contract enforced in `services/n1_insight_generator.py` explicitly treats running efficiency (pace-over-heart-rate) as the canonical *ambiguous* metric. The ratio moves in opposite directions for two valid improvement modes (fitness gain vs. fatigue masking), and the OUTPUT_METRIC_REGISTRY suppresses directional claims about efficiency in athlete-facing text for that reason. The public landing page promises adaptation based on the exact metric the internal contract says should not be interpreted directionally without care. Either the contract's polarity work has matured beyond the current code (it has not — see the 8-service legacy debt tracked in `docs/TRAINING_PLAN_REBUILD_PLAN.md`), or the landing page is selling a claim the backend will, correctly, refuse to make on any given athlete's data. Change the public phrasing. "Adaptation based on your actual response patterns," "based on how your body actually responds to each training stimulus," or "based on the correlations your data reveals" are all closer to the product's real capability and do not bind the coach to a claim it cannot ground.

**Claim 2 — "Based on Daniels/Gilbert VDOT system."** The Training Pace Calculator page uses "VDOT" four times, including in the page's structured explanation (`apps/web/app/tools/training-pace-calculator/page.tsx` lines 114, 117). The coach's system prompt in `services/coaching/core.py` explicitly prohibits saying "VDOT" on grounds of trademark and directs the coach to use "RPI" (Running Performance Index) instead. The Pricing component (`Pricing.tsx` line 10) already does the right thing: "Training Pace Calculator (RPI)". The Race Equivalency hub (`apps/web/app/tools/race-equivalency/page.tsx`) and the Boston Qualifying dynamic slug pages (`apps/web/app/tools/boston-qualifying/[slug]/page.tsx`) also use "RPI" consistently. Only the Training Pace Calculator hub is out of step. This is either a deliberate SEO play — "VDOT training paces" has real search volume and the Training Pace page is the calculator hub — in which case it should be documented as such, or an oversight where the other tool pages caught up to the RPI migration and this one did not. If it is deliberate, the page should still introduce RPI once: "Daniels/Gilbert's oxygen cost equations produce a number known publicly as VDOT. StrideIQ surfaces this as RPI (Running Performance Index) — the same math, the same zones, owned nomenclature." That paragraph keeps the keyword play and ends the internal inconsistency.

Side note, not a public claim but a related bug: the coach system prompt text in `services/coaching/core.py` contains a self-contradicting instruction about terminology that reads "NEVER say RPI — this is a trademarked term. ALWAYS say RPI (Running Performance Index) instead." Both halves of that sentence say RPI. This looks like a find-and-replace accident where "VDOT" was replaced with "RPI" across the file including the text that was telling the coach to avoid VDOT. The coach prompt is currently telling the coach to never-and-always-say the same word. This should be fixed as part of the same cleanup.

**Claim 3 — "Research-backed formulas (not lookup tables)."** The `FreeTools` component says this (`FreeTools.tsx` line 22, and repeats in the trust-indicator row on line 58). The training pace computation in fact uses `_RPI_PACE_TABLE`, a hardcoded lookup table derived from first principles and declared unmodifiable in the wiki's `plan-engine.md`. Lookup tables are not dishonorable — they're a deterministic representation of the equations — but claiming "not lookup tables" on a surface that is implemented as a lookup table is the kind of small claim that a careful reader (and the founder's own stated quality bar) will eventually notice. Drop the parenthetical and let the claim stand: "Research-backed formulas. Instant results. Mobile-friendly."

## Section 4 — The production bug on the PSEO surface

The dynamic Boston Qualifying slug page (`apps/web/app/tools/boston-qualifying/[slug]/page.tsx`) has four entries where the `trainingContext` field is written with template-literal interpolation syntax inside a single-quoted JavaScript string. Single-quoted strings do not interpolate. The template syntax renders as literal text on the live page.

Affected entries:

- Line 85: `boston-qualifying-time-men-40-44` — "Easy days should genuinely feel easy — at ${d.paces?.easy?.mi || 'this pace'} or slower — to allow full recovery..."
- Line 163: `boston-qualifying-time-men-70-74` — "Threshold work once every 10–14 days at ${d.paces?.threshold?.mi || 'threshold'} pace maintains..."
- Line 230: `boston-qualifying-time-women-40-44` — "Running easy days genuinely easy — at ${d.paces?.easy?.mi || 'this pace'} or slower — is the most impactful discipline change..."
- Line 282: `boston-qualifying-time-women-60-64` — "Easy pace at ${d.paces?.easy?.mi || 'this pace'}/mi or slower must be the norm..."

The render path is line 522: `<p>{config.trainingContext}</p>`, which dumps the string verbatim. Four live SEO pages — each targeting a high-intent query like "Boston qualifying time men 40-44" — are currently showing the literal text `${d.paces?.easy?.mi || 'this pace'}` to readers and to Google's crawler. This is a real trust rupture the moment a visitor sees it. It is also the kind of thing that reads as "this team does not check its own work" to competitive runners, which is the opposite of the site's stated evidence-contract stance.

The fix is small: convert each affected entry from a static string to a function `(d: BQEntry) => string` that returns an interpolated template string, parallel to how `buildFaq` is already typed on line 52. The type on line 51 should change from `trainingContext: string` to `trainingContext: string | ((d: BQEntry) => string)`, and the render site on line 522 should call the function form when it is a function. Alternately, fix the four affected entries to not interpolate and rewrite the text to be self-contained (e.g., drop the `${d.paces.easy.mi}` reference, since the page already displays the pace table directly above the prose block). The second approach is lower-risk and ships in five minutes.

This is the only must-fix in this review.

## Section 5 — What's solid in the calculator pages and PSEO

The calculator page template is well-executed. Using the Training Pace page as the reference:

- Metadata is complete (title, description, canonical, OpenGraph, Twitter) and brand-consistent.
- Three JSON-LD blocks (SoftwareApplication, BreadcrumbList, FAQPage) provide proper structured data.
- The answer capsule ("Quick answer: Enter a recent race time and distance...") targets featured snippet retrieval.
- The how-it-works narrative is substantive (four paragraphs of keyword-relevant prose).
- The internal linking is dense and deliberate: goal-time-specific pages, distance-specific pages, related calculators.
- The FAQ items are phrased as genuine questions, not keyword-stuffed.

The sitemap (`apps/web/app/sitemap.ts`) is data-driven, pulling goal slugs, demographic slugs, equivalency slugs, and BQ slugs from JSON data files rather than maintaining a static list. That is the right architecture for PSEO scale.

Robots (`apps/web/app/robots.ts`) correctly disallows every authenticated surface. This is often wrong on consumer products; it is right here.

The BQ `[slug]` template (when its interpolation bug is fixed) is actually the most sophisticated per-page PSEO work on the site. It combines authoritative data (BAA standards), computed training paces, WMA age-grades, and distance equivalents, and wraps all of it in voice-consistent prose ("Masters marathon training for men 40–44 differs from the 30s primarily in recovery management"). The prose is detailed enough to register as genuine content, not thin affiliate material. Google rewards this.

The Race Equivalency hub (`apps/web/app/tools/race-equivalency/page.tsx`) deserves specific mention. Its FAQ answer on "When should I trust race equivalency — and when should I not?" is the best piece of content on the public site. It names a limitation ("5K → marathon predictions are less reliable") rather than hiding it, gives the reader the physiology ("the marathon requires specific training adaptations — long runs, glycogen management, pacing experience"), and resolves with a useful guideline ("Trust equivalency as a potential ceiling, not a race-day prediction"). This is the voice the Hero should be using. It is the manifesto's "suppression over hallucination" principle rendered as marketing copy, and it works.

## Section 6 — What's missing or thin

**OG images are one file for the whole site.** Every page references `/og-image.png?v=6`. A single static OG image is fine for a basic product; it is a missed SEO opportunity for a product whose pages are highly differentiated (a training pace calculator share link should visually differ from a Boston qualifying share link). Per-page OG images, generated dynamically with the Next.js OG image route or baked in per-tool, would lift link-preview CTR on social and in messaging apps.

**The `WebApplication` JSON-LD on the landing page is misleading.** `apps/web/app/page.tsx` lines 35–42 declares `offers: [{ price: '0', priceCurrency: 'USD' }]`. The product is $24.99/mo or $199/yr after 30-day trial. Declaring the entire WebApplication as a free offer is technically untrue. Google may ignore this, or may penalize it under misleading-content signals. Either remove the `offers` block, or declare both the trial tier ($0, 30 days) and the paid tier ($24.99/mo) under an `offers` array of `AggregateOffer`.

**No Person or Author schema for Michael Shaffer.** The About page has the kind of authority content (founder background, specific credentials, specific running history) that benefits from E-E-A-T structured data. Adding a `Person` JSON-LD on the About page, with `worksFor: {Organization: StrideIQ}`, `knowsAbout: ['running', 'exercise physiology', 'age-graded performance']`, and a `sameAs` pointing at a LinkedIn or Strava profile, reinforces the evidence-contract positioning in a way search engines can consume.

**Single story.** The sitemap's `STORY_SLUGS` array contains one slug: `father-son-state-age-group-records`. Stories are the highest-leverage editorial PSEO lever the site has — competitive runners read race reports, age-group records, comeback stories, training deep-dives — and StrideIQ has exactly one. The story surface is also the one place where the voice StrideIQ is trying to establish (specific, grounded, evidence-backed) naturally becomes marketing content without needing to be performatively so. If editorial content is not the founder's bandwidth, it is nonetheless the single highest-leverage content expansion available.

**No obvious brand-to-product bridge on calculator pages.** The calculator pages get the traffic ("training pace calculator" is a high-volume term). The bridge from calculator to product is, in most cases, a related-tools row at the bottom plus a generic "Start free trial" button. The opportunity being missed: a single specific sentence on each tool page that distinguishes the calculator (a one-shot computation) from the product (the longitudinal correlation engine). On the Training Pace page, for example: *"These paces are a starting point. Your actual response — what heart rate you can sustain at Threshold, how long your body takes to absorb Interval work, whether Easy for you is 7:45 or 8:30 — is discoverable only from your own data over time. StrideIQ learns that."* One sentence. One link. No up-sell tone. The founder's voice on the About page is the template.

**FAQ question #7 on the landing page is category-generic.** "What is the best AI running coach for marathon training?" (`FAQ.tsx` lines 35–38). This is a search-keyword bend rather than a real runner question, and the answer ("The best AI running coach generates training paces from your actual race data...") is self-referential and vague. Either drop this question or rewrite its answer to lead with exactly one thing only StrideIQ does that other AI coaches do not — the correlation engine, the Pre-Race Fingerprint concept, evidence citation. The other seven FAQ items are sound.

**The Pricing tier names are muted.** Free tier is called "Free"; paid tier is called "StrideIQ." The second name is the company name, which is technically right but reads as lazy — especially paired with a "Full Access" badge. The feature list is crisp, the toggle and price display work, but the tier names could do more work. "Calculators" vs "Personal Coach" or "Tools" vs "Your Coach" both name the actual jobs-to-be-done rather than leaving the decision as "Free vs brand-name."

**Footer brand copy is weaker than the Hero meta description.** `Footer.tsx` line 27: "AI-powered running intelligence. Discover what actually improves your running through data-driven insights." The meta description ("Your body has a voice. StrideIQ is AI running intelligence that turns your data into decisions...") is better and should be reused here.

## Section 7 — The three highest-leverage changes, in priority order

**One: Fix the four `trainingContext` interpolation bugs on the BQ slug pages.** This is 30 minutes of work and removes a live trust rupture on four high-intent SEO pages. It is the only change in this review that cannot wait for a discussion.

**Two: Rewrite the Hero and the WhyGuidedCoaching section in the voice of the About page.** The Hero should lead with something closer to "Your body has a voice. StrideIQ gives it one" (or the founder's preferred expression of the manifesto thesis), the value-prop stack should mention the correlation engine or Personal Operating Manual or Pre-Race Fingerprint by name, and the "AI Running Coach vs Human Running Coach" comparison block should be replaced — either with a more generous framing (what StrideIQ does that calculators and plans-in-a-box do not) or removed entirely. The About page already demonstrates that StrideIQ's voice, applied honestly, is marketing copy that works. This is a single focused pass on five files (`Hero.tsx`, `QuickValue.tsx`, `HowItWorks.tsx`, `WhyGuidedCoaching.tsx`, `FAQ.tsx`) and probably an afternoon with the founder to confirm lines. It is the highest-leverage change because it is the one a real customer will read.

**Three: Fix the three claim-contract conflicts flagged in Section 3.** The efficiency claim, the VDOT/RPI split, and the "not lookup tables" claim are small lines each, but each one binds the product to a promise the backend is designed not to make. Each is a surgical edit (one sentence or one parenthetical). Doing these at the same time as the voice pass is natural; separating them risks the voice pass shipping with the conflicts intact.

## Section 8 — Suggested concrete rewrites

These are candidates for discussion, not edits. Each is one option. The founder's voice should win; these are starting points that resolve the specific issues above.

**Hero tagline candidates (replacing "Deep Intelligence. Zero Fluff." subhead pair):**

- *Your body has a voice. StrideIQ gives it one.* (Manifesto-direct. Strongest.)
- *The intelligence your data was hiding.* (Curiosity hook.)
- *Training that learns you, not the other way around.* (Contrast against templates.)

**Hero subhead replacing "AI Running Coach" orange caps line:** the product is a longitudinal correlation engine with a coach on top. Candidate: *"Correlation engine. Evidence contract. A coach that remembers."*

**QuickValue stat replacements (currently "3 / 360° / 24/7"):** three numbers that actually mean something in the product. Candidates from internal data:
- number of signals the correlation engine ingests per athlete (runs, sleep, nutrition, training load, stride, cadence, heart rate zones — 20+ data streams)
- days of history needed before the engine produces findings (threshold by layer, but the answer is "~30 runs")
- lines of evidence cited per finding (the evidence-contract commitment). Concrete numbers replace marketing abstractions.

**HowItWorks step 3 replacement for "Adaptation based on your efficiency trends":** *Your plan adapts as your data reveals what actually works for you — not averages, not scores, and not claims we can't back with evidence.*

**Training Pace page RPI/VDOT reconciliation paragraph (to insert after current "How the training pace calculator works" opening):** *Daniels and Gilbert's published equations produce a number known publicly as VDOT. StrideIQ surfaces this as RPI (Running Performance Index) — the same math, the same zones, a name StrideIQ can stand behind. The calculator above uses these equations directly.*

**FAQ question #7 replacement:** drop the "best AI running coach for marathon training" question; replace with: *"Does StrideIQ tell me what my sleep or nutrition did to my training?"* Answer: *"Yes — when the data supports it. StrideIQ runs a correlation engine against your own history: sleep, nutrition check-ins, training load, and run outcomes. When a pattern is real in your data, it is surfaced with the specific evidence. When a pattern is not clear, StrideIQ stays quiet. The commitment is accuracy, not volume."*

## Section 9 — Out of scope

This review did not examine: the signup/onboarding flow (`/register`), the interior dashboard, the Stripe pricing configuration, the Google Analytics/plausible setup, the performance metrics (Core Web Vitals, Lighthouse), the accessibility audit, or the marketing email / outbound funnel. Each of these is a separate review. The scope here was the public pre-signup surface: landing, tools, editorial, SEO plumbing.

Two items that were examined but held at arm's length: the support page, the terms and privacy pages. These are referenced in the footer but were not opened. They are unlikely to affect acquisition and were deprioritized.

The sitemap's single story slug and the broader question of editorial / content marketing strategy (who writes stories, how often, what about) is flagged as a gap in Section 6 but is not sized here because it is a resource question more than a technical one.

---

Total: two reports (structural review filed April 16, 2026; this marketing review, same day), seven claims flagged, one production bug, three priority actions. The structural review's recommendations and this review's recommendations are independent and can proceed in parallel.
