# IMPLEMENTATION ROADMAP: AI Coaching Knowledge Base

**Last Updated:** Jan 4, 2026  
**Status:** Strategic Planning

## How This Fits Into Current Development

### Current State
- ✅ Diagnostic engine (efficiency trends, load mapping, recovery elasticity)
- ✅ WMA age-grading
- ✅ Performance metrics and race detection
- 🚧 Production infrastructure (Celery, caching, rate limiting)
- 📋 Product tiers and monetization strategy defined

### AI Knowledge Base Integration Points

**1. Diagnostic Engine → AI Coaching**
- Current diagnostic signals feed into AI coaching engine
- AI uses signals to personalize coaching recommendations
- Example: "Efficiency trend positive → can increase intensity per Daniels principles"

**2. Knowledge Base → Fixed Plans (Tier 2)**
- Fixed plans generated using knowledge base principles
- Demonstrates value before subscription
- Example: "Daniels-inspired 5K plan" but personalized to athlete's VDOT

**3. Knowledge Base → Guided Coaching (Tier 3)**
- AI generates weekly guidance using knowledge base + activity data
- Personalized but no recovery insights
- Example: "Based on Pfitzinger periodization, adjusted for your load efficiency"

**4. Knowledge Base → Premium Coaching (Tier 4)**
- Full AI coaching with knowledge base + all diagnostic signals
- Maximum personalization including recovery correlations
- Example: "Canova special blocks, but spaced 72h apart based on your recovery elasticity"

## Implementation Strategy (PRE-LAUNCH)

**Timeline:** Now through March 15, 2026 Launch

### Phase 1: Knowledge Base Foundation (Now - Feb 1)

**Goal:** Build knowledge base infrastructure and extract core principles

**Tasks:**
1. **Acquire Source Material** ✅ START NOW
   - Purchase/download coaching books (Daniels, Pfitzinger, Canova, Hansen, Roche, Bitter, etc.)
   - Collect articles, research papers, coach interviews
   - Build library of coaching methodologies

2. **Build Knowledge Extraction Pipeline** ✅ OPERATIONAL
   - ✅ PDF/text ingestion system (scripts created)
   - ✅ EPUB extraction (`extract_from_epub.py`)
   - ✅ PDF extraction (`extract_from_pdf.py`)
   - ✅ Web content extraction (`crawl_running_writings.py`)
   - ✅ Google Docs extraction (`download_google_docs.py`)
   - ✅ Patreon extraction (`patreon_browser_extractor.js` + `process_patreon_json.py`)
   - ✅ Text chunking and storage (`store_text_chunks.py`)
   - ✅ Training plan extraction (`extract_training_plans.py`)
   - ✅ Principle extraction (`extract_principles_direct.py`)
   - ✅ Direct text analysis (working without external AI APIs)
   - 🚧 AI extraction (Claude/GPT-4) for enhanced extraction (optional)
   - 📋 Create embeddings for semantic search (pgvector setup pending)

3. **Extract Core Principles** ✅ IN PROGRESS
   - ✅ 239 entries extracted from 9 sources
   - ✅ 20 training plans extracted and stored
   - ✅ 50+ principle entries extracted and stored
   - 🚧 VDOT formula and pace tables (Daniels) - extraction in progress
   - 🚧 Periodization models (Pfitzinger, Canova) - extraction in progress
   - 🚧 Load progression principles - extraction in progress
   - 🚧 Recovery and adaptation principles - extraction in progress
   - 🚧 Special blocks and training concepts (Canova, Hansen, etc.) - extraction in progress

4. **Build Knowledge Base Storage** ✅ PARTIALLY COMPLETE
   - ✅ Structured database operational (PostgreSQL with knowledge base tables)
   - ✅ 239 entries stored in `coaching_knowledge_entries` table
   - ✅ Training plans stored with metadata
   - ✅ Principles stored with source attribution
   - ✅ Cross-methodology tagging system (JSONB tags with GIN index)
   - ✅ Methodology opacity architecture (neutral terminology translation layer)
   - ✅ Blending rationale tracking (`blending_rationale` field in `CoachingRecommendation`)
   - 📋 Vector database setup (pgvector extension in PostgreSQL) - pending
   - ✅ Source material storage (local `/books` directory)

