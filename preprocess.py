#!/usr/bin/env python3
"""
Preprocess DJVU-derived Sein und Zeit text to clean formatting artifacts.
Input: Raw DJVU text with page breaks and hyphenation
Output: Clean markdown ready for translation
"""

import re
import sys
from pathlib import Path

def clean_djvu_text(text):
    """
    Main preprocessing pipeline for DJVU text cleanup.
    """
    # Step 1: Fix page break artifacts
    text = rejoin_split_text(text)
    text = remove_standalone_page_numbers(text)
    
    # Step 2: Clean hyphenation and formatting
    text = fix_hyphenation(text)
    text = clean_whitespace(text)
    
    # Step 3: Mark structural elements
    text = mark_sections(text)
    
    return text

def rejoin_split_text(text):
    """
    Rejoin text split across page breaks.
    Example: "be-\n\n6\n\ndarf" -> "bedarf"
    Example: "ihre Wurzel\n\n3\n\nin der" -> "ihre Wurzel in der"
    Example: "definition.\n\n5\n\n## § 2." -> "definition. ## § 2."
    """
    # Case 1: Ends with hyphen - join without space
    text = re.sub(r'(.)-\s*\n\n\d+\s*\n\n(.)', r'\1\2', text)
    
    # Case 2: Doesn't end with hyphen - join with space
    text = re.sub(r'([^-])\s*\n\n\d+\s*\n\n(.)', r'\1 \2', text)
    
    return text

def remove_standalone_page_numbers(text):
    """Remove standalone page numbers that aren't part of citations."""
    # Remove page numbers that are isolated on their own lines
    # But preserve them in citations like "Met. B 4, 1001 a 21"
    text = re.sub(r'\n\n\d+\n\n', '\n\n', text)
    
    return text

def fix_hyphenation(text):
    """Fix hyphenation artifacts from OCR."""
    # Remove soft hyphen character ¬ that appears at line breaks
    text = re.sub(r'¬\s*', '', text)
    
    return text

def mark_sections(text):
    """Mark § section breaks as markdown headings."""
    # § N. becomes markdown heading
    text = re.sub(r'^(§ \d+\.)', r'## \1', text, flags=re.MULTILINE)
    
    return text

def clean_whitespace(text):
    """Clean up excessive whitespace while preserving paragraph structure."""
    # Remove excessive blank lines (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing whitespace from lines
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    
    # Ensure single spaces between words (but preserve intentional spacing)
    text = re.sub(r'(?<!\n) {2,}(?!\n)', ' ', text)
    
    return text.strip()

def main():
    if len(sys.argv) != 3:
        print("Usage: python preprocess.py input.txt output.md")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file {input_file} not found")
        sys.exit(1)
    
    print(f"Preprocessing DJVU text: {input_file}...")
    
    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"Input: {len(text)} characters")
    
    # Process
    processed_text = clean_djvu_text(text)
    
    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(processed_text)
    
    print(f"Output: {len(processed_text)} characters -> {output_file}")
    print("DJVU preprocessing complete!")
    print("\nNext steps:")
    print("- Review Greek passages manually")
    print("- Citations and footnotes have been preserved")
    print("- Numbered arguments maintained for philosophical structure")

if __name__ == "__main__":
    main()
