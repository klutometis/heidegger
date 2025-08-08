from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import re
from translator import TranslationContext

@dataclass
class ParsedParagraph:
    number: int
    german_text: str = ""
    english_translation: Optional[str] = None
    thinking: Optional[str] = None
    key_terms: List[str] = None
    uncertainties: List[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.key_terms is None:
            self.key_terms = []
        if self.uncertainties is None:
            self.uncertainties = []
    
    @property
    def is_error(self) -> bool:
        return self.error_message is not None
    
    @property
    def is_complete(self) -> bool:
        return self.english_translation is not None and not self.is_error

class TranslationParser:
    """Parse existing translation markdown files and extract structured data."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = file_path.read_text(encoding='utf-8')
        self._paragraphs: Optional[List[ParsedParagraph]] = None
    
    def parse_paragraphs(self) -> List[ParsedParagraph]:
        """Extract all paragraphs from the markdown file."""
        if self._paragraphs is not None:
            return self._paragraphs
            
        paragraphs = []
        
        # Split by paragraph headers: ## Paragraph N or ## Paragraph N - ERROR
        paragraph_pattern = r'^## Paragraph (\d+)(?:\s*-\s*ERROR)?$'
        sections = re.split(paragraph_pattern, self.content, flags=re.MULTILINE)
        
        # sections[0] is content before first paragraph (usually header/metadata)
        # sections[1] is first paragraph number, sections[2] is first paragraph content, etc.
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                para_num = int(sections[i])
                para_content = sections[i + 1].strip()
                
                # Check if this was an error paragraph by looking at the original header
                header_match = re.search(rf'^## Paragraph {para_num}(\s*-\s*ERROR)?$', 
                                       self.content, re.MULTILINE)
                is_error = header_match and header_match.group(1) is not None
                
                if is_error:
                    paragraph = self._parse_error_paragraph(para_num, para_content)
                else:
                    paragraph = self._parse_successful_paragraph(para_num, para_content)
                
                paragraphs.append(paragraph)
        
        self._paragraphs = paragraphs
        return paragraphs
    
    def _parse_successful_paragraph(self, para_num: int, content: str) -> ParsedParagraph:
        """Parse a successfully translated paragraph."""
        german = self._extract_section(content, r'\*\*German:\*\*(.*?)(?=\*\*English:|\*\*Error:|\Z)', multiline=True)
        english = self._extract_section(content, r'\*\*English:\*\*(.*?)(?=\*\*Translator\'s Notes:|\*\*Error:|\Z)', multiline=True)
        thinking = self._extract_section(content, r'\*\*Translator\'s Notes:\*\*(.*?)(?=\*\*Key Terms:|\*\*Error:|\Z)', multiline=True)
        
        # Extract key terms (comma-separated)
        key_terms_raw = self._extract_section(content, r'\*\*Key Terms:\*\*(.*?)(?=\*\*Translation Uncertainties:|\*\*Error:|\Z)')
        key_terms = []
        if key_terms_raw:
            key_terms = [term.strip() for term in key_terms_raw.split(',') if term.strip()]
        
        # Extract uncertainties (can be bullet points or paragraphs)
        uncertainties_raw = self._extract_section(content, r'\*\*Translation Uncertainties:\*\*(.*?)(?=\n##|\Z)', multiline=True)
        uncertainties = self._parse_uncertainties_list(uncertainties_raw)
        
        return ParsedParagraph(
            number=para_num,
            german_text=german.strip() if german else "",
            english_translation=english.strip() if english else None,
            thinking=thinking.strip() if thinking else None,
            key_terms=key_terms,
            uncertainties=uncertainties
        )
    
    def _parse_error_paragraph(self, para_num: int, content: str) -> ParsedParagraph:
        """Parse an error paragraph."""
        german = self._extract_section(content, r'\*\*German:\*\*(.*?)(?=\*\*Error:|\Z)', multiline=True)
        error = self._extract_section(content, r'\*\*Error:\*\*(.*?)(?=\n##|\Z)', multiline=True)
        
        return ParsedParagraph(
            number=para_num,
            german_text=german.strip() if german else "",
            error_message=error.strip() if error else "Unknown error"
        )
    
    def _extract_section(self, text: str, pattern: str, multiline: bool = False) -> Optional[str]:
        """Extract a section using regex pattern."""
        flags = re.DOTALL if multiline else 0
        match = re.search(pattern, text, flags)
        return match.group(1) if match else None
    
    def _parse_uncertainties_list(self, uncertainties_text: str) -> List[str]:
        """Parse uncertainties section into list of individual uncertainties."""
        if not uncertainties_text:
            return []
        
        uncertainties = []
        
        # Check if it's bullet point format
        if re.search(r'^\s*[-*]\s+', uncertainties_text.strip(), re.MULTILINE):
            # Extract bullet points
            bullets = re.findall(r'^\s*[-*]\s+(.+)$', uncertainties_text, re.MULTILINE)
            uncertainties.extend([bullet.strip() for bullet in bullets])
        else:
            # Treat as single uncertainty or paragraph
            cleaned = uncertainties_text.strip()
            if cleaned:
                uncertainties.append(cleaned)
        
        return uncertainties
    
    def find_errors(self) -> List[int]:
        """Return paragraph numbers that have errors."""
        paragraphs = self.parse_paragraphs()
        return [p.number for p in paragraphs if p.is_error]
    
    def find_successful(self) -> List[int]:
        """Return paragraph numbers that were successfully translated."""
        paragraphs = self.parse_paragraphs()
        return [p.number for p in paragraphs if p.is_complete]
    
    def get_paragraph(self, para_num: int) -> Optional[ParsedParagraph]:
        """Get a specific paragraph by number."""
        paragraphs = self.parse_paragraphs()
        for p in paragraphs:
            if p.number == para_num:
                return p
        return None
    
    def get_context_for_repair(self, para_num: int, context_size: int = 3) -> TranslationContext:
        """Build translation context for repairing a failed paragraph."""
        paragraphs = self.parse_paragraphs()
        target_para = self.get_paragraph(para_num)
        
        if not target_para or not target_para.is_error:
            raise ValueError(f"Paragraph {para_num} is not an error paragraph")
        
        # Collect previous successful paragraphs for context
        prev_german = []
        prev_english = []
        
        for p in paragraphs:
            if p.number < para_num and p.is_complete:
                prev_german.append(p.german_text)
                prev_english.append(p.english_translation)
        
        # Take the last N paragraphs as context
        prev_german = prev_german[-context_size:]
        prev_english = prev_english[-context_size:]
        
        return TranslationContext(
            current_german=target_para.german_text,
            prev_german_paragraphs=prev_german,
            prev_english_paragraphs=prev_english,
            context_window_size=context_size
        )
    
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the translation file."""
        paragraphs = self.parse_paragraphs()
        total = len(paragraphs)
        errors = len([p for p in paragraphs if p.is_error])
        complete = len([p for p in paragraphs if p.is_complete])
        
        return {
            'total_paragraphs': total,
            'error_paragraphs': errors,
            'complete_paragraphs': complete,
            'success_rate': round(complete / total * 100, 1) if total > 0 else 0
        }

def main():
    """Test the parser on a translation file."""
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python translation_parser.py <translation_file.md>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    parser = TranslationParser(file_path)
    
    print(f"Parsing {file_path}")
    stats = parser.get_statistics()
    print(f"Statistics: {stats}")
    
    errors = parser.find_errors()
    if errors:
        print(f"Found {len(errors)} error paragraphs: {errors[:10]}{'...' if len(errors) > 10 else ''}")
        
        # Show first error as example
        first_error = parser.get_paragraph(errors[0])
        print(f"\nFirst error (Paragraph {first_error.number}):")
        print(f"German: {first_error.german_text[:100]}...")
        print(f"Error: {first_error.error_message}")
    else:
        print("No errors found!")

if __name__ == "__main__":
    main()
