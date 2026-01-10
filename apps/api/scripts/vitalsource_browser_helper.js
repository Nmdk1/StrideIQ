/**
 * VitalSource Text Extraction Helper
 * 
 * Paste this into browser console (F12) while viewing VitalSource book
 * 
 * Instructions:
 * 1. Open your VitalSource book in browser
 * 2. Press F12 to open Developer Tools
 * 3. Go to Console tab
 * 4. Paste this entire script
 * 5. Press Enter
 * 6. Text will be extracted and copied to clipboard
 * 7. Navigate to next page and run again
 */

(function() {
    console.log('🔍 Extracting text from VitalSource reader...');
    
    // Function to extract text from various VitalSource selectors
    function extractText() {
        let allText = [];
        const seen = new Set();
        
        // Common VitalSource selectors
        const selectors = [
            'div[class*="reader"]',
            'div[class*="content"]',
            'div[class*="text"]',
            'p',
            'span[class*="text"]',
            '[role="textbox"]',
            '.vs-reader-content',
            '#reader-content',
            '[data-testid*="content"]'
        ];
        
        // Try each selector
        for (const selector of selectors) {
            try {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    const text = (el.innerText || el.textContent || '').trim();
                    if (text && text.length > 30 && !seen.has(text)) {
                        seen.add(text);
                        allText.push(text);
                    }
                });
            } catch (e) {
                // Ignore selector errors
            }
        }
        
        // Also try getting text from body
        const bodyText = document.body.innerText || document.body.textContent || '';
        if (bodyText.length > 100) {
            // Split into paragraphs
            const paragraphs = bodyText.split(/\n\s*\n/).filter(p => p.trim().length > 30);
            paragraphs.forEach(p => {
                const trimmed = p.trim();
                if (!seen.has(trimmed)) {
                    seen.add(trimmed);
                    allText.push(trimmed);
                }
            });
        }
        
        return allText.join('\n\n');
    }
    
    // Extract text
    const extracted = extractText();
    
    if (!extracted || extracted.length < 100) {
        console.warn('⚠️ Could not extract much text. Try:');
        console.log('1. Make sure you\'re on a page with visible text');
        console.log('2. Try scrolling down to load more content');
        console.log('3. Check if page is fully loaded');
        
        // Show what we found
        console.log('Found elements:', document.querySelectorAll('div, p').length);
        return;
    }
    
    console.log(`✅ Extracted ${extracted.length} characters`);
    console.log(`📄 ${extracted.split('\n\n').length} paragraphs`);
    
    // Copy to clipboard
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(extracted).then(() => {
            console.log('✅ Text copied to clipboard!');
            console.log('📋 Paste into your text file now');
        }).catch(err => {
            console.error('❌ Could not copy to clipboard:', err);
            console.log('📄 Text is in console - scroll up to see it');
        });
    } else {
        console.log('📄 Extracted text:');
        console.log('---');
        console.log(extracted);
        console.log('---');
        console.log('(Copy the text above manually)');
    }
    
    // Also create download link
    const blob = new Blob([extracted], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vitalsource_page_${Date.now()}.txt`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('💾 File download started!');
    console.log('📝 Repeat for each page/chapter');
    
    return extracted;
})();

