from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from pathlib import Path
from typing import Optional, Dict, Any

class TranslationPromptBuilder:
    """Builds LangChain prompts from configuration files."""
    
    def __init__(self, config_dir: Path = Path(".")):
        self.config_dir = config_dir
        self.style_content = self._load_file("STYLE.md")
        self.conventions_content = self._load_file("CONVENTIONS.md") 
        self.glossary_content = self._load_file("GLOSSARY.md")
    
    def _load_file(self, filename: str) -> str:
        """Load config file, return empty string if not found."""
        file_path = self.config_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return ""
    
    def build_translation_prompt(self) -> ChatPromptTemplate:
        """Create the main translation prompt template."""
        
        system_template = """You are translating Martin Heidegger's "Being and Time" from German to English.

# Translation Style Guidelines
{style_guidelines}

# Term Conventions
{conventions}

# Glossary & Conceptual Notes
{glossary}

# Instructions
- Provide your English translation in the 'translation' field
- Use the 'thinking' field to explain your reasoning about:
  * Key philosophical terms and why you chose specific translations
  * Challenges in capturing Heidegger's phenomenological concepts
  * How context influenced your translation choices
  * Connections to broader themes in Being and Time
  * Any interpretive decisions you made
- Note important philosophical terms in 'key_terms'
- Flag uncertain translation choices in 'uncertainties'
- Think through the philosophical implications as you translate
- Preserve the phenomenological rhythm and argumentative structure"""

        human_template = """# Previous German Context
{prev_german_context}

# Previous English Translation
{prev_english_context}

# Current German Paragraph to Translate
{current_german}

Please provide your English translation:"""

        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
    
    def build_context_dict(self) -> Dict[str, str]:
        """Return the loaded configuration as a dict for prompt formatting."""
        return {
            "style_guidelines": self.style_content,
            "conventions": self.conventions_content, 
            "glossary": self.glossary_content
        }
