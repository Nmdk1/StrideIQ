# AUDIBLE EXTRACTION GUIDE

**Last Updated:** Jan 4, 2026  
**Status:** Possible but Complex

## Challenge with Audible

Audible files (.aax) are:
- **Audio-only** (not text)
- **DRM-protected** (can't directly extract)
- Require **speech-to-text transcription**

## Options for Audible Books

### Option 1: Convert Audible + Transcribe (Complex)

**Step 1: Convert .aax to .mp3/.wav**
- Use tools like `ffmpeg` + `audible-cli` or `OpenAudible`
- Removes DRM and converts to standard audio format
- **Note:** May violate Audible's terms of service

**Step 2: Transcribe Audio to Text**
- Use OpenAI Whisper API (best quality)
- Or local Whisper model (free but slower)
- Script: `scripts/transcribe_audible.py`

**Step 3: Extract Principles**
- Use extracted text with `extract_knowledge.py`

**Pros:**
- Can use existing Audible purchases
- No need to buy again

**Cons:**
- More complex workflow
- Transcription quality may vary
- Time-consuming (hours of audio)
- May violate Audible terms

### Option 2: Get Text Versions (Recommended)

**Better Approach:**
1. Check if books available as EPUB/PDF
2. Purchase text versions (often similar price)
3. Extract directly (much faster, better quality)

**Why Text is Better:**
- ✅ Faster (minutes vs hours)
- ✅ More accurate (no transcription errors)
- ✅ Preserves formatting/tables
- ✅ No DRM issues
- ✅ Easier to process

## Recommendation

**For Knowledge Extraction: Get Text Versions**

The books you mentioned are available as EPUB/PDF:
- **Daniels' Running Formula** - EPUB available (~$25)
- **Faster Road Racing** - PDF available (~$20-25)
- **Advanced Marathoning** - EPUB available

**Benefits:**
- Direct text extraction (no transcription)
- Better accuracy (no speech-to-text errors)
- Faster processing
- Preserves formulas/tables

## If You Must Use Audible

If you want to proceed with Audible transcription:

### 1. Convert .aax to .mp3
```bash
# Requires OpenAudible or similar tool
# This removes DRM and converts format
```

### 2. Transcribe
```bash
docker compose exec api python scripts/transcribe_audible.py \
  /books/daniels_audio.mp3 \
  /app/extracted_texts/daniels_text.txt
```

### 3. Extract Principles
```bash
docker compose exec api python scripts/extract_knowledge.py \
  /app/extracted_texts/daniels_text.txt \
  "Daniels' Running Formula (Audible)" \
  "Daniels" \
  audiobook
```

**Time Estimate:**
- 10-hour audiobook ≈ 2-4 hours transcription time
- Plus extraction time

## Best Approach

**Recommendation:** Purchase EPUB/PDF versions for extraction
- Faster
- More accurate
- Easier workflow
- Better for formulas/tables

**Use Audible for:** Listening/learning
**Use EPUB/PDF for:** Knowledge extraction

## Cost Comparison

- **Audible:** ~$15-25/month subscription + individual books
- **EPUB/PDF:** ~$20-25 per book (one-time)
- **Transcription:** Free (local) or ~$0.006/minute (API)

**For extraction:** EPUB/PDF is more cost-effective and faster.

## Decision

**If you have Audible and want to use it:**
- I can help set up transcription
- Will take longer but can work
- Quality may vary

**If you want fastest/best results:**
- Purchase EPUB/PDF versions
- Extract directly
- Better accuracy

Your choice! I can support either approach.

