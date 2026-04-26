# Davis: Marathon Excellence & Training Load Series — Reference Note

**Source:** John Davis, Running Writings (2025-2026)
**Filed:** April 10, 2026
**Relevance:** Davis's book and training load series represent his
most complete thinking. The book is his definitive marathon training
system; the training load series provides the theoretical framework
for understanding stress, adaptation, and recovery across three
distinct dimensions.

---

## Marathon Excellence for Everyone (Book, September 2025)

### What It Is

Davis's comprehensive marathon training guide. 400+ scientific paper
citations. Five tiered training plans. Evidence-based race day
strategies. Over 2 years of writing + 12 years of coaching.

**"This book is my definitive answer to one of the most common
questions people ask me: how can I improve in the marathon?"**

### The Five Plans

| Plan | Peak mileage | Level |
|------|-------------|-------|
| Breeze | 40-50 mi/wk | Beginning marathoner |
| Wind | 55-65 mi/wk | Developing |
| Gale | 70-80 mi/wk | Established |
| Tornado | 85-95 mi/wk | Advanced |
| Hurricane | 100-120 mi/wk | Elite-level |

Each plan comes in 18-week and 12-week versions, with low-end and
high-end mileage variants — so each plan can be run at least twice
with progression.

**"These plans are not just scaled-up versions of the same training.
The workouts and periodization both scale intelligently with the
mileage level, keeping things simple for lower-mileage runners while
allowing more advanced marathoners to do longer and more sophisticated
workouts."**

### How Plans Scale (critical for the generator)

This is the key insight for our generator: different mileage tiers
don't just get more volume. They get different WORKOUT STRUCTURES:

- **Breeze (40-50):** Simpler workouts, longer general phase, fewer
  advanced techniques
- **Wind (55-65):** Moderate complexity, some float recovery
- **Gale (70-80):** Full workout spectrum, some doubles
- **Tornado (85-95):** Advanced techniques (double threshold, special
  blocks), regular doubles
- **Hurricane (100-120):** Full advanced toolkit, high-volume
  race-specific work

The generator should follow this principle: higher training age and
volume unlock more complex workout types, not just more miles of the
same workouts.

### Workout Detail Level

**"One thing that I believe quite strongly is that it matters how you
do your workouts, not just what workouts you do. To that end, all
workouts have detailed instructions and difficulty ratings."**

Every workout in Marathon Excellence includes:
- Detailed pace instructions (percentage-based)
- Difficulty rating
- Execution guidance (how to approach the session)
- Purpose explanation

This matches our quality bar: workout descriptions must tell the
athlete exactly what to do, why they're doing it, and how hard it
should feel.

### Beta Testing (92 runners)

Before publishing, Davis beta-tested the plans with 92 runners from
his email list across all five tiers. Results:
- Runners broke 4:00, 3:30, 3:00, 2:50, 2:40, 2:30, and even 2:20
- Success in tough conditions (Nashville hills, London heat, Boston)
- Favorite stories: "a mom returning after giving birth, a busy parent
  running his best marathon in ten years, an ordinary amateur runner
  squeezing under 3:00 in very hot conditions"

**"I scrapped some sessions that were too hard or too easy, and added
instructions to address things that were unclear."**

This validates the beta-testing approach for our V2 engine — real
athletes on real plans reveal what works and what doesn't.

### Tools

Davis created companion web applications:
- **Pace percentage calculator** (free) — calculates workout paces
  from race pace percentages
- **Heat-adjusted pace calculator** — estimates pace adjustments for
  hot/humid conditions
- **Track wind calculator** — wind effects on track workouts using
  biomechanics and track geometry

The heat-adjusted pace calculator is directly relevant to our
weather-adjusted pace feature.

---

## Three-Part Training Load Series (October-November 2025)

Davis argues there are three distinct types of training load that
must be considered independently:

### 1. Physiological Training Load

The traditional view: how much metabolic stress does the session
impose? Measured by volume, intensity, duration.

This is what most coaches and athletes think about when they say
"training load." But it's only one of three dimensions.

### 2. Biomechanical Training Load

**The mechanical stress on the body.** This is distance-specific:
- Running produces ground reaction forces of 2-3× body weight
- Tissue damage increases exponentially with speed
- Running economy degrades after 1-2 hours (even in pros)
- Injuries are driven by mechanical fatigue, not just metabolic stress

**Key implication:** A treadmill session at 4% grade produces the
same physiological load as flat running but LOWER biomechanical
load (no eccentric landing stress). This is why uphill TM training
is so valuable — same aerobic stimulus, less mechanical damage.

### 3. Psychological Training Load

**The mental and emotional cost of training.** Davis argues this is
"fascinating, subjective, and little-studied."

This maps directly to Roche's "Two Gas Tanks" theory (physical vs.
mental capacity). The worst training plans deplete the mental tank
faster than the physical one.

Factors that increase psychological load:
- Monotonous training (same workout every Tuesday)
- Pressure to hit exact paces
- Social media comparison
- Loss of autonomy in training decisions
- Training that conflicts with life responsibilities

Factors that decrease psychological load:
- Variety in workout types
- Distance ranges (athlete chooses)
- Fun and social elements
- Understanding the WHY of each session
- Feeling of progress and mastery

### Implications for StrideIQ

The three-load framework suggests our system should track and
manage ALL THREE dimensions:

1. **Physiological:** Already tracked via training load, TSB, ATL
2. **Biomechanical:** Could be estimated from pace, duration, and
   surface (road vs trail). Uphill TM sessions have lower
   biomechanical load for the same physiological cost.
3. **Psychological:** Harder to measure directly. But workout variety,
   distance ranges, effort-based language, and the coaching voice all
   reduce psychological load. The correlation engine could potentially
   detect psychological overload through patterns (skipped workouts,
   declining engagement, negative coach interactions).

---

## Additional Davis Articles Inventory

| Article | Date | Status |
|---------|------|--------|
| Full-spectrum percentage-based training overview | Dec 2023 | Filed (reference note) |
| SSmax for runners | Aug 2024 | Filed (reference note) |
| Physiological resilience | Aug 2024 | Summarized in physiology synthesis |
| Full-spectrum 10K plan from scratch | Oct 2024 | **Filed (this session)** |
| Coe-style elite 800/1500/mile training | Mar 2026 | Filed (reference note) |
| Modern marathon training principles | Dec 2025 | Filed (reference note + 5 principles) |
| Marathon Excellence book | Sep 2025 | **Summarized (this document)** |
| Training load series (3 parts) | Oct-Nov 2025 | **Summarized (this document)** |
| Post-race workouts guide | Dec 2025 | Noted, not yet filed |
| Kristoffer Ingebrigtsen threshold | Jul 2025 | Noted, not yet filed |
| Percy Cerutty philosophy | Aug 2025 | Noted, not yet filed |
| Video: How to build a marathon plan | Jan 2026 | Noted, not yet filed |
| Two workouts not in Marathon Excellence | Nov 2025 | Noted, not yet filed |
| Psychological training load | Nov 2025 | **Summarized (this document)** |

Davis is the most prolific and rigorous writer among our three primary
sources. His work should carry significant weight in the generator's
theoretical foundation, particularly for road racing (5K through
marathon).
