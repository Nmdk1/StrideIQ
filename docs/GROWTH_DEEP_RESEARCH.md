# StrideIQ — Deep Research Memo (Growth)

**Date:** April 12, 2026 (second pass: Intervals, Elevate, Strava–Runna, SEO depth, Reddit, measurement; **third pass:** advisor assessment — copy mandate, 10→100 gap, father–son post-mortem, Show HN as “moment”, founder Reddit constraint)  
**Purpose:** Independent desk research to ground [`docs/GROWTH_PHASED_PLAN.md`](GROWTH_PHASED_PLAN.md) in evidence, analogs, and channel mechanics—not to replace founder judgment or primary research with users.

**Methodology**

- **Primary sources** where available: founder blogs, company “about” pages, official product blogs (quoted or closely paraphrased with URLs).
- **Secondary sources:** industry profiles (Tracxn, CB Insights), SEO/indie practice articles, forum governance pages, Hacker News thread metadata (points/comments as rough engagement proxies).
- **What this is not:** Scraped Reddit/LetsRun thread corpora, Search Console exports for StrideIQ, paid survey, or live competitor product teardowns behind login. Those are **recommended follow-ups** and should supersede desk conclusions when available.

**Honest limitation:** Web search is a blunt instrument. Findings are **directional** and **hypothesis-generating**. The bar you set—“deeper than a one-line Google”—is addressed by **multi-source synthesis, named analogs, and explicit gaps**, not by pretending this is McKinsey-grade primary research.

---

## Strategic copy principle (non-negotiable for public-facing growth)

**Advisor + product-strategy alignment:** Do **not** lead the homepage, ads, or tool landing **hero** with **“AI coach”** or **“training plans”** as the **primary** headline. The **plan** lane is **commodity + consolidating** (see Strava × Runna). StrideIQ’s differentiated promise is **retrospective truth**: **connect Garmin/Strava → something true about *your* body in the first session** (see [`PRODUCT_STRATEGY_2026-03-03.md`](PRODUCT_STRATEGY_2026-03-03.md) first-session hook). Plans and coach are **supporting** proof, not the lead.

---

## 1. Why analogs matter for StrideIQ

StrideIQ sits in a **sparse** category: **Garmin + Strava ingestion**, **multi-year history**, **N=1 correlation intelligence**, **coach narrative**, **subscription**. Few products match the full stack. Research therefore combines:

1. **Analyst-first endurance tools** (depth, metrics, serious amateurs)—Runalyze, Smashrun, TrainingPeaks’ athlete side, Runlab-style overlays.
2. **Planner-first AI** (Athletica, Runna-class)—for contrast; they optimize different buying triggers.
3. **Distribution layers** runners already use (Strava social graph, SEO for calculators, communities with strict promo rules).

---

## 2. Analog products: how they grew (and what to infer)

### 2.1 TrainingPeaks — coach wedge → platform B2B2C