**Deliverable:** Queryable knowledge base with core coaching principles

---

### Phase 2: AI Coaching Engine Integration ✅ COMPLETE (Jan 4, 2026)

**Goal:** Integrate knowledge base with diagnostic engine for AI coaching

**Tasks:**
1. **Build AI Coaching Engine** ✅ COMPLETE
   - ✅ Knowledge base query system (tag-based JSONB queries)
   - ✅ Methodology opacity architecture (neutral terminology + translation)
   - ✅ Blending heuristics service (adaptive methodology selection)
   - ✅ Principle-based plan generator (4-18 week flexible durations)
   - ✅ Enhanced validation layer (5 safety checks)
   - ✅ Client-facing translation (methodology stripped)
   - 📋 Runtime AI service integration (for advanced synthesis - future)
   - 📋 Prompt engineering for coaching recommendations (future)

2. **Personalization Logic** ✅ COMPLETE
   - ✅ Map diagnostic signals to coaching adjustments (blending heuristics)
   - ✅ Efficiency trend → intensity adjustments
   - ✅ Recovery elasticity → session spacing
   - ✅ Volume tolerance → methodology selection
   - ✅ Injury history → lower-intensity approaches

3. **Generate Fixed Plans (Tier 2)** ✅ COMPLETE
   - ✅ AI generates plans using knowledge base principles
   - ✅ Personalized to athlete's current fitness (VDOT)
   - ✅ Flexible durations (4-18 weeks) for abbreviated builds
   - ✅ Enhanced validation ensures plan safety
   - 📋 Manual verification workflow (to be implemented)
   - 📋 Human review process (to be implemented)

4. **Basic Weekly Guidance (Tier 3)** 🚧 NEXT
   - 📋 AI generates weekly recommendations
   - 📋 Uses knowledge base + activity-based diagnostic signals
   - 📋 Personalized workout prescriptions

**Deliverable:** ✅ AI-powered coaching recommendations for Tier 2 & 3 (plan generation complete)

---

### Phase 3: Learning System (Feb 15 - March 1)

**Goal:** Continuous learning system - ALWAYS TRACK OUTCOMES

**Tasks:**
1. **Build Learning System** 🚧 IN PROGRESS
   - Track recommendation outcomes (ALWAYS)
   - Identify what works/doesn't work per athlete
   - Build athlete-specific coaching profiles
   - Refine personalization rules
   - Store outcomes in database

2. **Outcome Tracking Infrastructure**
   - Database schema for tracking recommendations → outcomes
   - Metrics: efficiency trends, PB probability, injury rates, adherence
   - Correlation analysis: which principles work for which athletes

3. **Continuous Refinement**
   - System learns from every outcome
   - Adjusts recommendations based on historical success
   - Builds personal coaching "DNA" per athlete

**Deliverable:** Learning system tracking all outcomes and refining recommendations

---

### Phase 4: Launch Preparation (March 1 - March 15)

**Goal:** Polish and prepare for launch

**Tasks:**
1. **Expand Knowledge Base**
   - Add more coaches/methodologies as available
   - Include cutting-edge research
   - Continuous updates

2. **Premium Features (Tier 4)**
   - Full AI coaching with recovery insights (when Garmin/Coros available)
   - Advanced personalization using all diagnostic signals
   - Recovery-based correlation adjustments

3. **Testing & Validation**
   - Test AI coaching recommendations
   - Validate knowledge base accuracy
   - Ensure learning system is tracking correctly

**Deliverable:** Launch-ready AI coaching system

## Technical Architecture

