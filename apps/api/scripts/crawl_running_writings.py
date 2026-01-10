#!/usr/bin/env python3
"""
Crawl RunningWritings.com for training content

Extracts articles, training principles, and coaching content from John Davis's site.
"""
import sys
import os
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def extract_article_content(soup: BeautifulSoup) -> Dict:
    """Extract main article content from page."""
    content = {
        "title": "",
        "text": "",
        "categories": [],
        "tags": [],
        "date": ""
    }
    
    # Extract title
    title_tag = soup.find('h1') or soup.find('title')
    if title_tag:
        content["title"] = title_tag.get_text().strip()
    
    # Extract main content (usually in article tag or main content div)
    article = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile('content|post|entry'))
    if article:
        # Remove script and style elements
        for script in article(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        
        # Get text content
        text = article.get_text(separator='\n', strip=True)
        content["text"] = text
    
    # Extract categories and tags
    for tag in soup.find_all(['a', 'span'], class_=re.compile('category|tag')):
        tag_text = tag.get_text().strip()
        if tag_text:
            if 'category' in str(tag.get('class', [])).lower():
                content["categories"].append(tag_text)
            elif 'tag' in str(tag.get('class', [])).lower():
                content["tags"].append(tag_text)
    
    # Extract date
    date_tag = soup.find('time') or soup.find(class_=re.compile('date|published'))
    if date_tag:
        content["date"] = date_tag.get_text().strip()
    
    return content


def get_article_urls_from_search_results() -> List[str]:
    """Get article URLs from known articles (fallback if crawling fails)."""
    # Known article URLs from the site
    return [
        "https://runningwritings.com/principles-of-modern-marathon-training/",
        "https://runningwritings.com/guide-to-post-race-workouts/",
        "https://runningwritings.com/tissue-loading-tissue-damage-running-injuries/",
        "https://runningwritings.com/psychological-training-load-runners/",
        "https://runningwritings.com/biomechanical-training-load-runners/",
        "https://runningwritings.com/race-pace-calculator/",
    ]


def crawl_author_page(base_url: str, max_pages: int = 20) -> List[str]:
    """
    Crawl author page and extract all article links.
    
    Args:
        base_url: Base URL for author page
        max_pages: Maximum number of pages to crawl
        
    Returns:
        List of article URLs
    """
    article_urls = []
    page = 1
    
    while page <= max_pages:
        # Construct URL (handles pagination)
        if page == 1:
            url = base_url
        else:
            url = f"{base_url}page/{page}/"
        
        print(f"  Crawling page {page}: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://runningwritings.com/'
            }
            response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links - look for post titles/headings
            links = []
            base_domain = urlparse(base_url).netloc
            
            # Look for links in article titles, headings, or post listings
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if not href:
                    continue
                
                # Make absolute URL
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                
                # Skip if not same domain or if it's the author page itself
                if parsed.netloc != base_domain:
                    continue
                if '/author/' in full_url:
                    continue
                if full_url == base_url or full_url == base_url.rstrip('/'):
                    continue
                
                # Check if it looks like an article URL (has date, category, or is a post)
                link_text = link.get_text().strip()
                if link_text and len(link_text) > 10:  # Has meaningful text
                    # Check if parent is a heading or article element
                    parent = link.parent
                    if parent and (parent.name in ['h1', 'h2', 'h3', 'h4'] or 
                                  'entry-title' in str(parent.get('class', [])) or
                                  'post-title' in str(parent.get('class', []))):
                        if full_url not in article_urls and full_url not in links:
                            links.append(full_url)
                            print(f"    Found: {link_text[:60]}...")
            
            if not links:
                print(f"  No more articles found on page {page}")
                break
            
            article_urls.extend(links)
            print(f"  Found {len(links)} articles on page {page}")
            
            # Check if there's a next page
            next_link = soup.find('a', string=re.compile('Next|next'))
            if not next_link:
                break
            
            page += 1
            time.sleep(1)  # Be respectful with rate limiting
            
        except Exception as e:
            print(f"  Error crawling page {page}: {e}")
            break
    
    return article_urls


def crawl_and_extract(base_url: str, max_articles: int = 50):
    """
    Crawl RunningWritings.com and extract training content.
    
    Args:
        base_url: Base URL to start crawling
        max_articles: Maximum number of articles to extract
    """
    if not REQUESTS_AVAILABLE:
        print("❌ requests and BeautifulSoup4 not available")
        print("   Install with: pip install requests beautifulsoup4 lxml")
        return
    
    db = get_db_sync()
    try:
        print(f"🚀 Starting crawl of {base_url}")
        print(f"   Max articles: {max_articles}")
        
        # Get article URLs
        print("\n📋 Finding article URLs...")
        article_urls = crawl_author_page(base_url, max_pages=20)
        
        # If crawling failed, use known URLs from site
        if not article_urls:
            print("  ⚠️  Crawling blocked, using known article URLs...")
            article_urls = [
                "https://runningwritings.com/principles-of-modern-marathon-training/",
                "https://runningwritings.com/guide-to-post-race-workouts/",
                "https://runningwritings.com/tissue-loading-tissue-damage-running-injuries/",
                "https://runningwritings.com/psychological-training-load-runners/",
                "https://runningwritings.com/biomechanical-training-load-runners/",
                "https://runningwritings.com/race-pace-calculator/",
            ]
            # Try to get more from main site
            try:
                main_url = "https://runningwritings.com/"
                print(f"  Trying main site: {main_url}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                response = requests.get(main_url, timeout=15, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        if href and 'runningwritings.com' in href and href not in article_urls:
                            if any(x in href for x in ['/training', '/marathon', '/workout', '/injury', '/coaching', '/']):
                                if href.count('/') >= 2:  # Has path beyond domain
                                    article_urls.append(href)
            except Exception as e:
                print(f"  Could not access main site: {e}")
        
        # Limit to max_articles
        article_urls = article_urls[:max_articles]
        print(f"\n✅ Found {len(article_urls)} articles to extract")
        
        # Extract content from each article
        extracted_count = 0
        for i, url in enumerate(article_urls, 1):
            print(f"\n[{i}/{len(article_urls)}] Extracting: {url}")
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://runningwritings.com/'
                }
                response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                content = extract_article_content(soup)
                
                if not content["text"] or len(content["text"]) < 200:
                    print(f"  ⚠️  Skipping - content too short or empty")
                    continue
                
                # Store article
                entry = CoachingKnowledgeEntry(
                    source="RunningWritings.com - John Davis",
                    methodology="Davis",
                    source_type="web_article",
                    text_chunk=content["text"][:2000],  # Store first 2000 chars as preview
                    extracted_principles=json.dumps({
                        "title": content["title"],
                        "url": url,
                        "categories": content["categories"],
                        "tags": content["tags"],
                        "date": content["date"],
                        "full_text": content["text"]
                    }),
                    principle_type="article",
                    metadata_json=json.dumps({
                        "url": url,
                        "title": content["title"],
                        "categories": content["categories"],
                        "tags": content["tags"]
                    })
                )
                db.add(entry)
                extracted_count += 1
                
                print(f"  ✅ Extracted: {content['title'][:60]}... ({len(content['text'])} chars)")
                
                # Commit every 10 articles
                if extracted_count % 10 == 0:
                    db.commit()
                    print(f"  💾 Committed {extracted_count} articles")
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"  ❌ Error extracting {url}: {e}")
                continue
        
        db.commit()
        print(f"\n✅ Crawl complete!")
        print(f"   Extracted {extracted_count} articles")
        print(f"   Stored in knowledge base")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python crawl_running_writings.py <base_url> [max_articles]")
        print("\nExample:")
        print("  python crawl_running_writings.py https://runningwritings.com/author/john-davis 50")
        sys.exit(1)
    
    base_url = sys.argv[1]
    max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    crawl_and_extract(base_url, max_articles)
    print("✅ Done!")


if __name__ == "__main__":
    main()

