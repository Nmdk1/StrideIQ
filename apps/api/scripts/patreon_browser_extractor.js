/**
 * Patreon Content Extractor
 * 
 * Run this in your browser console while logged into Patreon
 * Instructions:
 * 1. Log into Patreon
 * 2. Go to https://www.patreon.com/c/swap/posts
 * 3. Open Developer Console (F12)
 * 4. Paste this entire script
 * 5. Press Enter
 * 6. Wait for extraction to complete
 * 7. Copy the output JSON
 */

(function() {
    console.log('🔍 Extracting Patreon posts...');
    
    const posts = [];
    const seenUrls = new Set();
    
    // Function to extract post content
    function extractPost(postElement) {
        try {
            // Find title
            const titleEl = postElement.querySelector('h3, h2, [class*="title"], [class*="post-title"]');
            const title = titleEl ? titleEl.innerText.trim() : '';
            
            // Find content
            const contentEl = postElement.querySelector('[class*="content"], [class*="post-content"], article, .post-body');
            const content = contentEl ? contentEl.innerText.trim() : '';
            
            // Find date
            const dateEl = postElement.querySelector('time, [class*="date"], [class*="published"]');
            const date = dateEl ? dateEl.innerText.trim() : '';
            
            // Find URL
            const linkEl = postElement.querySelector('a[href*="/posts/"]');
            const url = linkEl ? linkEl.href : '';
            
            if (title || content) {
                return {
                    title: title,
                    content: content,
                    date: date,
                    url: url,
                    length: content.length
                };
            }
        } catch (e) {
            console.warn('Error extracting post:', e);
        }
        return null;
    }
    
    // Find all post elements
    const postSelectors = [
        'article',
        '[class*="post"]',
        '[class*="Post"]',
        '[data-tag="post-card"]',
        '[class*="card"]'
    ];
    
    let postElements = [];
    for (const selector of postSelectors) {
        const elements = document.querySelectorAll(selector);
        if (elements.length > 0) {
            postElements = Array.from(elements);
            console.log(`Found ${elements.length} elements with selector: ${selector}`);
            break;
        }
    }
    
    // Extract posts
    postElements.forEach((el, index) => {
        const post = extractPost(el);
        if (post && post.content.length > 50) {
            if (!seenUrls.has(post.url)) {
                seenUrls.add(post.url);
                posts.push(post);
                console.log(`✅ Extracted post ${posts.length}: ${post.title.substring(0, 50)}...`);
            }
        }
    });
    
    // Scroll and load more posts (Patreon uses infinite scroll)
    console.log('\n📜 Scrolling to load more posts...');
    let lastPostCount = posts.length;
    let scrollAttempts = 0;
    const maxScrolls = 10;
    
    const scrollInterval = setInterval(() => {
        window.scrollTo(0, document.body.scrollHeight);
        scrollAttempts++;
        
        setTimeout(() => {
            // Check for new posts
            const newPosts = document.querySelectorAll('article, [class*="post"]');
            if (newPosts.length > lastPostCount || scrollAttempts >= maxScrolls) {
                // Extract new posts
                Array.from(newPosts).slice(lastPostCount).forEach(el => {
                    const post = extractPost(el);
                    if (post && post.content.length > 50 && !seenUrls.has(post.url)) {
                        seenUrls.add(post.url);
                        posts.push(post);
                        console.log(`✅ Extracted post ${posts.length}: ${post.title.substring(0, 50)}...`);
                    }
                });
                
                lastPostCount = posts.length;
                
                if (scrollAttempts >= maxScrolls || posts.length >= 50) {
                    clearInterval(scrollInterval);
                    finishExtraction();
                }
            }
        }, 2000);
    }, 3000);
    
    function finishExtraction() {
        console.log(`\n✅ Extraction complete! Found ${posts.length} posts`);
        
        // Create JSON output
        const output = {
            source: "Patreon - David and Megan Roche (Some Work, All Play)",
            methodology: "Roche",
            extracted_at: new Date().toISOString(),
            total_posts: posts.length,
            posts: posts
        };
        
        // Copy to clipboard
        const jsonStr = JSON.stringify(output, null, 2);
        navigator.clipboard.writeText(jsonStr).then(() => {
            console.log('✅ JSON copied to clipboard!');
            console.log('\n📋 Next steps:');
            console.log('1. Save the JSON to a file (patreon_roche.json)');
            console.log('2. Or paste it here and I can process it');
        }).catch(() => {
            console.log('\n📋 JSON output:');
            console.log(jsonStr);
            console.log('\n(Copy the JSON above)');
        });
        
        // Also create download
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `patreon_roche_${Date.now()}.json`;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('💾 File download started!');
        
        return output;
    }
    
    // If no posts found initially, try alternative extraction
    if (posts.length === 0) {
        console.log('⚠️  No posts found with standard selectors');
        console.log('Trying alternative method...');
        
        // Try extracting from page text
        const bodyText = document.body.innerText;
        const postMatches = bodyText.match(/(.{50,500})/g);
        if (postMatches) {
            postMatches.slice(0, 20).forEach((text, i) => {
                if (text.length > 100) {
                    posts.push({
                        title: `Post ${i + 1}`,
                        content: text,
                        date: '',
                        url: window.location.href,
                        length: text.length
                    });
                }
            });
        }
        
        if (posts.length > 0) {
            finishExtraction();
        } else {
            console.log('❌ Could not extract posts automatically');
            console.log('Please manually copy post content or use Patreon export feature');
        }
    }
    
    return posts;
})();

