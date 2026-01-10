#!/usr/bin/env python3
"""
Extract text from all PDF books on desktop.
Creates .txt files in books/raw/
"""

import os
from pathlib import Path

# Try pypdf first, fall back to PyPDF2
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

# Source and destination
DESKTOP = Path(r"C:\Users\mbsha\OneDrive\Desktop")
OUTPUT_DIR = Path(r"C:\Dev\StrideIQ\books\raw")

# Books to extract
BOOKS = [
    "_OceanofPDF.com_Advanced_Marathoning_4th_Edition_-_Pete_Pfitzinger.pdf",
    "_OceanofPDF.com_Daniels_Running_Formula_4th_Edition_-_Jack_Daniels.pdf",
    "_OceanofPDF.com_Fast_5K_25_Crucial_Keys_n_4_Training_Plans_-_Pete_Magill.pdf",
    "_OceanofPDF.com_8020_Running_-_Matt_Fitzgerald.pdf",
    "_OceanofPDF.com_Hansons_Half-Marathon_Method_-_Luke_Humphrey.pdf",
    "_OceanofPDF.com_How_to_Run_the_Perfect_Race_-_Matt_Fitzgerald.pdf",
    "_OceanofPDF.com_Run_Faster_from_the_5K_to_the_Marathon_-_Brad_Hudson.pdf",
    "_OceanofPDF.com_The_Science_of_Running_-_Steve_Magness.pdf",
]

# Clean names for output files
CLEAN_NAMES = {
    "_OceanofPDF.com_Advanced_Marathoning_4th_Edition_-_Pete_Pfitzinger.pdf": "pfitzinger_advanced_marathoning.txt",
    "_OceanofPDF.com_Daniels_Running_Formula_4th_Edition_-_Jack_Daniels.pdf": "daniels_running_formula.txt",
    "_OceanofPDF.com_Fast_5K_25_Crucial_Keys_n_4_Training_Plans_-_Pete_Magill.pdf": "magill_fast_5k.txt",
    "_OceanofPDF.com_8020_Running_-_Matt_Fitzgerald.pdf": "fitzgerald_80_20_running.txt",
    "_OceanofPDF.com_Hansons_Half-Marathon_Method_-_Luke_Humphrey.pdf": "hansons_half_marathon.txt",
    "_OceanofPDF.com_How_to_Run_the_Perfect_Race_-_Matt_Fitzgerald.pdf": "fitzgerald_perfect_race.txt",
    "_OceanofPDF.com_Run_Faster_from_the_5K_to_the_Marathon_-_Brad_Hudson.pdf": "hudson_run_faster.txt",
    "_OceanofPDF.com_The_Science_of_Running_-_Steve_Magness.pdf": "magness_science_of_running.txt",
}


def extract_pdf(pdf_path: Path, output_path: Path) -> int:
    """Extract text from PDF and save to txt file. Returns page count."""
    try:
        reader = PdfReader(str(pdf_path))
        text_content = []
        
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text:
                    text_content.append(f"\n--- PAGE {i+1} ---\n")
                    text_content.append(text)
            except Exception as e:
                text_content.append(f"\n--- PAGE {i+1} (extraction error: {e}) ---\n")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("".join(text_content))
        
        return len(reader.pages)
    
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0


def main():
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting {len(BOOKS)} books to {OUTPUT_DIR}\n")
    
    total_pages = 0
    successful = 0
    
    for book in BOOKS:
        pdf_path = DESKTOP / book
        output_name = CLEAN_NAMES.get(book, book.replace(".pdf", ".txt"))
        output_path = OUTPUT_DIR / output_name
        
        print(f"Processing: {output_name}")
        
        if not pdf_path.exists():
            print(f"  NOT FOUND: {pdf_path}")
            continue
        
        pages = extract_pdf(pdf_path, output_path)
        
        if pages > 0:
            size_kb = output_path.stat().st_size / 1024
            print(f"  OK: {pages} pages -> {size_kb:.1f} KB")
            total_pages += pages
            successful += 1
        else:
            print(f"  FAILED")
    
    print(f"\n{'='*50}")
    print(f"Extracted {successful}/{len(BOOKS)} books")
    print(f"Total pages: {total_pages}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