**Primary source:** Joe Friel’s blog post *How TrainingPeaks Came to Be* (Oct 2, 2009), [trainingbible.com](https://trainingbible.com/joesblog/2009/10/how-trainingpeaks-came-to-be.html).

**Facts from the source**

- **1994:** Friel built a **FileMaker Pro** system on vacation to replace faxing/mailing training schedules to coached athletes.
- **1999:** Son Dirk Friel + **Gear Fisher** shipped a **web version** mirroring the FileMaker layout—“Classic View.”
- **2000:** Took it **public with subscriptions**. Gear worked nights from his bedroom until **spring 2001** (first payroll check).

**Secondary source:** TrainingPeaks materials describe evolution into a **neutral platform for any coach** (not only Friel’s practice)—B2B2C via coaches as distribution.

**Inference for StrideIQ**

- The **first revenue** came from solving a **high-friction coaching workflow** (schedule delivery), not from “growth hacks.”
- **Institutional trust** (named coach, decade of methodology books) lowered adoption friction for early users.
- **Platform neutrality** scaled distribution beyond one practice—relevant if StrideIQ ever revisits **coach tier** or B2B2C; not required for D2C-first.

StrideIQ is **not** starting from a fax problem in 1994; the parallel is: **wedge = painkiller workflow for a defined ICP** (serious athlete with history), not generic consumer fitness.

---

### 2.2 Runalyze — bootstrapped analyst product, scale through sync and sharing

**Sources:** Runalyze blog *Year in review 2018* [blog.runalyze.com](https://blog.runalyze.com/allgemein-en/year-in-review-2018/); company profiles (Tracxn/Startbase cite bootstrapped, small team).

**Quantitative signals (2018 blog, Runalyze self-reported)**

- Documented kilometres in system grew from **~25M to 50M+** in one year (driven by sync + full imports).
- **~+7,500 users** in the year; **active users doubled**.
- **Garmin sync** ~**5,800** connected users; Polar ~**1,160** (ordering by adoption).
- **October 2018:** Launched **download and share graphics** for individual activities for Facebook/Twitter/Instagram/blogs—“social sharing options.”

**Inference**

- **Device sync** (especially Garmin) was a **step-change** in uploads and retention—not just “better charts.”
- They explicitly invested in **shareable graphics** as a **social loop**—direct precedent for StrideIQ **Phase 2** (finding cards differ in content but same **shareable proof** class).
- Growth was **organic** and **feature-led** over years, consistent with **no paid blitz** narrative.

**Positioning:** Runalyze emphasizes **device-independent analysis**, sports science, **Effective VO2max**, age grading—**analyst** lane, not “get couch to 5K.” StrideIQ’s **N=1 correlations + Manual** are a **superset narrative** (relationships in data), not the same feature set.

**Infrastructure as proof of scale (primary source):** Runalyze’s *Our major background migration* [blog.runalyze.com](https://blog.runalyze.com/allgemein-en/our-major-background-migration/) states the stack originally assumed **single-user** origins; by migration they must handle **“over 30,000 users”** and **~seven million activities** with GPS and sensor data—driving a **file-based** cold-store architecture because **~80%** of activities are “uploaded once” then rarely read (but must remain available for recalculation, posters, backup). **Inference:** sustained **organic load** forced **real engineering investment**—analogous to StrideIQ’s Timescale/correlation depth: **serious analyst products create serious data gravity.**

---

### 2.3 Smashrun — motivation through context; long build before scale

**Primary source:** Smashrun *The story so far* [smashrun.com/about/story](https://smashrun.com/about/story).

**Core thesis (their words, condensed)**

- **Motivation and context are linked:** understanding how a run fits **history and goals** creates **purpose**—“doing anything with purpose is easier.”
- **Gamification:** explicit comparison to **video game reward loops** applied to beneficial behavior.
- **Origin:** Brooklyn; **“long winter of coding”** before launch.

**Inference**

- **Emotional job-to-be-done** for analytics products is not “more numbers”—it’s **meaning** after the run. StrideIQ’s **coachable moments** and **Manual** align with that psychology; **shareable cards** should answer “why should anyone care?” in one glance.
- Smashrun’s path implies **years** of iteration—sets expectations on **timeline** vs overnight SEO.

**Note:** Third-party articles (e.g. AndesBeat 2012) mention early **Nike+** integration and press (e.g. Mashable). StrideIQ is **Garmin/Strava-first**—different platform politics; the lesson is **integrate where athletes already live**, not the specific brand.

---

### 2.4 Athletica.ai — contemporary AI planner (contrast case)

**Sources:** Tracxn profile (unfunded, founded ~2020, Revelstoke); company site emphasizes **Garmin, Strava, COROS, Wahoo**, adaptive plans, **free trial**.

**Inference**

- **Multi-device** positioning is **table stakes** for new endurance AI products; **Garmin-only** would be a positioning liability for StrideIQ if messaged narrowly—your product already supports Strava + Garmin; messaging should reflect **breadth** where true.
- **Athletica** optimizes **plan adaptation**; StrideIQ’s differentiated story is **retrospective intelligence + compounding model**—competitive framing should **not** chase “another adaptive plan” copy.

---

### 2.5 Intervals.icu — Strava-adjacent analysis → standalone; organic scale without venture story

**Primary source:** [Intervals.icu — About](https://www.intervals.icu/about/) (accessed 2026).

**Facts from the source (quoted narrative)**

- Started **mid-2018** as a **side project** (David Tinker, Cape Town) to learn a new framework while exploring road-bike training.
- **“Originally built as an analysis extension for Strava”** — then “took on a life of its own” as athletes found analytics that **“rivalled expensive paid platforms.”**
- **“Word spread through cycling and triathlon communities, and the user base grew organically.”**
- By **2024**: **“over 100,000 athletes”** who had collectively analyzed **“over 111 million activities.”** David went **full-time in September 2024**.
- **Community:** Volunteer moderators, active **forum**, translations into **20+ languages** via GitHub.

**Inference for StrideIQ**

- **Organic word-of-mouth** at **six-figure athlete** scale is **documented** for an **analyst-first** product that **started** as **Strava-layer** software—closest public analog to “serious people tell serious people” without a celebrity budget.
- **Overlap:** multisport **calendar + workout tooling** is Intervals’ center of gravity; StrideIQ’s center is **retrospective N=1 intelligence + Manual + coach**. Same **ICP overlap** (data-heavy endurance), **different wedge**—StrideIQ should **not** try to out-**calendar** Intervals; it should win on **“it found something true in my history.”**
- **Hiring moment (full-time 2024)** suggests **revenue or runway** crossed a threshold after **years** of side-project growth—sets **expectations** for **timeline** vs overnight SEO.

---

### 2.6 Elevate for Strava — Chrome extension as acquisition channel (parallel mechanic)

**Sources:** Open repository [`thomaschampagne/elevate`](https://github.com/thomaschampagne/elevate) (Elevate for Strava); Chrome Web Store listing **Elevate for Strava** ([Chrome Web Store](https://chromewebstore.google.com/detail/elevate-for-strava/dhiaggccakkgdfcadnklkbljcgicpckn)).

**Observed pattern (desk research, verify before marketing use)**

- Third-party aggregators and store listings cite **large install bases** (order **10⁵** users) and **strong star ratings** for this **free** extension that **adds analytics** on top of Strava’s web experience.
- **Acquisition mechanics** historically used by extension authors: **answer power-user questions** in forums/Reddit/Strava communities where people complain about missing metrics, link **only when helpful**; **Chrome Web Store** keyword + description hygiene.

**Inference for StrideIQ**

- Demonstrates **demand for deeper metrics** than Strava’s default surface—consistent with StrideIQ’s **analyst** positioning.
- **Not** a recommendation to build an extension now: it is a **parallel funnel** that trades **engineering surface area** (browser + Strava DOM) for **distribution**. File under **optional future** if web SEO + cards plateau—**Phase 1–4** in [`GROWTH_PHASED_PLAN.md`](GROWTH_PHASED_PLAN.md) remain the scoped path.

---

### 2.7 Market structure — Strava × Runna (2025) and the “training app” lane

**Primary source:** Strava press release [Strava to Acquire Runna, A Leading Running Training App](https://press.strava.com/articles/strava-to-acquire-runna-a-leading-running-training-app), **April 17, 2025**.

**Facts stated for the market (use as category context, not StrideIQ forecasting)**

- Strava cites **150+ million** registered users; **“nearly 1 billion runs”** on Strava in **2024**.
- **Year In Sport** narrative: running as **fastest-growing sport** globally; **43%** of Strava users wanting to **“conquer a big race or event in 2025”** (Strava survey framing).
- Strategic: **“Over 100 training apps”** connect to Strava’s API; Strava emphasizes **continuing** as an **open platform** for developers while investing in Runna.
- Product: **“Keep the apps separate for the foreseeable future”** — Runna remains its own subscription surface.

**Inference for StrideIQ**

- **M&A validates** the **personalized training plan** category as **strategically valuable** to the **dominant social graph**. StrideIQ is **not** primarily a **plan library** company—**consolidation** strengthens the case for **differentiation on intelligence + compounding athlete model**, not on **another static plan**.
- **Demand for races** (Strava’s 43% stat) supports **SEO** around **pace, BQ, equivalency**—your **tool stack** maps to **documented mass intent**.
- **Developer ecosystem** rhetoric from Strava is **aligned** with building **API-backed** value—but **Phase 3** still requires **legal/product** review of **API Terms** + **brand guidelines** (not fetched in full here; review before shipping).

---

### 2.8 Indie / fitness acquisition patterns (non-running-specific but behavioral)

**Indie Hackers (summaries from interview index):**

- **Martial Arts on Rails / gym software:** Weekly meetings with **gym managers** during development; validation via **Reddit BJJ** community; organic/social due to **budget constraints**.
- **Jumpy Cat:** **1,000 installs / 30 paying** via communities and “things that don’t scale”; unexpected **visually impaired** segment found product-market fit—lesson: **early segments can be surprising**; instrumentation matters.

**Inference:** **Community seeding** works when **authentic** and **problem-specific**; **spammy drive-by posts fail** (see LetsRun below). StrideIQ’s founder constraints push toward **product-mediated** discovery over forum hustle.

---

### 2.9 The 10 → 100 user gap (distinct from 30k–100k compounding)

**What the public record shows:** Intervals.icu’s [About](https://www.intervals.icu/about/) page documents **origin → organic word of mouth → 100k+ athletes by 2024** and **full-time September 2024**, but **does not** publish **how the first 50 users** arrived. Desk research **does not** surface a Tinker blog post titled “our first customers.”

**Plausible mechanisms (hypotheses, not verified)**

- **Cycling/triathlon** forum culture (English-language **Slowtwitch**, club WhatsApp, Strava club chatter) as **pre-Reddit** discovery paths—comparison threads (e.g. Intervals vs TrainingPeaks) appear in **tri** forums by **2024**; very early diffusion may be **invisible** in SEO-indexed pages.
- **Strava-adjacent** power users recommending tools in **comments** and **HN**—e.g. an HN discussion ([item 42915986](https://news.ycombinator.com/item?id=42915986)) where a user praises Intervals.icu unprompted (“**totally worth paying to support**”)—**organic advocacy**, not a **Show HN** launch thread from the founder.
- **Multi-year side project** (2018→2024) means “first 100” may be **stretched over years**, not a single **viral week**—timeline honesty remains important.

**What would actually crack the 10→100 black box**

- **Primary:** Interview or written Q&A with **David Tinker** (or dig **forum.intervals.icu** / project Discord archives for **2018–2020** posts by the founder—labor-intensive).
- **Secondary:** **Podcast** episodes mentioning Intervals’ origin ([example index: Spotify “Stroke FM” interview listing](https://podcasters.spotify.com/pod/show/khosravanih/episodes/Mastering-your-Fitness-Metrics-Interview-with-intervals-icu-David-Tinker-e3c1e29))—transcribe for **first-user** anecdotes.

**StrideIQ implication:** The **10→100** problem may require **one concentrated “moment”** (see §3.4 Show HN) **plus** SEO/tool **baseline**—not **only** long SEO lag.

---

### 2.10 Father–son state records — influencer post-mortem (hypotheses, not a write-off)

**Facts from founder context (as stated in product handoffs):** A **Brady Holmer**–adjacent promotion highlighted the **human story** (father–son state age-group records); **StrideIQ was not named** in a way that drove product trials; founder saw **~30–50 new X followers**, not a measurable **signup wave**.

**Hypotheses for why attention did not convert** (testable; not accusations toward any third party)

| Hypothesis | Implication |
|------------|-------------|
| **No product in the hero** | If the clip/post centers **human drama** without **named product + URL + single CTA**, viewers **follow** the people, not the **software**. |
| **Followers ≠ buyers** | X engagement rewards **story**; **SaaS** conversion requires **intent** (problem-aware, desktop/mobile signup friction). |
| **Audience mismatch** | Holmer’s audience may skew **general science/fitness** vs **Garmin-paywall serious** runners who would **connect a device** same day. |
| **Messenger–ecosystem friction** | If the messenger is **strongly associated with another device ecosystem** (e.g. COROS), **Garmin-primary** positioning of StrideIQ may feel **orthogonal** to viewers’ next step—**messaging** should still lead **data truth**, not hardware tribalism. |
| **Single moment vs funnel** | One **broadcast** without **retargeting**, **landing A/B**, or **tool** follow-up leaves **no** compounding—vs Intervals’ **years** of drip advocacy. |
| **Proof type** | **Records** prove **athletic outcome**; StrideIQ must prove **product mechanism** (“here is the **finding** the engine produced”)—different **evidence** for different **claim**. |

**Strategic use of the story (advisor direction):** Reframe for **technical audiences** (HN, serious runners) as **evidence of physiological modeling**, not **celebrity**—paired with **reproducible demo**: connect → **first finding** in minutes.

---

## 3. Channels — mechanics, evidence, and constraints

### 3.1 SEO and programmatic intent (calculator / tool pages)

**Established practice (industry):** Long-tail **intent pages** (calculators, converters, “what is X for marathon”) compound when each URL has **unique utility**—thin duplicate pages are penalized; **unique inputs/outputs** per page (your distance-specific tool routes) are the right shape.

**Patrick McKenzie (“patio11”) lineage:** Kalzumeus writing since **2006** emphasizes **SEO, landing experiments, and marketing for builders who dislike marketing**—[Kalzumeus](https://www.kalzumeus.com) (e.g. *Marketing For People Who Would Rather Be Building Stuff*, 2013). StrideIQ’s Phase 1 (metadata, internal links, sitemap discipline, measurement) matches this **craft** tradition: **measurable pages**, not hope.

**Timeline:** Organic search commonly shows **multi-month** lag before meaningful impressions move—Phase 1 **must** pair **Search Console + telemetry** so “failure” is diagnosed as **query mismatch vs technical vs CTA**, not vibes.

**Technical depth (what “SEO” means in Phase 1 beyond a title tag)**

| Layer | Why it matters | StrideIQ application |
|-------|----------------|----------------------|
| **Indexation** | Pages not in sitemap or blocked by `robots`/noindex never compete | Audit `app/robots.ts` or static robots, route-level `metadata.robots`, ensure `/tools/**` discoverable |
| **Canonical & dupes** | Calculator **slug** variants (distance, goal, conversion) can **cannibalize** or dilute | One **primary** URL per intent; `rel=canonical` where params/slugs overlap; internal links point to **preferred** URL |
| **Title/H1/query alignment** | Google matches **query language** to visible H1 + title | Map **target queries** per cluster (e.g. “Boston qualifying calculator” vs “BQ pace”)—one **dominant** phrase per page, not keyword stuffing |
| **Structured data** | Rich results for **FAQ**, **HowTo**, **SoftwareApplication** (where honest) can lift CTR | Add only **truthful** schema; no fake reviews |
| **Core Web Vitals / INP** | Ranking tie-breaker; tools often client-heavy | Next.js: watch **bundle** on tool pages; defer non-critical chart code |
| **Internal PageRank** | Orphan tool pages **don’t rank** | Hub from `/tools`, home **Free tools**, cross-links between related calculators (already in phased plan) |
| **E-E-A-T signals** | YMYL less strict for pace calcs than medical; still **trust** helps | About/support/privacy visible; authoritativeness via **correct formulas** (you already care about correctness in product) |

**Diagnosis workflow (90-day loop):** Weekly: **Search Console** impressions/clicks/queries per **landing URL**; **telemetry** sessions tool_view → cta_click → signup_start. If impressions ↑ but clicks flat → **SERP snippet / title**; if clicks ↑ but signup flat → **landing CTA / value prop**; if neither ↑ → **query mismatch** or **technical indexation**.

---

### 3.2 Strava ecosystem and “stats as content”

**Strava API:** Public materials describe **OAuth 2.0**, rate limits (e.g. **200 requests / 15 minutes**, **2,000/day** defaults—[developers.strava.com](https://developers.strava.com/docs/authentication/)), and a large developer ecosystem (third-party directories cite **100k+** developer scale; treat order-of-magnitude as **ecosystem depth**, not a prospect list).

**Share behavior:** The category shows **persistent innovation on sharing**: StatShot, Run Photo, Relive-class video, Strava’s own **Sticker Stats** / Instagram-oriented sharing (2025–2026 coverage). Runners **already** treat **performance artifacts as social content**.

**Inference for Phase 2–3**

- **Finding cards** compete for attention with **polished stat graphics**—StrideIQ’s edge must be **truth density** (“confirmed N times,” suppression-safe wording), not generic pretty charts.
- **Strava description line (Phase 3)** competes with **noise** in followers’ feeds; **opt-in + preview + frequency cap** are not optional—they’re **trust** requirements.

---

### 3.3 Forums: LetsRun and the anti-spam boundary

**Primary source:** [LetsRun.com Message Board Community Guidelines](https://www.letsrun.com/forum/moderation-information-and-community-guidelines) (accessed 2026).

**Rule relevant to commercial posts**

> “The message board forum(s) are not designed to serve as a place where one makes posts that are nothing more than glorified advertisements (i.e. anything promoting another website, product, etc.). If you would like to advertise contact us at advertise@letsrun.com.”

**Inference**

- **Unsolicited product drops** in LetsRun are **structurally hostile** to the venue. Growth via “post in forums” **without** buying ads or earning **organic recommendation** (someone else mentions you) is **high risk** to reputation.
- **Earned** presence—e.g. a genuine training question answered with **data**, or a **recognized user** vouching—fits the culture better than **founder spam**.

This **supports** the phased plan’s **de-emphasis of outbound** and **emphasis on product-led artifacts** (tools, shares) over forum pitching.

---

### 3.4 Hacker News / “Show HN” — high-variance, but a credible **10→100 “moment”**

**Observed pattern (search-indexed threads):** Fitness **Show HN** posts range from **hundreds of points** (e.g. Workout.lol ~993 points, 281 comments per index) to **single-digit** traction. **Discussion quality** often attacks **coaching correctness**—HN rewards **technical honesty** and punishes **shallow AI wrappers**.

**Advisor reassessment (not dismissive):** For StrideIQ, **variance is not the same as irrelevance**. A product with a **demo-able wow** (“connect Garmin → **true** statement about **your** body in minutes”) and **engineering depth** is **exactly** the profile HN often rewards—**when** the post is **substantive**, the founder **stays in the thread** to answer technical questions, and claims are **grounded** in determinism + safety (Athlete Trust contract), not vibe-marketing.

**Intervals.icu on HN (data point):** Intervals is discussed **organically** on HN (e.g. [thread 42915986](https://news.ycombinator.com/item?id=42915986)) with **user advocacy** (“totally worth paying to support”)—not necessarily a **founder-launched** Show HN. That supports **technical community pull** for analyst tools even without a formal launch post.

**Recommended package for a future StrideIQ Show HN (planning only — founder approves timing)**

| Element | Purpose |
|---------|---------|
| **Title** | Lead with **first-session truth**, not “AI coach” or “plans” (see **Strategic copy principle** above). |
| **Demo** | Screen recording or live: OAuth → sync → **one** suppressed-safe finding in **≤2 minutes** (or honest “insufficient data” if demo account is cold). |
| **Evidence** | Father–son state records as **outcome validation of the model**, not celebrity—tie to **what the engine would surface** (without violating privacy). |
| **Thread discipline** | Reply to **every** technical objection; link to **deterministic** behavior vs LLM slop; never overclaim. |
| **CTA** | Single URL + **what to do next** (trial, connect). |

**Risks:** Hostile coaching audits; privacy questions; “another AI app” skepticism—mitigate with **architecture honesty** and **contracts** (suppression, safety tests).

**Relationship to phased plan:** This is **not** a replacement for **Phase 1** (SEO + telemetry). Run **after** measurement exists so you can tag **hn** traffic in first-party analytics. Treat as **one-shot event**, not a weekly channel.

---

### 3.5 Garmin Connect IQ (alternate distribution surface)

**Garmin developer docs:** Connect IQ Store reaches **millions** of device users; submission/review for watch apps/widgets—[developer.garmin.com/connect-iq](https://developer.garmin.com/connect-iq/).

**Inference**

- **Native app spec** aside, **on-watch** distribution is a **different product** (Monkey C, store review). Not a substitute for **web SEO** in the near term; **long-term** optional wedge if StrideIQ ships **native** experiences.

---

### 3.6 Reddit — site-wide norms; **founder-specific constraint**

**Platform rule of thumb (long-standing Reddit culture):** Reddit Inc. and moderator guidance have historically described **self-promotion** as acceptable only when **a small fraction** of submissions link to your own site/product—the often-cited heuristic is **~90% neutral participation / ~10% self-link** (see [reddit.com/wiki/selfpromotion](https://www.reddit.com/wiki/selfpromotion) — **read current version**; rules evolve).

**Inference (general)**

- **Drive-by “check out my app”** posts are **high-ban-risk** and **low-trust**.
- **Earned** mention (someone else recommends your product) is the only **reliable** organic pattern for builders who will not farm karma.

**Founder-specific (StrideIQ):** The founder reports a **permanent ban** from **r/AdvancedRunning** after a dispute involving **moderation and competitor mention**—regardless of fault, **Reddit cannot be assigned** as a channel the founder will **personally** cultivate. **Do not** recommend “post in weekly thread” or “rebuild karma” as **founder** work. Third-party **earned** Reddit threads remain possible as **read-only** research only (see §5).

**Practical conclusion:** Prefer **product-mediated** discovery (SEO, shareable cards, Strava, **Show HN**, credible press/podcast) over **founder participation** on Reddit.

---

### 3.7 Measurement, attribution, and experiment discipline (deeper)

**Minimum viable instrumentation (Phase 1)**

- **Per-tool URL** (or route template) as dimension — not aggregate “/tools” only.
- **Funnel:** `tool_page_view` → `tool_result_view` (if applicable) → `signup_cta_click` → `account_created` (server-side if possible).
- **UTM standard** for any **manual** link (influencer Phase 4, newsletter, podcast): `utm_source`, `utm_medium`, `utm_campaign` — store on signup if schema allows.

**Attribution limits (honesty)**

- **Organic search:** last-click in first-party analytics undercounts **assist** channels; **Search Console** shows queries, not **users**.
- **Share cards (Phase 2):** use **UTM on shared URL** + **short link** domain you control to separate **share** from **SEO**.

**Experiment hygiene**

- Change **one** major variable per 2–4 weeks on a **single** landing (title vs CTA vs above-fold proof) — avoid changing **five** things and guessing what worked.

---

### 3.8 Behavioral wedge — compounding data as switching cost (StrideIQ-specific)

**Mechanism (product strategy doc alignment, not external study):** StrideIQ’s moat narrative—**the longer you use it, the less replaceable it becomes**—maps to **loss aversion** and **sunk expertise** in the athlete’s mental model: leaving means losing **relational** insight, not just **rows** of CSV.

**Growth implication**

- **Acquisition copy** should **not** lead with “AI coach” parity—lead with **specificity**: “something true about **your** history in the first session” (matches [`PRODUCT_STRATEGY_2026-03-03.md`](PRODUCT_STRATEGY_2026-03-03.md) first-session hook).
- **Shareable cards** work when they **evidence** that compounding (“confirmed **N** times”)—**social proof of intelligence**, not vanity.

---

## 4. Synthesis: what this research adds beyond “three proposals + process”

| Theme | Evidence | Implication for StrideIQ |
|--------|-----------|---------------------------|
| **Analyst lane** | Runalyze/TrainingPeaks/Smashrun histories | Buyers tolerate **complexity** if **trust + device sync** deliver; StrideIQ should **not** dumb down the pitch—**clarity** beats **simplicity**. |
| **Six-figure organic (analyst)** | Intervals.icu **100k+ athletes / 111M+ activities** by 2024; started as **Strava analysis extension** | **Word-of-mouth** can carry **deep** product to large scale **without** celebrity marketing—StrideIQ’s **first-session truth** hook must be **demonstrable** in onboarding. |
| **Infrastructure gravity** | Runalyze **30k+ users**, **7M activities**, file-based migration | Real scale creates **real** infra cost—StrideIQ’s engine depth is **feature + moat**, not “lite” analytics. |
| **Share graphics** | Runalyze 2018 social sharing feature; Strava-adjacent stat apps | **Shareable proof** is a **proven** category behavior; **finding cards** are differentiated if they carry **N=1 truth**, not vanity stats. |
| **Extension distribution** | Elevate for Strava — **Chrome Web Store** + forum help pattern | **Optional** parallel funnel; validates hunger for **more metrics** than Strava default UI. |
| **Market consolidation** | Strava **acquiring Runna** (2025); **100+** training apps on API | **Plan** lane is **strategically crowded**; StrideIQ wins on **retrospective intelligence + Manual**, not “another plan.” |
| **Coach / B2B2C** | TrainingPeaks origin | Optional **future** channel; **not** required for D2C Phase 1–2. |
| **SEO craft** | Technical SEO table + patio11-era discipline | Phase 1 = **indexation + canonical + query fit + CWV + internal links**—measurable; **90-day** diagnosis workflow. |
| **Forums** | LetsRun anti-ad rule; Reddit self-promo norms | **Earned** only; no **drive-by** spam strategy. |
| **Strava** | API scale + stat-sharing tools + **open platform** press narrative | **Phase 3** plausible with **trust UX** + **terms** review; **Phase 2** supplies **what** to say. |
| **Attribution** | Funnel + UTM + GSC limits (section 3.7) | Ship **telemetry first** so Phase 2–4 are **judged**, not narrated. |

**Novel strategic point (research-backed, not in the original three bullets):** The **convergence** of (a) **Runalyze-style share graphics**, (b) **Intervals-style organic analyst growth**, (c) **Strava ecosystem** distribution surfaces, and (d) **TrainingPeaks-style depth**—against a backdrop of **Strava buying a plan company**—suggests StrideIQ’s **differentiated** lane is **“intelligence + compounding N=1 model,”** not **plan parity** or **generic AI coach** copy.

---

### 4.1 Competitive framing matrix (where StrideIQ sits)

| Product archetype | Primary promise | StrideIQ overlap | StrideIQ non-overlap |
|-------------------|-----------------|------------------|----------------------|
| **Social graph** (Strava) | Belonging, segments, kudos | Strava sync, share | Not building **the** graph |
| **Adaptive planner** (Runna-class, Athletica) | Plan follows schedule/fitness | Plans exist | Moat is **not** static plan PDF |
| **Analyst workbench** (Runalyze, Intervals) | Depth, charts, zones | Serious athlete | StrideIQ adds **correlation + Manual + voice** |
| **Coach platform** (TrainingPeaks) | Coach-athlete workflow | Future coach tier possible | D2C first |
| **Augment Strava** (Elevate) | Better metrics in feed | Metaphor: “more insight” | StrideIQ is **full app**, not extension |

Use this matrix in **messaging** to avoid **unfavorable** comparison (“vs Runna plans”) and favor **orthogonal** comparison (“vs generic charts”).

---

## 5. Recommended primary follow-ups (outrank desk research)

1. **Google Search Console:** Export **queries, pages, CTR** for `/tools/*` over **12 months**; identify **query–page mismatch**.
2. **5–10 semi-structured interviews** with **masters + data-heavy** runners who use **Garmin + Strava** (not necessarily StrideIQ users): *how* they found **Intervals.icu**, Runalyze, TrainingPeaks, Athletica; **what** triggered signup; **whether** they pay for **multiple** tools (substitutes vs complements).
3. **Competitive teardown matrix** (same script for each): connect flow, **time-to-first surprising insight**, pricing, **trust moments** on site, **export/portability** narrative.
4. **Reddit (research only, not founder channel):** The founder is **not** to rely on **r/AdvancedRunning** participation (see §3.6). If useful, a **delegate** or **researcher** may do **read-only** thematic coding of “how I chose my training app” threads—**no** expectation of founder posting.
5. **Strava API Terms / Brand Guidelines:** Founder or counsel **read-through** of current **API Agreement** and **developer brand rules** before **Phase 3** implementation (not substituted by this memo).
6. **Chrome Web Store:** If an extension path is ever evaluated—**live** install snapshot for Elevate (desk research cites **aggregators**; marketing claims need **primary** store data).

---

## 6. References (URLs)

| Source | URL |
|--------|-----|
| Joe Friel — How TrainingPeaks Came to Be (2009) | https://trainingbible.com/joesblog/2009/10/how-trainingpeaks-came-to-be.html |
| Runalyze — Year in review 2018 | https://blog.runalyze.com/allgemein-en/year-in-review-2018/ |
| Runalyze — Major background migration (30k users, 7M activities) | https://blog.runalyze.com/allgemein-en/our-major-background-migration/ |
| Smashrun — Story | https://smashrun.com/about/story |
| Intervals.icu — About | https://www.intervals.icu/about/ |
| Elevate for Strava — GitHub | https://github.com/thomaschampagne/elevate |
| Elevate — Chrome Web Store | https://chromewebstore.google.com/detail/elevate-for-strava/dhiaggccakkgdfcadnklkbljcgicpckn |
| Strava — Press: Acquire Runna (Apr 2025) | https://press.strava.com/articles/strava-to-acquire-runna-a-leading-running-training-app |
| LetsRun — Community guidelines (spam/ad rule) | https://www.letsrun.com/forum/moderation-information-and-community-guidelines |
| Reddit — Self-promotion wiki | https://www.reddit.com/wiki/selfpromotion |
| Strava Developers — Authentication / API | https://developers.strava.com/docs/authentication/ |
| Kalzumeus Software (patio11) | https://www.kalzumeus.com |
| Garmin Connect IQ — Developer hub | https://developer.garmin.com/connect-iq/ |
| Hacker News — Intervals.icu organic thread (example) | https://news.ycombinator.com/item?id=42915986 |

---

## 7. Link to execution plan

Tactical sequencing, approval gates, and phase checkboxes remain in **[`docs/GROWTH_PHASED_PLAN.md`](GROWTH_PHASED_PLAN.md)**. This memo **informs** that plan; it does **not** replace founder approval or scoped implementation.
