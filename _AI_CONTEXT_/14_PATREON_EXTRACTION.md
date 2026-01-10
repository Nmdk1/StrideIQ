# PATREON EXTRACTION GUIDE

**Last Updated:** Jan 4, 2026  
**Status:** Requires Manual Browser Extraction

## Challenge with Patreon

Patreon content is:
- **Behind authentication** (requires login)
- **Protected from scraping** (blocks automated access)
- **Requires subscription** (most content is paywalled)

## Solution: Browser-Based Extraction

Since you're subscribed, use the browser script to extract content:

### Step 1: Extract Posts Using Browser Script

1. **Log into Patreon** in your browser
2. **Navigate to:** https://www.patreon.com/c/swap/posts
3. **Open Developer Console:** Press F12 → Console tab
4. **Copy and paste** the script from `apps/api/scripts/patreon_browser_extractor.js`
5. **Press Enter** - script will:
   - Extract all visible posts
   - Scroll to load more posts
   - Create JSON file
   - Copy JSON to clipboard

### Step 2: Save the JSON

The script will:
- Download a JSON file automatically
- Copy JSON to clipboard

**Save the file** as `patreon_roche.json` in the `books/` folder

### Step 3: Process the JSON

Once you have the JSON file:

```bash
docker compose exec api python scripts/process_patreon_json.py /books/patreon_roche.json
```

This will:
- Extract all posts
- Store them in the knowledge base
- Make them available for AI coaching engine

## Alternative: Manual Export

If the browser script doesn't work:

1. **Manually copy** post content from Patreon
2. **Save to text file** in `books/` folder
3. **Run extraction:**

```bash
docker compose exec api python scripts/store_text_chunks.py \
  /books/patreon_roche.txt \
  "Patreon - David and Megan Roche" \
  "Roche" \
  web_article
```

## What Gets Extracted

- Post titles
- Full post content
- Publication dates
- Post URLs
- Training principles and advice

## Notes

- Patreon uses infinite scroll - script will scroll to load more posts
- May take a few minutes for large numbers of posts
- Script stops after 10 scrolls or 50 posts (adjustable in script)

