# Pre-Race Performance Prediction: Literature Review

*Compiled March 2026 for StrideIQ feature development*

This document summarizes the sports science literature on pre-race performance prediction, training block analysis, taper optimization, and N=1 performance modeling for distance runners. The goal is to establish a scientifically rigorous foundation — not a marketing narrative.

---

## 1. Pre-Race Performance Predictors

### What training metrics actually predict race performance?

**The short answer: no single metric is a reliable standalone predictor.** The evidence shows that training load variables alone explain only about 26.5% of the variance in long-distance race prediction models, with aerobic metabolism variables (43.4%) and anthropometric factors (20.6%) also being significant (systematic review: *Predictive Performance Models in Long-Distance Runners*, IJERPH, 2020).

#### CTL / Chronic Training Load

CTL correlates with performance potential but does not guarantee performance. Research on competitive road cyclists found large to very large relationships (r = 0.54–0.81) between training load methods and changes in aerobic fitness variables (Newman et al., Guild HE repository). However, **individualized training load metrics** (iTRIMP, TSS) show stronger dose-response relationships than generic load measures.

In endurance runners, modeled performance based on training load correlated with actual 1,500m performance:
- Running TSS: r = 0.70 ± 0.11
- Session-RPE: r = 0.60 ± 0.10
- TRIMP methods: r = 0.65 ± 0.13

(Wallace et al., *European Journal of Applied Physiology*, 2014)

**Key takeaway for StrideIQ:** CTL is necessary but not sufficient. It represents the "have you done the work?" question. The shape of the curve, the taper execution, and the athlete's individual response characteristics matter at least as much as the absolute value.

#### Training Intensity Distribution

The most robust finding in endurance training science is the importance of intensity distribution. Seiler & Kjerland (2006, *Scandinavian Journal of Medicine & Science in Sports*) established that elite endurance athletes consistently train with a **polarized distribution**: ~75% low intensity (below first lactate threshold), ~8% moderate, ~15-20% high intensity.

A 2024 study in *Sports Medicine* (Springer) analyzed marathon runners across performance levels and found:
- Over 80% of the fastest marathon runners employ a **pyramidal** intensity distribution
- Faster runners distinguish themselves by accumulating higher overall training volumes, primarily via more low-intensity training
- Strong correlations (R² ≥ 0.90) between high training volume and marathon performance

The distinction between pyramidal (most volume low, progressively less at each higher zone) and polarized (high volume low + high, minimal moderate) remains debated, but both outperform threshold-heavy approaches.

#### The Shape of the Fitness Curve

Alan Couzens' "influence curves" analysis (2009) provides the most practically useful framework here. The critical finding:
- Training in the **7-3 week window before competition** has the greatest positive influence on performance
- Training in the **0-14 day window** generally has a negative effect on performance (fatigue outweighs fitness gain)
- The **14-21 day window** is a gray zone varying by individual

This means it's not just "how fit are you" but "what shape is your fitness trajectory relative to race day."

---

## 2. Taper Science

### The Canonical Meta-Analyses

**Bosquet, Montpetit & Arvisais (2007)** — *Medicine & Science in Sports & Exercise*
- Meta-analysis of 27 studies
- Optimal taper duration: **~2 weeks**
- Overall effect size: 0.59 ± 0.33 (P < 0.001)
- This is the most cited work establishing evidence-based taper recommendations

**Bosquet et al. (2023, PMC)** — Updated systematic review and meta-analysis
- 8-14 day taper with **41-60% reduction in training volume** optimal for most endurance athletes
- Taper typically produces **2-3% performance improvements**, which can be decisive at competitive levels

### The Three Levers of Taper

The research converges on three variables, ranked by importance:

1. **Volume** — Reduce substantially (41-60% is the sweet spot; range across studies: 17.6-85%)
2. **Intensity** — **Maintain or slightly increase.** This is the single most important finding in taper research. Mujika (2010, *Scandinavian Journal of Medicine & Science in Sports*) emphasizes: "the training load should not be reduced at the expense of intensity during the taper"
3. **Frequency** — Can be maintained or moderately reduced with similar results. Studies split roughly 50/50 on frequency reduction with both approaches working.

### Taper Pattern: Step vs. Exponential vs. Progressive

