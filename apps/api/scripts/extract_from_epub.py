#!/usr/bin/env python3
"""
EPUB Extraction Script

Extracts text from EPUB files and processes them for knowledge extraction.
"""
import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import re

def extract_text_from_epub(epub_path: str) -> str:
    """
    Extract text content from EPUB file.
    
    Args:
        epub_path: Path to EPUB file
        
    Returns:
        Extracted text content
    """
    text_content = []
    
    try:
        # EPUB files are ZIP archives
        with zipfile.ZipFile(epub_path, 'r') as epub:
            # Get list of files
            file_list = epub.namelist()
            
            # Find content files (usually .html, .xhtml, or .htm)
            content_files = [f for f in file_list if f.endswith(('.html', '.xhtml', '.htm'))]
            
            # Also check for .opf file to find content structure
            opf_files = [f for f in file_list if f.endswith('.opf')]
            
            # Extract text from HTML/XHTML files
            for content_file in sorted(content_files):
                try:
                    content = epub.read(content_file).decode('utf-8', errors='ignore')
                    
                    # Parse HTML and extract text
                    # Simple approach: remove HTML tags
                    text = re.sub(r'<[^>]+>', '', content)
                    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                    
                    if text.strip():
                        text_content.append(text.strip())
                except Exception as e:
                    print(f"Warning: Could not extract from {content_file}: {e}")
                    continue
        
        return '\n\n'.join(text_content)
        
    except Exception as e:
        print(f"Error extracting EPUB: {e}")
        return ""


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 3:
        print("Usage: python extract_from_epub.py <epub_file> <output_text_file>")
        print("\nExample:")
        print("  python extract_from_epub.py daniels_running_formula.epub daniels_text.txt")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print(f"Extracting text from {epub_file}...")
    text = extract_text_from_epub(epub_file)
    
    if not text:
        print("❌ No text extracted. File may be encrypted or invalid format.")
        sys.exit(1)
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"✅ Extracted {len(text)} characters to {output_file}")
    print(f"✅ Ready for knowledge extraction!")


if __name__ == "__main__":
    main()

