#!/usr/bin/env python3
"""
Store Text Chunks Script

Chunks text from extracted books and stores them in the knowledge base
for later AI extraction. This allows us to store content without needing
AI API keys immediately.
"""
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry
from services.knowledge_extraction_ai import chunk_text_for_extraction


def store_text_chunks(text_file: str, source: str, methodology: str, source_type: str = "book"):
    """
    Chunk text and store in knowledge base.
    
    Args:
        text_file: Path to text file
        source: Source identifier (book title, URL, etc.)
        methodology: Coaching methodology (e.g., "Daniels", "Pfitzinger")
        source_type: Type of source ("book", "article", "research")
    """
    db = get_db_sync()
    try:
        # Read text file
        print(f"Reading {text_file}...")
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        print(f"Text length: {len(text)} characters")
        
        # Chunk text (10KB chunks for AI processing)
        print("Chunking text...")
        chunks = chunk_text_for_extraction(text, chunk_size=10000)
        print(f"Created {len(chunks)} chunks")
        
        # Store each chunk
        stored_count = 0
        for i, chunk in enumerate(chunks):
            # Remove NUL characters (PostgreSQL doesn't allow them)
            chunk = chunk.replace('\x00', '')
            
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type=source_type,
                text_chunk=chunk,
                extracted_principles=None,  # Will be filled by AI extraction later
                principle_type="raw_text_chunk",
                metadata_json=json.dumps({
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk)
                })
            )
            db.add(entry)
            stored_count += 1
            
            if stored_count % 10 == 0:
                print(f"  Stored {stored_count}/{len(chunks)} chunks...")
                db.commit()
        
        db.commit()
        print(f"✅ Stored {stored_count} chunks in knowledge base")
        print(f"✅ Ready for AI extraction when API keys are available")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 4:
        print("Usage: python store_text_chunks.py <text_file> <source> <methodology> [source_type]")
        print("\nExample:")
        print("  python store_text_chunks.py /books/daniels.txt 'Daniels Running Formula' 'Daniels' book")
        sys.exit(1)
    
    text_file = sys.argv[1]
    source = sys.argv[2]
    methodology = sys.argv[3]
    source_type = sys.argv[4] if len(sys.argv) > 4 else "book"
    
    store_text_chunks(text_file, source, methodology, source_type)
    print("✅ Done!")


if __name__ == "__main__":
    main()

