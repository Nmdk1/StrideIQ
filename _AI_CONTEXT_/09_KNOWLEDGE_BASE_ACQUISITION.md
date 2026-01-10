# KNOWLEDGE BASE ACQUISITION PLAN

**Last Updated:** Jan 4, 2026  
**Status:** Active - START NOW

## Immediate Action Items

### 1. Acquire Coaching Books (Priority: HIGH - START NOW)

**Core Books (Must Have):**
- ✅ **Daniels' Running Formula** by Jack Daniels (EXTRACTED: 63 entries, 7 principles, 4 training plans)
- ✅ **Advanced Marathoning** by Pete Pfitzinger & Scott Douglas (EXTRACTED: 77 entries, 6 principles, 3 training plans)
- ✅ **Fast 5K: 25 Crucial Keys & 4 Training Plans** by Pete Magill (EXTRACTED: 21 entries, 5 principles, 2 training plans)
- ✅ **Hanson's Half-Marathon Method** by Luke Humphrey (EXTRACTED: 45 entries, 4 principles, 1 training plan)
- ✅ **SWAP 12-Week Marathon Plan** by David & Megan Roche (EXTRACTED: 4 entries, 2 principles, 2 training plans)
- ✅ **SWAP 5k/10k Speed Plan** by David & Megan Roche (EXTRACTED: 3 entries, 2 principles, 2 training plans)
- ✅ **David & Megan Roche Patreon Posts** (EXTRACTED: 10 entries, 10 principles)
- 📋 **Running with the Buffaloes** by Chris Lear (Canova methodology)
- 📋 **Training for the Uphill Athlete** by Steve House & Scott Johnston (Hansen methodology)
- 📋 **The Happy Runner** by David Roche & Megan Roche
- 📋 **Training Essentials for Ultrarunning** by Jason Koop (ultra-specific)
- 📋 **80/20 Running** by Matt Fitzgerald

**Additional Sources:**
- ✅ **RunningWritings.com** - John Davis articles (EXTRACTED: 8 entries, 7 principles, 4 training plans)
- ✅ **Basic Training Principles** - John Davis (Google Drive) (EXTRACTED: 5 entries, 5 principles)
- ✅ **Full Spectrum 10K Schedule** - 16-week plan (EXTRACTED: 3 entries, 2 principles, 2 training plans)
- 📋 **Training for the New Alpinism** by Steve House (Hansen)
- 📋 **Training for Climbing** by Eric Horst (cross-training principles)
- 📋 Research papers on periodization, adaptation, recovery
- 📋 Coach interviews and podcasts (transcripts)
- 📋 Historical training data from elite athletes

**Acquisition Method:**
- Purchase digital versions (Kindle, PDF) for easy ingestion
- Physical books → scan/OCR if needed
- Articles → web scraping or manual collection
- Research papers → academic databases

---

### 2. Knowledge Extraction Pipeline (Priority: HIGH)

**Technology Stack:**
- **PDF Processing:** PyPDF2, pdfplumber, or similar
- **Text Extraction:** OCR if needed (Tesseract)
- **AI Extraction:** Claude Opus/Sonnet (via Cursor), Claude API, GPT-4
- **Vector Embeddings:** OpenAI embeddings, Cohere, or local models
- **Storage:** PostgreSQL (pgvector extension) or Pinecone/Weaviate

**Pipeline Steps:**
1. **Ingest:** PDF/text → raw text
2. **Chunk:** Break into manageable sections (chapters, concepts)
3. **Extract:** AI extracts principles, algorithms, methodologies
4. **Structure:** Convert to structured format (JSON, database)
5. **Embed:** Create vector embeddings for semantic search
6. **Store:** Save to vector DB + structured DB

**Extraction Prompts (Examples):**
- "Extract the VDOT formula and pace tables from this text"
- "Identify periodization principles and training phases"
- "Extract load progression rules and recovery principles"
- "Identify workout types and their purposes"
- "Extract special training concepts (e.g., Canova special blocks)"

---

### 3. Core Principles to Extract (Priority: HIGH)

**From Daniels:**
- VDOT formula and calculation
- Pace tables (E, M, T, I, R paces)
- Training principles and laws
- Periodization model
- Workout prescriptions