- **Exponential decay** tapers are most studied and generally recommended for endurance athletes
- **Step tapers** (abrupt reduction) may produce superior muscle fiber adaptations in strength athletes (Frontiers in Physiology, 2021) but evidence in endurance is weaker
- The **progressive nonlinear taper** (gradually decreasing volume with maintained intensity) has the most support for distance runners

### Individual Variability in Optimal Taper

This is a critical gap in the literature. Most taper research uses population-level recommendations. However:

- Taper responses vary substantially between individuals
- Thomas et al. (2014, PLOS ONE) found that among 11 Olympic gold medal endurance performers, **only 3 of 11 took a rest day in the final 5 days before competition** — contradicting conventional taper advice
- The pre-taper level of fatigue influences taper effectiveness (PMC, 2024): athletes who are more fatigued going into a taper may need different protocols than those who aren't

**Implication for StrideIQ:** Population-based taper recommendations are a reasonable starting point but the real value is in learning each athlete's individual taper response over multiple race cycles. This is an N=1 problem.

### The Functional Overreaching Question

Aubry et al. (2014, *Medicine & Science in Sports & Exercise*) studied 33 triathletes through overload + taper cycles. Counterintuitively:
- Athletes who became **functionally overreached** showed **less** supercompensation than those who experienced only acute fatigue
- The acute-fatigue group showed 2.6% ± 1.1% greater performance improvement than the overreached group
- **Conclusion: "train hard then taper" doesn't mean "train to exhaustion then taper."** There's a ceiling beyond which pre-taper fatigue hurts rather than helps.

---

## 3. Training Block Periodization and Outcomes

### Block Periodization vs. Traditional

Block periodization (concentrating training stimuli into short focused blocks) produces superior improvements over traditional mixed approaches in well-trained athletes:
- Cyclists: BP achieved 8.8% vs 3.7% improvement in VO2max (Rønnestad et al., published in multiple journals)
- Effect sizes are moderate to large across multiple performance indices

### What Block Characteristics Predict Good Race Performance?

The literature points to several key characteristics:

**Volume trajectory:**
- Elite marathon runners achieve best results with high absolute training volumes (220-280+ km/week for elites, scaled proportionally for sub-elite)
- Volume should build progressively during preparation phases, not spike acutely
- The ACWR (Acute:Chronic Workload Ratio) sweet spot is 0.8-1.3; spikes above 2.0 are associated with 5-7x injury risk (Hulin et al., 2016, BJSM)

**Intensity distribution within blocks:**
- Blocks should follow the polarized/pyramidal pattern described above
- As competition approaches, training becomes more polarized and sport-specific (Thomas et al., 2014)
- In the final 6 weeks before major competition, elite athletes reduced volume 15-32% while maintaining absolute high-intensity volume

**Periodization approach of gold medalists (Thomas et al., 2014, PLOS ONE):**
- General Preparation Phase: 6-10 months before competition
- Specific Preparation Phase: 4-5 months before competition
- Competition Phase: 0-3 months before competition
- Total annual training: 700-900 hours across ~500 sessions
- 94% of training is aerobic; of that, ~90% is low intensity

### ACWR and Performance Readiness

While ACWR research has focused primarily on injury risk, the same framework applies to performance readiness:
- Low chronic workload is more dangerous than short recovery time (Hulin et al., 2016, BJSM)
- Maintaining high chronic training load is protective AND performance-enabling
- Acute spikes relative to chronic load indicate under-preparation, not overtraining per se

---

## 4. N=1 Performance Modeling

### The Banister Impulse-Response Model (1975)

The foundational model. Performance = fitness – fatigue, where both fitness and fatigue are impulse responses to training load with different time constants (fitness builds slowly and decays slowly; fatigue builds quickly and decays quickly).

**Strengths:**
- Conceptually elegant and physiologically intuitive
- Individual parameter estimation captures athlete-specific response characteristics
- Can model taper effects and predict optimal taper timing theoretically

**Weaknesses (critical):**
A 2025 study in *Scientific Reports* identified major statistical flaws:
- Overfitting: adding fatigue parameters didn't significantly improve prediction (p > 0.40) in 2 independent datasets
- Poor parameter identifiability: the model can't reliably distinguish fitness effects from fatigue effects
- Goodness-of-fit ≠ predictive ability: fits historical data but fails to predict future performance reliably
- Parameters are sensitive to starting values, modeling technique, and input variables (Pfeifer, IJSPP, 2022)