### Knowledge Base Layer
```
coaching_knowledge/
├── sources/
│   ├── books/
│   │   ├── daniels_running_formula.pdf
│   │   ├── advanced_marathoning.pdf
│   │   └── ...
│   ├── articles/
│   └── research/
├── extracted/
│   ├── principles/
│   │   ├── vdot_formula.py
│   │   ├── periodization_models.py
│   │   └── ...
│   └── embeddings/
│       └── vector_database/
└── metadata/
    └── relationships.json
```

### AI Coaching Service
```
services/
├── ai_coaching/
│   ├── knowledge_base.py      # Query knowledge base
│   ├── coaching_engine.py     # Generate recommendations
│   ├── personalization.py      # Adjust for athlete data
│   └── learning.py            # Track outcomes and learn
```

### Integration Points
- **Diagnostic Engine:** Feeds personal data signals
- **Knowledge Base:** Provides coaching principles
- **AI Engine:** Synthesizes knowledge + data
- **Learning System:** Refines based on outcomes

## Key Design Decisions

### 1. Knowledge Base Structure
**Decision:** Hybrid approach (vector DB + structured DB)
- Vector DB for semantic search ("find principles about tempo training")
- Structured DB for algorithms and relationships (VDOT formula, periodization rules)

### 2. AI Model Selection
**Decision:** Claude API for runtime (better reasoning) + embeddings for search
- Development: Claude Opus/Sonnet (via Cursor)
- Runtime: Claude API (for coaching recommendations)
- Embeddings: OpenAI or Cohere (for knowledge base search)

### 3. Personalization Approach
**Decision:** Diagnostic signals inform adjustments to coaching principles
- Don't replace principles with data
- Use data to adjust/prune principles
- Example: "Daniels suggests X, but your recovery elasticity suggests Y → use Y"

### 4. Learning Strategy
**Decision:** Outcome-based learning with athlete-specific profiles
- Track which principles work for which athletes
- Build personal coaching "DNA" per athlete
- Continuously refine recommendations

### 5. Cost Management
**Decision:** Tier-based AI usage + caching
- Tier 2: Basic AI (fixed plans)
- Tier 3: Moderate AI (weekly guidance)
- Tier 4: Full AI (comprehensive coaching)
- Cache common queries and patterns

## Success Metrics

**Knowledge Base:**
- Number of coaches/methodologies: Target 10+ major coaches
- Coverage: All major training concepts (VDOT, periodization, etc.)
- Query quality: Accurate, relevant results

**AI Coaching:**
- Recommendation acceptance: >70% of recommendations followed
- Outcome improvement: Positive efficiency trends for coached athletes
- Personalization: Athlete-specific adjustments working

**Learning System:**
- Accuracy: Correctly identify what works/doesn't work
- Improvement: Recommendations get better over time
- Personalization: Each athlete gets unique coaching profile

## Risks & Mitigations

**Risk 1: AI Hallucination**
- Mitigation: Ground AI in knowledge base, validate recommendations against principles
- Human review of critical recommendations

**Risk 2: Cost of AI Calls**
- Mitigation: Tier-based usage, caching, batch processing
- Consider fine-tuned models for common patterns

**Risk 3: Knowledge Base Quality**
- Mitigation: Careful extraction, validation, expert review
- Continuous refinement based on outcomes

**Risk 4: Over-Personalization**
- Mitigation: Balance personalization with proven principles
- Don't abandon core coaching wisdom

## Next Steps

1. **Immediate (Current Development):**
   - Continue Phase 1.5 infrastructure
   - Build landing page + VDOT calculator
   - Set up subscription tiers

2. **Post-Launch (Months 1-3):**
   - Acquire coaching books
   - Build knowledge extraction pipeline
   - Extract core principles (VDOT, periodization)

3. **Months 3-6:**
   - Integrate AI coaching engine
   - Generate AI-powered fixed plans
   - Basic weekly guidance for Tier 3

4. **Months 6-12:**
   - Expand knowledge base
   - Build learning system
   - Advanced personalization

This is a long-term vision that transforms the product from a diagnostic tool into an AI-powered coaching system that synthesizes the world's best knowledge with personal physiology.

