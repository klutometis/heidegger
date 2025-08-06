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
    # Step 1: Remove footnotes FIRST (before rejoining splits them)
    text = remove_footnotes(text)
    
    # Step 2: Fix page break artifacts (includes removing standalone page numbers)
    text = rejoin_split_text(text)
    
    # Step 3: Clean hyphenation and formatting
    text = fix_hyphenation(text)
    text = clean_whitespace(text)
    
    # Step 4: Convert footnotes to endnotes (DISABLED - footnotes removed above)
    # text = convert_to_endnotes(text)
    
    # Step 5: Mark structural elements
    text = mark_sections(text)
    
    return text

def rejoin_split_text(text):
    """
    Join text split by page numbers while preserving paragraph boundaries.
    """
    # Step 1: Find text + whitespace + page number + whitespace + text patterns
    # and join them with a single space
    text = re.sub(r'(\w)\s*\n+\s*\d+\s*\n+\s*(\w)', r'\1 \2', text)
    
    # Step 2: Clean up any remaining standalone page numbers
    text = re.sub(r'\s+\d+\s+', ' ', text)
    
    return text

def remove_footnotes(text):
    """Remove footnote blocks entirely before processing page breaks."""
    # Single digit + space + actual content (footnotes only)
    # This avoids removing page numbers like "200 " with no content
    text = re.sub(r'\n\d [^\n]+', '', text)
    
    return text

def fix_hyphenation(text):
    """Fix hyphenation artifacts from OCR."""
    # Remove soft hyphen character ¬ that appears at line breaks
    text = re.sub(r'¬\s*', '', text)
    
    return text

# DISABLED: Endnotes conversion (may re-enable later)
# Need to process footnotes BEFORE rejoining split text to work properly
def convert_to_endnotes(text):
    """
    Convert inline footnotes to endnote references and collect endnotes at end.
    Example: "text. 1 Aristoteles..." -> "text.[^1]" + endnotes section
    
    CURRENTLY DISABLED - footnotes are simply removed for now.
    To re-enable: call this function BEFORE rejoin_split_text() in the pipeline.
    """
    footnotes = {}
    footnote_counter = 1
    
    # Step 1: Extract footnote definitions more carefully
    # Look for: double newline + digit + space + content + double newline
    footnote_pattern = r'\n\n(\d+) ([^\n].*?)(?=\n\n(?:\d+ |\w|$))'
    
    def extract_footnote(match):
        nonlocal footnote_counter
        original_num = match.group(1)
        citation_text = match.group(2).strip()
        
        # Store footnote with new sequential number
        footnotes[footnote_counter] = f"[^{footnote_counter}]: {citation_text}"
        
        # Create mapping for inline reference replacement
        footnotes[f"orig_{original_num}"] = footnote_counter
        
        footnote_counter += 1
        return "\n\n"  # Leave double newlines to preserve structure
    
    # Extract all footnote definitions
    text = re.sub(footnote_pattern, extract_footnote, text, flags=re.DOTALL)
    
    # Step 2: Replace inline references
    # Pattern: punctuation + space + digit + optional space/asterisk
    inline_pattern = r'([.!?:]) (\d+)( \*?)'
    
    def replace_inline_ref(match):
        punct = match.group(1)
        orig_num = match.group(2)
        
        # Look up the new sequential number
        new_num = footnotes.get(f"orig_{orig_num}")
        if new_num:
            return f"{punct}[^{new_num}]"
        else:
            # If footnote not found, leave as is
            return match.group(0)
    
    text = re.sub(inline_pattern, replace_inline_ref, text)
    
    # Step 3: Build endnotes section
    if footnotes:
        endnote_list = []
        for i in range(1, footnote_counter):
            if footnotes.get(i):
                endnote_list.append(footnotes[i])
        
        if endnote_list:
            endnotes_section = "\n\n## Endnotes\n\n" + "\n\n".join(endnote_list)
            text = text + endnotes_section
    
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
    print("- Footnotes removed for cleaner audiobook flow")
    print("- Numbered arguments maintained for philosophical structure")

if __name__ == "__main__":
    main()
