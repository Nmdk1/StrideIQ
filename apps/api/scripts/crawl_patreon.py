#!/usr/bin/env python3
"""
Crawl Patreon for training content

Extracts publicly available content from Patreon creators.
Note: Most Patreon content requires authentication/subscription.
"""
import sys
import os
import json
import time
import re
from pathlib import Path
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


def extract_patreon_content(url: str):
    """
    Extract content from Patreon page.
    
    Note: Patreon content is typically behind authentication.
    This will only extract publicly available content.
    """
    if not REQUESTS_AVAILABLE:
        print("❌ requests and BeautifulSoup4 not available")
        return
    
    db = get_db_sync()
    try:
        print(f"🚀 Attempting to extract from Patreon: {url}")
        print("   Note: Most Patreon content requires authentication")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.patreon.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Could not access page (status {response.status_code})")
            print("   Patreon content typically requires login/subscription")
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract publicly available content
        # Patreon pages usually show previews/teasers
        content = {
            "title": "",
            "description": "",
            "posts_preview": []
        }
        
        # Try to find title
        title_tag = soup.find('title') or soup.find('h1')
        if title_tag:
            content["title"] = title_tag.get_text().strip()
        
        # Try to find description/about section
        description_tags = soup.find_all(['p', 'div'], class_=re.compile('description|about|bio'))
        for tag in description_tags:
            text = tag.get_text().strip()
            if text and len(text) > 50:
                content["description"] += text + "\n\n"
        
        # Try to find post previews (usually limited for non-subscribers)
        post_elements = soup.find_all(['article', 'div'], class_=re.compile('post|entry|card'))
        for post in post_elements[:10]:  # Limit to 10
            post_text = post.get_text(separator='\n', strip=True)
            if post_text and len(post_text) > 100:
                content["posts_preview"].append(post_text[:500])  # Limit preview length
        
        # Store if we found content
        if content["title"] or content["description"] or content["posts_preview"]:
            entry = CoachingKnowledgeEntry(
                source="Patreon - David and Megan Roche (Some Work, All Play)",
                methodology="Roche",
                source_type="web_article",
                text_chunk=(content["description"] or content["title"])[:2000],
                extracted_principles=json.dumps({
                    "title": content["title"],
                    "url": url,
                    "description": content["description"],
                    "posts_preview": content["posts_preview"],
                    "note": "Patreon content typically requires subscription - only public previews extracted"
                }),
                principle_type="article",
                metadata_json=json.dumps({
                    "url": url,
                    "title": content["title"],
                    "source_type": "patreon"
                })
            )
            db.add(entry)
            db.commit()
            
            print(f"✅ Stored public content preview")
            print(f"   Title: {content['title']}")
            print(f"   Description length: {len(content['description'])} chars")
            print(f"   Post previews: {len(content['posts_preview'])}")
        else:
            print("⚠️  No publicly available content found")
            print("   Patreon content requires subscription/login")
            print("   To extract full content, you would need to:")
            print("   1. Subscribe to the Patreon")
            print("   2. Export content manually")
            print("   3. Or provide exported content files")
        
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
        print("Usage: python crawl_patreon.py <patreon_url>")
        print("\nExample:")
        print("  python crawl_patreon.py https://www.patreon.com/c/swap/posts")
        print("\nNote: Patreon content typically requires authentication/subscription")
        sys.exit(1)
    
    url = sys.argv[1]
    extract_patreon_content(url)
    print("✅ Done!")


if __name__ == "__main__":
    main()