### The Busso Model

An extension of Banister with time-varying parameters. Applied to a middle-distance runner, achieved r² = 0.92 (P < 0.01) over a 12-week training period (QUT ePrints). The fatigue component correlated with psychological measures (POMS vigor: r² = 0.92; recovery metrics: r² = 0.78-0.87).

**Key limitation:** requires individualized parameter estimation specific to each athlete. Cannot be generalized.

### Bayesian Approaches (2024)

A 2024 SportRxiv preprint developed a Bayesian approach to the Banister model that:
- Formalizes prior knowledge integration with athlete data
- Produces more precise parameter estimates than nonlinear least squares
- Enables continuous model updating as new data accumulate
- Better handles the small sample sizes inherent in N=1 modeling

**This is the most promising direction for StrideIQ.** Bayesian methods naturally handle the "small N, many parameters" problem that plagues traditional fitting approaches.

### Modern ML Approaches

A 2025 systematic literature review found:
- **Ensemble models (Random Forest, XGBoost, LightGBM)** outperform traditional approaches for running performance prediction
- **Deep learning (LSTM, GRU)** effectively model temporal training dynamics
- Training experience is the strongest predictor of training methodology response (r = 0.72)
- ML identified four distinct athlete response types: polarized responders (31.5%), pyramidal responders (31.9%), dual responders (18.7%), non-responders (17.9%)

A key finding from Terra Research (tryterra.co): consumer wearable data combined with ML can produce useful marathon pace predictions, though the specific accuracy metrics vary.

### The Honest Assessment

**The fitness-fatigue model family (Banister, Busso, etc.) is better as a conceptual framework than a predictive tool.** The recommendation from Pfeifer et al. (IJSPP, 2022) is to use these models "data-informed" rather than "data-driven" — they help structure thinking about training-performance relationships but should not be trusted as precise prediction instruments.

For StrideIQ, this means: **don't try to predict a race time from training data with false precision. Instead, characterize the athlete's preparation state relative to their own history and identify signals (positive and negative) that correlate with their individual best performances.**

---

## 5. Pre-Race Wellness and Performance

### Sleep

- Ultra-endurance athletes: better physical performance was associated with extended sleep the night before competition and increased light sleep time; longer wake time and lower sleep quality predicted poorer outcomes (MDPI, JCM, 2024)
- Sleep extension improves endurance performance markers; sleep restriction impairs them (NSCA JSCR, 2022)
- The relationship between sleep and performance is **individual** — population-level "8 hours" recommendations miss substantial inter-individual variation

### HRV

**Kiviniemi et al. (2007, *European Journal of Applied Physiology*):**
The landmark study showing HRV-guided training outperforms predetermined training:
- HRV-guided group: VO2peak improved from 56 to 60 ml/kg/min (P = 0.002)
- Predetermined group: VO2peak showed no significant change (P = 0.224)
- Key mechanism: HRV as morning measurement tells you whether the athlete's autonomic nervous system has recovered enough for high-intensity work

**Nocturnal HRV (Schmitt et al., 2024, Sports Medicine - Open):**
- First 4 hours of sleep HRV segments correlate with subsequent training adaptation
- HRV responses during early sleep predicted 3000m performance changes in runners

**HRV as overreaching marker:**
- Aubry et al. (2015, PLOS ONE): functional overreaching is associated with faster heart rate recovery — counterintuitive but useful as a detection signal
- Declining HRV trends over days/weeks indicate accumulating fatigue before subjective symptoms appear

### Subjective Wellness Markers

**Saw, Main & Gastin (2016, BJSM):** This systematic review of 56 studies found:
- **Subjective self-reported measures OUTPERFORM commonly used objective measures** for monitoring training response
- Subjective and objective measures generally don't correlate with each other
- Subjective measures reflect both acute and chronic training loads with superior sensitivity and consistency
- Mood and perceived stress are more sensitive to training load changes than blood markers, HR, or VO2

**Halson (2014, *Sports Medicine*):** Monitoring tools include:
- Profile of Mood States (POMS)
- Daily Analysis of Life Demands for Athletes (DALDA)
- Recovery-Stress Questionnaire for Athletes (RESTQ-Sport)
- Dissociation between external load and internal load reveals fatigue state

