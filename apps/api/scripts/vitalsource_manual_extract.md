# VitalSource Manual Extraction Guide

**Fastest way to extract from VitalSource web reader:**

## Option 1: Browser Console Script (Easiest)

1. **Open your VitalSource book** in Chrome/Firefox
2. **Open Developer Console** (F12 → Console tab)
3. **Paste this script:**

```javascript
// Extract all visible text from VitalSource reader
function extractVitalSourceText() {
    let text = '';
    
    // Try different selectors VitalSource might use
    const selectors = [
        '[class*="reader"]',
        '[class*="content"]',
        '[class*="text"]',
        'p',
        'div[role="textbox"]',
        '.vs-reader-content',
        '#reader-content'
    ];
    
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            const txt = el.innerText || el.textContent;
            if (txt && txt.length > 20) {
                text += txt + '\n\n';
            }
        });
    }
    
    // Remove duplicates
    const lines = text.split('\n').filter((line, index, self) => 
        line.trim() && self.indexOf(line) === index
    );
    
    return lines.join('\n');
}

// Run extraction
const extracted = extractVitalSourceText();
console.log(extracted);

// Copy to clipboard
navigator.clipboard.writeText(extracted).then(() => {
    console.log('✅ Text copied to clipboard!');
    console.log(`Extracted ${extracted.length} characters`);
});
```

4. **Navigate through pages** (click next) and run script again
5. **Paste each page** into a text file
6. **Save as** `daniels_running_formula.txt`

## Option 2: Browser Extension (Better)

Use a browser extension like:
- **Copy All URLs** or **Text Grabber**
- Or install **Tampermonkey** and create a script to auto-extract

## Option 3: Manual Copy-Paste (Simplest)

1. Open VitalSource reader
2. Select all text on page (Ctrl+A)
3. Copy (Ctrl+C)
4. Paste into text file
5. Repeat for each page/chapter
6. Save as `daniels_running_formula.txt`

## Then Extract Principles

Once you have the text file:

```bash
docker compose exec api python scripts/extract_knowledge.py \
  /app/books/daniels_running_formula.txt \
  "Daniels' Running Formula" \
  "Daniels" \
  book
```

**Note:** This is for personal use of content you've purchased.

