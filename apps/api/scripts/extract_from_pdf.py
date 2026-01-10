#!/usr/bin/env python3
"""
PDF Extraction Script

Extracts text from PDF files and processes them for knowledge extraction.
"""
import sys
import os
from pathlib import Path

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


def extract_text_from_pdf_pypdf2(pdf_path: str) -> str:
    """Extract text using PyPDF2."""
    text_content = []
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_content.append(text)
                except Exception as e:
                    print(f"Warning: Could not extract page {page_num + 1}: {e}")
                    continue
        
        return '\n\n'.join(text_content)
    except Exception as e:
        print(f"Error with PyPDF2: {e}")
        return ""


def extract_text_from_pdf_pdfplumber(pdf_path: str) -> str:
    """Extract text using pdfplumber (better quality)."""
    text_content = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                except Exception as e:
                    print(f"Warning: Could not extract page {page_num + 1}: {e}")
                    continue
        
        return '\n\n'.join(text_content)
    except Exception as e:
        print(f"Error with pdfplumber: {e}")
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file.
    
    Tries pdfplumber first (better), falls back to PyPDF2.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text content
    """
    # Try pdfplumber first (better quality)
    if PDFPLUMBER_AVAILABLE:
        print("Using pdfplumber for extraction...")
        text = extract_text_from_pdf_pdfplumber(pdf_path)
        if text:
            return text
    
    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
        print("Using PyPDF2 for extraction...")
        text = extract_text_from_pdf_pypdf2(pdf_path)
        if text:
            return text
    
    print("❌ No PDF extraction library available. Install pdfplumber or PyPDF2:")
    print("  pip install pdfplumber  # Recommended")
    print("  pip install PyPDF2      # Alternative")
    return ""


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 3:
        print("Usage: python extract_from_pdf.py <pdf_file> <output_text_file>")
        print("\nExample:")
        print("  python extract_from_pdf.py faster_road_racing.pdf faster_road_racing_text.txt")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print(f"Extracting text from {pdf_file}...")
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        print("❌ No text extracted. File may be encrypted, scanned (needs OCR), or invalid format.")
        sys.exit(1)
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"✅ Extracted {len(text)} characters to {output_file}")
    print(f"✅ Ready for knowledge extraction!")


if __name__ == "__main__":
    main()