**Implication for StrideIQ:** Self-reported wellness data (sleep quality, energy, mood, muscle soreness, stress) may be MORE predictive of race readiness than any objective metric, including HRV. The challenge is getting athletes to log it consistently and honestly.

### The Multivariate Reality

No single wellness marker predicts race performance in isolation. The evidence supports a **multivariate approach** combining:
1. Subjective wellness (mood, fatigue, sleep quality, stress)
2. HRV trends (not single readings — the trajectory matters)
3. Training load context (is the athlete in a build, taper, or recovery phase?)
4. Sleep quantity and quality
5. The athlete's individual baseline and response patterns

---

## 6. Race-to-Race Patterns Within Cycles

### Tune-Up Race → Goal Race Prediction

The academic literature on this specific topic is thin. Most evidence comes from coaching practice rather than controlled research:

- Standard practice: use race equivalency calculators (VDOT, Riegel formula) to estimate goal race times from shorter tune-up results
- Half marathon time × 2.1-2.2 is the rough marathon prediction rule
- Tune-up races are recommended 3-8 weeks before goal races depending on distances (shorter distance = closer to race day is acceptable)

**What the science doesn't adequately address:**
- How tune-up race performance *relative to expected performance* predicts goal race outcome
- Whether a tune-up race PR is a positive or negative signal (did the athlete peak too early? or are they in great shape?)
- How the recovery cost of the tune-up race affects goal race performance

**This is a significant opportunity for StrideIQ's correlation engine.** With sufficient individual race history + training data, you could learn athlete-specific relationships between tune-up performance and goal race outcomes that the literature hasn't established at a population level.

### Peak Fitness Timing

Thomas et al. (2014, PLOS ONE) on Olympic gold medalists:
- Athletes trained 92% sport-specific in the final 6 weeks
- Volume decreased 15-32% from preparation to competition phase
- Only 3 of 11 took a rest day in the final 5 days — most kept training lightly through race week
- Absolute high-intensity volume was maintained even as total volume dropped

The evidence suggests peak performance occurs when:
1. High chronic fitness has been built (high CTL / chronic training load)
2. Acute fatigue has been dissipated (through taper)
3. But not so much rest that detraining has begun (2-3 weeks max for most athletes)

---

## 7. Personal Bests and Fitness Trajectory

### When Do PBs Occur?

Based on the influence curve analysis and the training patterns of gold medal performers:

**PBs tend to occur when:**
1. Chronic training load is at or near its highest sustained level for that cycle
2. A 1-3 week taper has allowed fatigue to dissipate while fitness is largely preserved
3. The training block leading into the taper featured **substantial loading in the 7-3 week pre-race window**
4. The athlete is NOT functionally overreached going into the taper (acute fatigue is fine; overreaching is not)
5. Subjective wellness markers are positive (energy, mood, sleep quality)

**PBs do NOT tend to occur when:**
1. CTL is rising steeply (still building, not yet consolidated)
2. CTL is declining (detraining or post-injury)
3. The athlete skipped the taper or tapered too aggressively/too long
4. ACWR is elevated (acute spike relative to chronic preparation)
5. Subjective wellness is impaired

### Individual Variation

The most critical finding across ALL of this research is the enormous inter-individual variation:

- Kiviniemi et al. and the HRV literature show different athletes respond to the same training differently
- ML research identifies 4 distinct response types (polarized responders, pyramidal responders, dual responders, non-responders)
- Taper research shows optimal duration, volume reduction, and frequency changes vary by individual
- A 2025 systematic review (PMC) found that much of the observed "inter-individual variation" may actually be measurement error — but true individual differences DO exist, they're just smaller than raw data suggests

**For StrideIQ:** The product's value proposition is precisely in learning these individual patterns. Population-level findings give you priors. Individual history gives you the real signal.

---

## Summary: What StrideIQ Should Build On

### High-Confidence Findings (Build on These)
1. **Intensity distribution matters** — polarized/pyramidal approaches produce better outcomes
2. **Taper = reduce volume, maintain intensity** — 2 weeks, 40-60% volume reduction, intensity preserved
3. **Subjective wellness markers outperform objective markers** for monitoring training response
4. **HRV trends (not single values) track training adaptation** and predict readiness
5. **Individual variation is real** — population norms are starting points, not endpoints
6. **The 7-3 week pre-race training window** is the most influential for performance
7. **Functional overreaching hurts taper supercompensation** — more is not always better