**From Pfitzinger:**
- Marathon training principles
- Long run guidelines
- Medium-long run principles
- Recovery and injury prevention
- Periodization for marathoners

**From Canova:**
- Special blocks concept
- Race-specific training
- Volume and intensity principles
- Recovery between hard sessions

**From Hansen:**
- Aerobic base building
- Uphill/downhill training
- Periodization model
- Recovery principles

**From Roche:**
- Happy running philosophy
- Training principles
- Recovery and adaptation

**From Others:**
- 80/20 principles (Fitzgerald)
- Ultrarunning specifics (Koop)
- Marathon methods (Hansons)

---

### 4. Knowledge Base Structure

**Vector Database (Semantic Search):**
- Store text chunks with embeddings
- Enable queries like: "Find principles about tempo training"
- Technology: pgvector (PostgreSQL extension) or Pinecone/Weaviate

**Structured Database (Algorithms/Rules):**
- VDOT formula (code/algorithm)
- Pace tables (structured data)
- Periodization models (rules/logic)
- Workout prescriptions (templates)
- Technology: PostgreSQL

**Source Material Storage:**
- Original PDFs/texts
- Extracted structured data
- Metadata (author, source, date, etc.)
- Technology: S3 or local storage

---

### 5. Implementation Plan

**Week 1-2 (Now - Jan 18):**
- ✅ Acquire core books (Daniels, Pfitzinger, Magill, Humphrey, Roche)
- ✅ Set up knowledge extraction pipeline
- ✅ Extract text from 9 sources (239 entries stored)
- ✅ Extract training plans (20 plans stored)
- ✅ Extract principles (50+ entries stored)
- ✅ Set up database storage (PostgreSQL with knowledge base tables)
- 🚧 Extract exact VDOT formula from stored text
- 🚧 Set up vector database (pgvector) for semantic search

**Week 3-4 (Jan 19 - Feb 1):**
- 📋 Extract periodization principles
- 📋 Extract load progression rules
- 📋 Extract recovery principles
- 📋 Build structured database schema

**Week 5-6 (Feb 2 - Feb 15):**
- 📋 Integrate with AI coaching engine
- 📋 Test knowledge base queries
- 📋 Refine extraction pipeline

**Week 7-8 (Feb 16 - March 1):**
- 📋 Expand knowledge base (more coaches)
- 📋 Continuous refinement
- 📋 Testing and validation

---

### 6. AI Model Selection

**Development (Cursor):**
- Claude Opus/Sonnet for extraction and code generation
- Best reasoning capabilities

**Runtime (API):**
- **Claude API:** Best reasoning, good for complex synthesis
- **GPT-4:** Good reasoning, sometimes faster
- **Both:** Use best tool for each job
- **Decision:** Start with Claude API, add GPT-4 if needed

**Embeddings:**
- **OpenAI embeddings:** High quality, reliable
- **Cohere:** Alternative option
- **Local models:** Consider for cost savings later

---

### 7. Success Criteria

**Knowledge Base:**
- ✅ Core books acquired and extracted (9 methodologies, 239 entries)
- ✅ Training plans extracted (20 plans stored)
- ✅ Principles extracted (50+ entries stored)
- ✅ Structured database operational (PostgreSQL)
- 📋 VDOT formula extracted and implemented (extraction in progress)
- 📋 Periodization principles extracted (extraction in progress)
- 📋 Load progression rules extracted (extraction in progress)
- 📋 Vector database operational (pgvector setup pending)

**Extraction Quality:**
- Accurate principle extraction
- Proper structuring
- Queryable format
- Semantic search working

**Integration:**
- Knowledge base accessible to AI coaching engine
- Queries return relevant results
- Principles can be applied to athlete data

---

## Next Steps (IMMEDIATE)

1. **TODAY:** Acquire Daniels' Running Formula and Advanced Marathoning (digital versions)
2. **THIS WEEK:** Set up knowledge extraction pipeline
3. **THIS WEEK:** Extract VDOT formula as proof of concept
4. **NEXT WEEK:** Extract periodization principles
5. **ONGOING:** Always track outcomes and refine

This is infrastructure - start now, refine continuously.

