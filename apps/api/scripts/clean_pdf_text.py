#!/usr/bin/env python3
"""
Clean PDF text that has character duplication issues
"""
import sys
import re

def clean_duplicated_chars(text: str) -> str:
    """Remove character duplication common in PDF extraction."""
    # Pattern: repeated characters like "BBBBaaaassssiiiicccc" -> "Basic"
    # Look for sequences of 3+ repeated chars
    def deduplicate(match):
        chars = match.group(0)
        # Count occurrences of each char
        char_counts = {}
        for c in chars:
            char_counts[c] = char_counts.get(c, 0) + 1
        
        # Find the most common char (should be the actual char)
        if char_counts:
            most_common = max(char_counts.items(), key=lambda x: x[1])[0]
            return most_common
        return chars[0] if chars else ""
    
    # Replace sequences of 3+ repeated characters with single char
    text = re.sub(r'(.)\1{2,}', deduplicate, text)
    
    # Also handle cases like "TTTTTrrrraaaaiiiinnnniiiinnnngggg" -> "Training"
    # Split into groups and deduplicate
    words = text.split()
    cleaned_words = []
    for word in words:
        # Remove repeated chars within word
        cleaned = re.sub(r'(.)\1+', r'\1', word)
        cleaned_words.append(cleaned)
    
    return ' '.join(cleaned_words)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python clean_pdf_text.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    cleaned = clean_duplicated_chars(text)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    
    print(f"✅ Cleaned text: {len(text)} -> {len(cleaned)} chars")

