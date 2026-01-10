#!/usr/bin/env python3
"""
Process Patreon JSON export

Takes a JSON file exported from Patreon and stores it in the knowledge base.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def process_patreon_json(json_file: str):
    """Process Patreon JSON export and store in knowledge base."""
    db = get_db_sync()
    try:
        print(f"Reading {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        source = data.get('source', 'Patreon - David and Megan Roche')
        methodology = data.get('methodology', 'Roche')
        posts = data.get('posts', [])
        
        print(f"Found {len(posts)} posts to process")
        
        stored_count = 0
        for i, post in enumerate(posts, 1):
            title = post.get('title', f'Post {i}')
            content = post.get('content', '')
            url = post.get('url', '')
            date = post.get('date', '')
            
            if not content or len(content) < 50:
                print(f"  ⚠️  Skipping post {i} - content too short")
                continue
            
            print(f"  [{i}/{len(posts)}] Storing: {title[:60]}...")
            
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type="web_article",
                text_chunk=content[:2000],  # Preview
                extracted_principles=json.dumps({
                    "title": title,
                    "url": url,
                    "date": date,
                    "full_text": content
                }),
                principle_type="article",
                metadata_json=json.dumps({
                    "url": url,
                    "title": title,
                    "date": date,
                    "source_type": "patreon"
                })
            )
            db.add(entry)
            stored_count += 1
            
            if stored_count % 10 == 0:
                db.commit()
                print(f"    💾 Committed {stored_count} posts")
        
        db.commit()
        print(f"\n✅ Stored {stored_count} posts in knowledge base")
        
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
        print("Usage: python process_patreon_json.py <json_file>")
        print("\nExample:")
        print("  python process_patreon_json.py patreon_roche.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    process_patreon_json(json_file)
    print("✅ Done!")


if __name__ == "__main__":
    main()

