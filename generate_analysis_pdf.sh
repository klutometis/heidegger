#!/bin/bash

# Generate beautiful PDF from the AI translation analysis
# Creates "Four Minds on Being: AI Comparative Translation Analysis"

set -e

INPUT_FILE="final_analysis_paragraph_77.md"
OUTPUT_FILE="four_minds_on_being.pdf"

# Check if pandoc is available
if ! command -v pandoc &> /dev/null; then
    echo "Error: pandoc is required but not installed."
    echo "Install with: brew install pandoc (macOS) or apt-get install pandoc (Linux)"
    exit 1
fi

echo "Generating PDF analysis: $OUTPUT_FILE"

pandoc "$INPUT_FILE" \
    -o "$OUTPUT_FILE" \
    --pdf-engine=xelatex \
    --toc \
    --toc-depth=2 \
    --number-sections \
    --metadata title="Four Minds on Being" \
    --metadata subtitle="AI Comparative Analysis of Heidegger Translation" \
    --metadata author="Multi-Model AI Translation System" \
    --metadata date="$(date '+%B %Y')" \
    --variable papersize=letter \
    --variable fontsize=11pt \
    --variable geometry=margin=1in

echo "✓ Generated: $OUTPUT_FILE"
echo "This PDF showcases transparent AI reasoning in philosophical translation."