### Moderate-Confidence Findings (Use Cautiously)
1. CTL/fitness metrics explain ~25-70% of performance variance depending on methodology
2. ACWR 0.8-1.3 is the "sweet spot" for performance and injury avoidance
3. Bayesian N=1 models show promise but are early-stage
4. Sleep quality the night before competition correlates with performance
5. Tune-up race results can inform goal race predictions via equivalency formulas

### Low-Confidence / Research Gaps (Opportunity for StrideIQ)
1. Individualized taper optimization — almost no controlled research exists
2. Tune-up → goal race prediction patterns at individual level
3. Multivariate pre-race readiness scoring combining subjective + objective + training context
4. When PBs occur relative to individual fitness curves (anecdotal, not rigorously studied)
5. How training block characteristics interact with individual response profiles to produce outcomes

### What NOT to Build
1. **Don't build a single-number race predictor with false precision.** The science doesn't support it.
2. **Don't use the raw fitness-fatigue model as a prediction engine.** It has documented statistical flaws and overfitting problems.
3. **Don't ignore subjective data.** The literature is clear: subjective measures are more sensitive than most objective measures.
4. **Don't assume one taper protocol fits all athletes.** The evidence for individual variation is strong.

---

## Key References

### Taper Science
- Bosquet L, Montpetit J, Arvisais D, Mujika I. (2007). Effects of tapering on performance: a meta-analysis. *Medicine & Science in Sports & Exercise*, 39(8):1358-65.
- Mujika I. (2010). Intense training: the key to optimal performance before and during the taper. *Scand J Med Sci Sports*, 20(Suppl 2):24-31.
- Aubry A, et al. (2014). Functional overreaching: the key to peak performance during the taper? *Medicine & Science in Sports & Exercise*, 46(9):1769-77.

### Training Load and Performance
- Seiler KS, Kjerland GØ. (2006). Quantifying training intensity distribution in elite endurance athletes. *Scand J Med Sci Sports*, 16(1):49-56.
- Thomas L, Mujika I, Busso T. (2014). The road to gold: Training and peaking characteristics in the year prior to a gold medal endurance performance. *PLOS ONE*, 9(7):e101796.
- Soligard T, et al. (2016). How much is too much? IOC consensus statement on load in sport and risk of injury. *BJSM*, 50(17):1030-41.

### N=1 Modeling
- Banister EW, et al. (1975). A systems model of training for athletic performance. *Aust J Sports Med*, 7:57-61.
- Busso T, et al. (2002). Effects of training frequency on the dynamics of performance response to a single training bout. *J Appl Physiol*, 92(2):572-80.
- Clarke DC, Skiba PF. (2013). Rationale and resources for teaching the mathematical modeling of athletic training and performance. *Adv Physiol Educ*, 37:134-52.
- Pfeifer C, et al. (2022). The fitness-fatigue model: What's in the numbers? *IJSPP*, 17(5):810-18.
- Kolossa D, et al. (2025). Statistical flaws of the fitness-fatigue sports performance prediction model. *Scientific Reports*.

### Wellness Monitoring
- Saw AE, Main LC, Gastin PB. (2016). Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures. *BJSM*, 50(5):281-91.
- Halson SL. (2014). Monitoring training load to understand fatigue in athletes. *Sports Medicine*, 44(Suppl 2):S139-47.
- Kiviniemi AM, et al. (2007). Endurance training guided individually by daily heart rate variability measurements. *Eur J Appl Physiol*, 101(6):743-51.

### Individual Variation
- Bonafiglia JT, et al. (2025). Inter-individual heterogeneity in aerobic training adaptations: systematic review. *PMC*.
- ML-based personalized training models. (2025). *Scientific Reports*.

### Block Periodization
- Rønnestad BR, et al. (2012). Effects of 12 weeks of block periodization on performance in well-trained cyclists.
- Stöggl TL, Sperlich B. (2014). Polarized training has greater impact on key endurance variables than threshold, high-intensity, or high-volume training. *Front Physiol*.
