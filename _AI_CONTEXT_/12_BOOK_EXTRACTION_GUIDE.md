# BOOK EXTRACTION GUIDE

**Last Updated:** Jan 4, 2026  
**Status:** Ready for Book Processing

## Recommended Formats

### Best Options (Easiest to Extract)

1. **EPUB** ⭐ RECOMMENDED
   - Best for text extraction
   - Can be parsed directly
   - Script: `scripts/extract_from_epub.py`
   - Available for:
     - Daniels' Running Formula (4th Edition) - Human Kinetics EPUB
     - Advanced Marathoning (4th Edition) - Human Kinetics EPUB

2. **PDF** ⭐ RECOMMENDED
   - Good for text extraction
   - Can be parsed with pdfplumber
   - Script: `scripts/extract_from_pdf.py`
   - Available for:
     - Faster Road Racing - Human Kinetics PDF

### Alternative Options

3. **Kindle (.azw, .mobi)**
   - Can convert to EPUB using Calibre
   - Or use Kindle's "Send to Kindle" feature to get PDF
   - Available for most books

4. **Library Borrows (Libby, Hoopla)**
   - Often EPUB or PDF format
   - Can download and extract

## Extraction Workflow

### Step 1: Extract Text from Book File

**For EPUB:**
```bash
docker compose exec api python scripts/extract_from_epub.py \
  /path/to/daniels_running_formula.epub \
  /app/extracted_texts/daniels_text.txt
```

**For PDF:**
```bash
docker compose exec api python scripts/extract_from_pdf.py \
  /path/to/faster_road_racing.pdf \
  /app/extracted_texts/faster_road_racing_text.txt
```

### Step 2: Extract Principles Using AI

```bash
docker compose exec api python scripts/extract_knowledge.py \
  /app/extracted_texts/daniels_text.txt \
  "Daniels' Running Formula (4th Edition)" \
  "Daniels" \
  book
```

### Step 3: Store in Knowledge Base

The extraction script automatically stores extracted principles in the database.

## Recommended Book Acquisition Order

### Priority 1: Core Books (Start Here)
1. **Daniels' Running Formula (4th Edition)** - EPUB from Human Kinetics
   - Contains RPI formula and pace tables
   - Core training principles
   - **Action:** Purchase EPUB, extract immediately

2. **Faster Road Racing** - PDF from Human Kinetics
   - 5K to half-marathon focus
   - Strong 5K plans
   - **Action:** Purchase PDF, extract immediately

### Priority 2: Marathon Focus
3. **Advanced Marathoning (4th Edition)** - EPUB from Human Kinetics
   - Marathon-specific training
   - Periodization models
   - **Action:** Purchase EPUB, extract

### Priority 3: Additional Methodologies
4. **Fast 5K** (Pete Magill) - Kindle
   - 5K-specific speed improvements
   - **Action:** Purchase Kindle, convert to EPUB if needed

5. **Hansons Marathon Method** - Kindle
   - Cumulative fatigue approach
   - **Action:** Purchase Kindle or borrow from library

6. **Marathon Excellence for Everyone** - Kindle/ebook
   - Modern, evidence-based approach
   - Canova influences
   - **Action:** Purchase if available

### Priority 4: Articles/Lectures
7. **Canova Articles** - Web content
   - RunningWritings.com analysis
   - Special blocks methodology
   - **Action:** Extract from web articles

## Extraction Scripts Created

1. **`extract_from_epub.py`** - Extracts text from EPUB files
2. **`extract_from_pdf.py`** - Extracts text from PDF files
3. **`extract_knowledge.py`** - Uses AI to extract principles from text

## Setup Instructions

### 1. Install Dependencies
The extraction scripts require:
- `pdfplumber` (for PDF) - ✅ Added to requirements.txt
- `PyPDF2` (fallback for PDF) - ✅ Added to requirements.txt
- `ebooklib` (for EPUB) - ✅ Added to requirements.txt

**Rebuild API container:**
```bash
docker compose build api
docker compose up -d api
```

### 2. Configure AI API Keys

Add to `.env` file:
```bash
ANTHROPIC_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here
```

### 3. Copy Books to Container

**Option A: Mount Volume**
Add to `docker-compose.yml`:
```yaml
api:
  volumes:
    - ./apps/api:/app
    - ./books:/books  # Mount books directory
```

**Option B: Copy into Container**
```bash
docker compose cp daniels_running_formula.epub running_app_api:/app/books/
```

## Extraction Process

### Example: Extract from Daniels' Running Formula

1. **Purchase EPUB** from Human Kinetics
2. **Copy to container:**
   ```bash
   docker compose cp daniels_running_formula.epub running_app_api:/app/books/
   ```

3. **Extract text:**
   ```bash
   docker compose exec api python scripts/extract_from_epub.py \
     /app/books/daniels_running_formula.epub \
     /app/extracted_texts/daniels_text.txt
   ```

4. **Extract principles:**
   ```bash
   docker compose exec api python scripts/extract_knowledge.py \
     /app/extracted_texts/daniels_text.txt \
     "Daniels' Running Formula (4th Edition)" \
     "Daniels" \
     book
   ```

5. **Verify extraction:**
   ```bash
   docker compose exec api python -c "
   from core.database import get_db_sync
   from models import CoachingKnowledgeEntry
   db = get_db_sync()
   entries = db.query(CoachingKnowledgeEntry).filter(
       CoachingKnowledgeEntry.methodology == 'Daniels'
   ).all()
   print(f'Found {len(entries)} entries')
   for e in entries[:3]:
       print(f'- {e.principle_type}: {e.source}')
   "
   ```

## What Gets Extracted

### From Each Book:

1. **RPI Formula** (if present)
   - Calculation method
   - Pace tables
   - Training pace formulas

2. **Periodization Principles**
   - Training phases
   - Volume progression
   - Intensity progression
   - Recovery principles

3. **General Principles**
   - Core training concepts
   - Workout types
   - Load progression rules
   - Recovery principles

## Next Steps After Extraction

1. **Review Extracted Principles**
   - Verify accuracy
   - Refine if needed

2. **Update RPI Calculator**
   - Replace approximations with exact formulas
   - Test against reference calculator

3. **Build AI Coaching Engine**
   - Use extracted principles
   - Generate personalized recommendations

4. **Test Learning System**
   - Track recommendations
   - Monitor outcomes

## Format Recommendations

**Best:** EPUB (Human Kinetics) - easiest to extract, clean text
**Good:** PDF (Human Kinetics) - good extraction quality
**OK:** Kindle - need to convert first
**Avoid:** Scanned PDFs (need OCR) - lower quality extraction

## Ready to Start

Once you have the EPUB or PDF files:
1. Copy them to the container
2. Run extraction scripts
3. Extract principles using AI
4. Knowledge base will be populated automatically

The infrastructure is ready - just need the book files!

