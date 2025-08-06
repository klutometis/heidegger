from pathlib import Path
from typing import List, Iterator
import re

class TextChunker:
    """Extracts paragraphs from cleaned Heidegger text."""
    
    def __init__(self, text_file: Path):
        self.text_file = text_file
        self.text = self._load_text()
    
    def _load_text(self) -> str:
        """Load the cleaned text file."""
        return self.text_file.read_text(encoding='utf-8')
    
    def extract_paragraphs(self) -> List[str]:
        """Split text into paragraphs, preserving section markers."""
        # Split on double newlines (paragraph boundaries)
        raw_paragraphs = self.text.split('\n\n')
        
        # Clean and filter paragraphs
        paragraphs = []
        for para in raw_paragraphs:
            para = para.strip()
            if para and len(para) > 10:  # Skip very short fragments
                paragraphs.append(para)
        
        return paragraphs
    
    def extract_sections(self) -> List[tuple]:
        """Extract paragraphs grouped by sections (§ markers)."""
        paragraphs = self.extract_paragraphs()
        sections = []
        current_section = None
        current_paras = []
        
        for para in paragraphs:
            # Check if this is a section header (starts with §)
            if para.startswith('# §'):
                # Save previous section if exists
                if current_section and current_paras:
                    sections.append((current_section, current_paras))
                
                # Start new section
                current_section = para
                current_paras = []
            else:
                current_paras.append(para)
        
        # Add final section
        if current_section and current_paras:
            sections.append((current_section, current_paras))
        
        return sections
    
    def get_paragraph_with_context(self, index: int, context_size: int = 2) -> tuple:
        """Get a paragraph with surrounding context for translation."""
        paragraphs = self.extract_paragraphs()
        
        if index >= len(paragraphs):
            raise IndexError(f"Paragraph index {index} out of range")
        
        current = paragraphs[index]
        
        # Get previous context
        start_idx = max(0, index - context_size)
        prev_context = paragraphs[start_idx:index]
        
        return current, prev_context
    
    def chunk_iterator(self, context_size: int = 2) -> Iterator[tuple]:
        """Iterate through paragraphs with context."""
        paragraphs = self.extract_paragraphs()
        
        for i, para in enumerate(paragraphs):
            start_idx = max(0, i - context_size)
            prev_context = paragraphs[start_idx:i]
            yield i, para, prev_context
