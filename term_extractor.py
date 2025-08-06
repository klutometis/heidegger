#!/usr/bin/env python3
"""
Term extraction system for Heidegger's Being and Time.
Hybrid approach: primitive text analysis + LLM philosophical analysis.
"""

import re
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from chunker import TextChunker
from translator import Translator
from nltk.stem.snowball import GermanStemmer

@dataclass
class PhilosophicalTerm:
    """Analysis of a philosophical term with morphological variants."""
    canonical_form: str  # Most frequent surface form
    stem: str
    total_frequency: int
    morphological_forms: Dict[str, int]  # form -> frequency
    contexts: List[str]
    philosophical_importance: Optional[int] = None  # 1-10 scale
    is_core_concept: Optional[bool] = None
    translation_challenges: Optional[str] = None
    suggested_renderings: List[str] = None
    contextual_variations: Optional[str] = None
    
    def __post_init__(self):
        if self.suggested_renderings is None:
            self.suggested_renderings = []

class TermExtractor:
    """Extracts and analyzes philosophical terms from Heidegger's text."""
    
    def __init__(self, text_file: Path, model_name: str = "gpt-4o"):
        self.text_file = text_file
        self.chunker = TextChunker(text_file)
        self.text = self.chunker.text
        self.translator = Translator(model_name)  # Reuse for LLM analysis
        self.logger = logging.getLogger(__name__)
        
        # Initialize German stemmer
        self.stemmer = GermanStemmer()
        
        # Updated patterns - simpler and more targeted
        self.compound_patterns = [
            r'\b[Ii]n-der-[Ww]elt-sein\b',  # Exact compound matches first
            r'\b[Ss]ein-zum-[Tt]ode?\b',    # Being-toward-death
            r'\b[A-Z][a-z]+(?:-[a-z]+)+\b', # General hyphenated compounds  
            r'\b[a-z]+(?:heit|keit|ung|schaft|tum|nis)\b', # Philosophical suffixes
            r'\b[DdSsZzWwEeGgAaBbFf][a-zäöüß]{3,}\b', # German philosophical terms
        ]
        
        # Common non-philosophical words to filter out
        self.stopwords = {
            'der', 'die', 'das', 'und', 'oder', 'aber', 'auch', 'noch', 'nur', 
            'wie', 'was', 'wenn', 'dann', 'sich', 'auf', 'aus', 'bei', 'mit',
            'nach', 'von', 'vor', 'über', 'unter', 'durch', 'für', 'gegen',
            'ohne', 'um', 'bis', 'seit', 'während', 'wegen', 'trotz',
            'diese', 'dieses', 'dieser', 'dem', 'den', 'allem', 'andere', 'anderen',
            # Functional/connective words
            'damit', 'daher', 'darin', 'dabei', 'dafür', 'dagegen', 'danach', 
            'davon', 'dazu', 'demnach', 'deshalb', 'deswegen', 'hierbei', 
            'hierzu', 'indem', 'insofern', 'somit', 'wobei', 'wodurch', 'zudem'
        }
    
    def extract_and_cluster_terms(self) -> Dict[str, PhilosophicalTerm]:
        """Extract terms and cluster by stem."""
        self.logger.info("Extracting terms and clustering by stem...")
        
        # Step 1: Extract raw terms
        raw_term_contexts = self._extract_raw_terms()
        
        # Step 2: Cluster by stem  
        stem_clusters = self._cluster_by_stem(raw_term_contexts)
        
        # Step 3: Create PhilosophicalTerm objects
        philosophical_terms = {}
        for stem, cluster_data in stem_clusters.items():
            if cluster_data['total_frequency'] >= 3:  # Filter low-frequency
                philosophical_terms[stem] = self._create_philosophical_term(stem, cluster_data)
        
        self.logger.info(f"Clustered into {len(philosophical_terms)} stem groups")
        return philosophical_terms

    def _extract_raw_terms(self) -> Dict[str, List[str]]:
        """Extract raw terms with contexts."""
        term_contexts = defaultdict(list)
        paragraphs = self.text.split('\n\n')
        
        for para in paragraphs:
            if len(para) < 20:
                continue
                
            # Apply patterns in order of specificity
            matched_positions = set()
            
            for pattern in self.compound_patterns:
                for match in re.finditer(pattern, para):
                    start, end = match.span()
                    
                    # Skip overlapping matches
                    if any(pos in matched_positions for pos in range(start, end)):
                        continue
                        
                    term = match.group().lower()
                    
                    if self._is_philosophical_term(term):
                        matched_positions.update(range(start, end))
                        
                        # Context window
                        context_start = max(0, start - 100)  
                        context_end = min(len(para), end + 100)
                        context = para[context_start:context_end].strip()
                        
                        term_contexts[term].append(context)
        
        return dict(term_contexts)

    def _cluster_by_stem(self, raw_terms: Dict[str, List[str]]) -> Dict[str, Dict]:
        """Cluster terms by German stem."""
        stem_data = defaultdict(lambda: {
            'forms': Counter(),
            'contexts': [],
            'total_frequency': 0
        })
        
        for term, contexts in raw_terms.items():
            stem = self.stemmer.stem(term)
            frequency = len(contexts)
            
            stem_data[stem]['forms'][term] += frequency
            stem_data[stem]['contexts'].extend(contexts)
            stem_data[stem]['total_frequency'] += frequency
        
        return dict(stem_data)

    def _create_philosophical_term(self, stem: str, cluster_data: Dict) -> PhilosophicalTerm:
        """Create PhilosophicalTerm from cluster data."""
        # Most frequent form becomes canonical
        canonical_form = cluster_data['forms'].most_common(1)[0][0]
        
        return PhilosophicalTerm(
            canonical_form=canonical_form,
            stem=stem,
            total_frequency=cluster_data['total_frequency'],
            morphological_forms=dict(cluster_data['forms']),
            contexts=cluster_data['contexts'][:8]  # Sample contexts
        )

    def _is_philosophical_term(self, term: str) -> bool:
        """Filter for philosophical terms."""
        # Stopwords and noise
        if term in self.stopwords:
            return False
            
        if len(term) < 4:
            return False
            
        # Philosophical indicators
        philosophical_markers = [
            'sein', 'da', 'zeit', 'welt', 'sorge', 'angst', 'wahrheit',
            'heit', 'keit', 'ung', 'schaft', 'tum', 'nis'
        ]
        
        return any(marker in term for marker in philosophical_markers)
    
    def prioritize_terms(self, philosophical_terms: Dict[str, PhilosophicalTerm], top_n: int = 100) -> List[PhilosophicalTerm]:
        """Prioritize terms for LLM analysis based on frequency and patterns."""
        
        def priority_score(term: PhilosophicalTerm) -> float:
            score = term.total_frequency  # Base frequency
            
            # Boost for capitalized canonical forms (likely important concepts)
            if any(c.isupper() for c in term.canonical_form):
                score *= 1.5
            
            # Boost for compound words with philosophical suffixes
            if any(term.canonical_form.endswith(suffix) for suffix in ['heit', 'keit', 'ung', 'schaft']):
                score *= 2.0
            
            # Boost for terms containing 'sein' or 'da'
            if 'sein' in term.canonical_form or 'da' in term.canonical_form:
                score *= 1.8
            
            # Boost for hyphenated terms (often technical)
            if '-' in term.canonical_form:
                score *= 1.3
            
            return score
        
        # Calculate priority scores
        term_scores = [
            (term, priority_score(term))
            for term in philosophical_terms.values()
        ]
        
        # Sort by score and take top N
        term_scores.sort(key=lambda x: x[1], reverse=True)
        top_terms = [term for term, score in term_scores[:top_n]]
        
        self.logger.info(f"Prioritized top {len(top_terms)} terms for LLM analysis")
        return top_terms
    
    def analyze_term_philosophically(self, term: PhilosophicalTerm) -> PhilosophicalTerm:
        """Phase 2: Use LLM to analyze philosophical significance of a term."""
        
        # Show morphological forms in prompt
        forms_info = ", ".join([f"{form} ({freq}x)" for form, freq in term.morphological_forms.items()])
        
        prompt = f"""Analyze the philosophical term "{term.canonical_form}" in Heidegger's "Being and Time".

This term appears {term.total_frequency} times total in these forms: {forms_info}
Stem: {term.stem}

Context examples:
{chr(10).join(f"- {ctx[:200]}..." for ctx in term.contexts)}

Provide analysis in this format:
- Philosophical importance (1-10 scale, where 10 = fundamental Heideggerian concept)
- Core concept (yes/no - is this a central concept in Being and Time?)
- Translation challenges (what makes this term difficult to translate?)
- Suggested renderings (2-3 possible English translations)
- Contextual variations (does the meaning shift across different contexts?)

Be concise and focus on translation-relevant insights."""

        try:
            # For now, let's use a simpler approach - direct model call
            from langchain_core.messages import HumanMessage
            response = self.translator.model.invoke([HumanMessage(content=prompt)])
            analysis_text = response.content
            
            # Parse the response (simple regex parsing)
            importance_match = re.search(r'importance.*?(\d+)', analysis_text.lower())
            importance = int(importance_match.group(1)) if importance_match else 5
            
            core_concept = 'yes' in analysis_text.lower() and 'core concept' in analysis_text.lower()
            
            # Extract other fields with simple pattern matching
            challenges = self._extract_section(analysis_text, "translation challenges")
            renderings = self._extract_renderings(analysis_text)
            variations = self._extract_section(analysis_text, "contextual variations")
            
            # Update the term with analysis
            term.philosophical_importance = importance
            term.is_core_concept = core_concept
            term.translation_challenges = challenges
            term.suggested_renderings = renderings
            term.contextual_variations = variations
            
            return term
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze term '{term.canonical_form}': {e}")
            return term
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from LLM response."""
        pattern = rf"{section_name}[:\-\s]*(.+?)(?:\n-|\n[A-Z]|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""
    
    def _extract_renderings(self, text: str) -> List[str]:
        """Extract suggested renderings from LLM response."""
        section = self._extract_section(text, "suggested renderings")
        if not section:
            return []
        
        # Split on commas, semicolons, or line breaks
        renderings = re.split(r'[,;\n]+', section)
        return [r.strip(' -"\'') for r in renderings if r.strip()]
    
    def analyze_terms_batch(self, priority_terms: List[PhilosophicalTerm]) -> List[PhilosophicalTerm]:
        """Analyze multiple terms using LLM."""
        self.logger.info(f"Analyzing {len(priority_terms)} terms with LLM...")
        
        analyzed_terms = []
        for i, term in enumerate(priority_terms):
            self.logger.info(f"Analyzing term {i+1}/{len(priority_terms)}: {term.canonical_form} (stem: {term.stem})")
            
            analyzed = self.analyze_term_philosophically(term)
            analyzed_terms.append(analyzed)
        
        return analyzed_terms
    
    def generate_glossary(self, analyzed_terms: List[PhilosophicalTerm]) -> str:
        """Generate GLOSSARY.md content from analyzed terms."""
        
        # Sort by philosophical importance
        sorted_terms = sorted(
            [t for t in analyzed_terms if t.philosophical_importance and t.philosophical_importance >= 6],
            key=lambda x: x.philosophical_importance or 0,
            reverse=True
        )
        
        glossary = "# Philosophical Glossary & Conceptual Notes\n\n"
        glossary += "*Auto-generated from stem analysis - review and refine as needed*\n\n"
        glossary += "## Core Concepts\n\n"
        
        for term in sorted_terms:
            if term.is_core_concept:
                glossary += f"### {term.canonical_form.title()}\n"
                
                # Show morphological variants
                if len(term.morphological_forms) > 1:
                    forms_list = [f"{form} ({freq}x)" for form, freq in term.morphological_forms.items()]
                    glossary += f"- **Forms**: {', '.join(forms_list)}\n"
                
                if term.suggested_renderings:
                    glossary += f"- **Possible renderings**: {', '.join(term.suggested_renderings)}\n"
                if term.translation_challenges:
                    glossary += f"- **Translation challenges**: {term.translation_challenges}\n"
                if term.contextual_variations:
                    glossary += f"- **Context sensitivity**: {term.contextual_variations}\n"
                glossary += f"- **Total frequency**: {term.total_frequency} occurrences\n"
                glossary += f"- **Stem**: {term.stem}\n"
                glossary += "\n"
        
        # Add secondary terms
        secondary_terms = [t for t in sorted_terms if not t.is_core_concept]
        if secondary_terms:
            glossary += "## Secondary Terms\n\n"
            for term in secondary_terms[:20]:  # Top 20 secondary terms
                glossary += f"- **{term.canonical_form}**: "
                if term.suggested_renderings:
                    glossary += f"{', '.join(term.suggested_renderings[:2])}"
                glossary += f" ({term.total_frequency}x)\n"
        
        return glossary
    
    def generate_conventions(self, analyzed_terms: List[PhilosophicalTerm]) -> str:
        """Generate CONVENTIONS.md content from analyzed terms."""
        
        # Focus on high-frequency core concepts for conventions
        core_terms = [
            t for t in analyzed_terms 
            if t.is_core_concept and t.total_frequency >= 10
        ]
        core_terms.sort(key=lambda x: x.total_frequency, reverse=True)
        
        conventions = "# Term Conventions\n\n"
        conventions += "*Auto-generated from stem analysis - review and refine as needed*\n\n"
        conventions += "## Core Existential Terms\n"
        
        for term in core_terms[:15]:  # Top 15 most frequent core terms
            if term.suggested_renderings:
                primary = term.suggested_renderings[0]
                conventions += f"- **{term.canonical_form}**: {primary}"
                
                # Show morphological variants  
                if len(term.morphological_forms) > 1:
                    variants = [f"{form} ({freq}x)" for form, freq in term.morphological_forms.items() 
                               if form != term.canonical_form]
                    if variants:
                        conventions += f" [variants: {', '.join(variants)}]"
                
                if len(term.suggested_renderings) > 1:
                    conventions += f" (alt: {', '.join(term.suggested_renderings[1:3])})"
                conventions += "\n"
        
        # Add placeholder strategy section
        conventions += "\n## Placeholder Strategy\n"
        conventions += "- When encountering ambiguous or contextually sensitive terms, use: `{{German-term}}`\n"
        conventions += "- Explain reasoning for translation choice\n"
        conventions += "- Allow for evolution of term choices across translation\n"
        
        return conventions
    
    def save_analysis(self, analyzed_terms: List[PhilosophicalTerm], output_file: Path):
        """Save full analysis to JSON for future reference."""
        analysis_data = {
            "metadata": {
                "source_file": str(self.text_file),
                "total_terms": len(analyzed_terms),
                "analysis_date": None  # Could add timestamp
            },
            "terms": [asdict(term) for term in analyzed_terms]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved analysis to {output_file}")

def main():
    """Command-line interface for term extraction."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract and analyze philosophical terms")
    parser.add_argument("--input", type=Path, default=Path("cleaned_text.md"),
                       help="Input cleaned text file")
    parser.add_argument("--output-dir", type=Path, default=Path("."),
                       help="Output directory for generated files")
    parser.add_argument("--top-terms", type=int, default=50,
                       help="Number of top terms to analyze with LLM")
    parser.add_argument("--min-freq", type=int, default=3,
                       help="Minimum frequency for term inclusion")
    parser.add_argument("--model", default="gpt-4o",
                       help="Model to use for analysis")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run extraction
    extractor = TermExtractor(args.input, args.model)
    
    # Phase 1: Extract candidates
    term_contexts = extractor.extract_candidate_terms()
    term_contexts = extractor.filter_by_frequency(term_contexts, args.min_freq)
    
    # Phase 2: Prioritize and analyze
    priority_terms = extractor.prioritize_terms(term_contexts, args.top_terms)
    analyzed_terms = extractor.analyze_terms_batch(priority_terms, term_contexts)
    
    # Generate outputs
    glossary = extractor.generate_glossary(analyzed_terms)
    conventions = extractor.generate_conventions(analyzed_terms)
    
    # Save files
    (args.output_dir / "GLOSSARY.md").write_text(glossary, encoding='utf-8')
    (args.output_dir / "CONVENTIONS.md").write_text(conventions, encoding='utf-8')
    extractor.save_analysis(analyzed_terms, args.output_dir / "term_analysis.json")
    
    print(f"Generated GLOSSARY.md with {len([t for t in analyzed_terms if t.is_core_concept])} core concepts")
    print(f"Generated CONVENTIONS.md with translation rules")
    print(f"Saved detailed analysis to term_analysis.json")

if __name__ == "__main__":
    main()
