#!/usr/bin/env python3
"""
Translation driver for Heidegger's Being and Time.
Basic flat configuration version.
"""

import argparse
import logging
from pathlib import Path
from typing import List
import sys

from translator import Translator, TranslationContext, PhilosophicalTranslation
from prompt_builder import TranslationPromptBuilder
from chunker import TextChunker

def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(description="Translate Being and Time using LangChain")
    parser.add_argument("--mode", default="translate", 
                       choices=["translate", "extract-terms", "generate-configs"],
                       help="Operation mode")
    parser.add_argument("--input", "-i", type=Path, default=Path("cleaned_text.md"),
                       help="Input cleaned text file")
    parser.add_argument("--output", "-o", type=Path, default=Path("translation.md"),
                       help="Output translation file")
    parser.add_argument("--model", "-m", default="gpt-4o",
                       help="Model to use (gpt-4o, gpt-4, claude-3-sonnet-20240229, etc.)")
    parser.add_argument("--start", type=int, default=0,
                       help="Start paragraph index")
    parser.add_argument("--end", type=int, default=10,
                       help="End paragraph index")
    parser.add_argument("--context-size", type=int, default=2,
                       help="Number of previous paragraphs for context")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--stream", action="store_true",
                       help="Stream translation output")
    
    # Term extraction specific arguments
    parser.add_argument("--top-terms", type=int, default=50,
                       help="Number of top terms to analyze with LLM")
    parser.add_argument("--min-freq", type=int, default=3,
                       help="Minimum frequency for term inclusion")
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Check input file exists
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    # Route to appropriate mode
    if args.mode == "extract-terms":
        extract_terms_mode(args, logger)
    elif args.mode == "generate-configs":
        generate_configs_mode(args, logger) 
    else:
        translate_mode(args, logger)

def extract_terms_mode(args, logger):
    """Term extraction mode."""
    from term_extractor import TermExtractor
    
    logger.info("Running term extraction mode")
    extractor = TermExtractor(args.input, args.model)
    
    # Extract and cluster by stems
    philosophical_terms = extractor.extract_and_cluster_terms()
    
    # Prioritize and analyze terms
    priority_terms = extractor.prioritize_terms(philosophical_terms, args.top_terms)
    analyzed_terms = extractor.analyze_terms_batch(priority_terms)
    
    # Save analysis
    output_dir = args.output.parent if args.output != Path("translation.md") else Path(".")
    extractor.save_analysis(analyzed_terms, output_dir / "term_analysis.json")
    
    logger.info(f"Term extraction complete. Found {len(analyzed_terms)} terms.")
    logger.info(f"Analysis saved to term_analysis.json")

def generate_configs_mode(args, logger):
    """Generate configuration files from term analysis."""
    import json
    
    logger.info("Generating configuration files from term analysis")
    
    # Load analysis
    analysis_file = args.input if args.input.name == "term_analysis.json" else Path("term_analysis.json")
    
    if not analysis_file.exists():
        logger.error(f"Term analysis file not found: {analysis_file}")
        logger.error("Run with --mode extract-terms first")
        sys.exit(1)
    
    with open(analysis_file, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)
    
    # Reconstruct PhilosophicalTerm objects
    from term_extractor import PhilosophicalTerm
    analyzed_terms = []
    for term_data in analysis_data["terms"]:
        term = PhilosophicalTerm(**term_data)
        analyzed_terms.append(term)
    
    # Generate configs
    from term_extractor import TermExtractor
    extractor = TermExtractor(Path("cleaned_text.md"))  # Dummy path for methods
    
    glossary = extractor.generate_glossary(analyzed_terms)
    conventions = extractor.generate_conventions(analyzed_terms)
    
    # Save files
    output_dir = args.output.parent if args.output != Path("translation.md") else Path(".")
    (output_dir / "GLOSSARY.md").write_text(glossary, encoding='utf-8')
    (output_dir / "CONVENTIONS.md").write_text(conventions, encoding='utf-8')
    
    logger.info("Generated GLOSSARY.md and CONVENTIONS.md")

def translate_mode(args, logger):
    """Translation mode (original functionality)."""
    # Initialize components
    logger.info(f"Initializing translator with model: {args.model}")
    translator = Translator(args.model)
    
    logger.info("Loading configuration files...")
    prompt_builder = TranslationPromptBuilder()
    config = prompt_builder.build_context_dict()
    
    logger.info(f"Loading text from: {args.input}")
    chunker = TextChunker(args.input)
    paragraphs = chunker.extract_paragraphs()
    
    logger.info(f"Found {len(paragraphs)} paragraphs")
    
    # Validate range
    if args.start >= len(paragraphs):
        logger.error(f"Start index {args.start} exceeds available paragraphs ({len(paragraphs)})")
        sys.exit(1)
    
    end_idx = min(args.end, len(paragraphs))
    logger.info(f"Translating paragraphs {args.start} to {end_idx-1}")
    
    # Translation loop
    german_history = []
    english_history = []
    translations = []
    
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(f"# Being and Time - Translation\n\n")
        f.write(f"**Model:** {args.model}\n")
        f.write(f"**Paragraphs:** {args.start}-{end_idx-1}\n\n")
        f.write("---\n\n")
        
        for i in range(args.start, end_idx):
            current_german = paragraphs[i]
            
            logger.info(f"Translating paragraph {i}/{len(paragraphs)}")
            logger.debug(f"German text: {current_german[:100]}...")
            
            # Build translation context
            context = TranslationContext(
                prev_german_paragraphs=german_history,
                prev_english_paragraphs=english_history,
                current_german=current_german,
                context_window_size=args.context_size
            )
            
            # Translate
            try:
                if args.stream:
                    # Note: Streaming not yet implemented for structured output
                    logger.warning("Streaming not supported with structured output, falling back to regular translation")
                
                # Get structured translation result
                structured_result = translator.translate_paragraph(context, config)
                
                # Write to file with enhanced formatting
                f.write(f"## Paragraph {i}\n\n")
                f.write(f"**German:**\n{current_german}\n\n")
                f.write(f"**English:**\n{structured_result.translation}\n\n")
                
                if structured_result.thinking:
                    f.write(f"**Translator's Notes:**\n{structured_result.thinking}\n\n")
                
                if structured_result.key_terms:
                    f.write(f"**Key Terms:** {', '.join(structured_result.key_terms)}\n\n")
                
                if structured_result.uncertainties:
                    f.write(f"**Translation Uncertainties:**\n")
                    for uncertainty in structured_result.uncertainties:
                        f.write(f"- {uncertainty}\n")
                    f.write("\n")
                
                f.write("---\n\n")
                
                # Update history (use just the translation text for context)
                german_history.append(current_german)
                english_history.append(structured_result.translation)
                translations.append(structured_result.translation)
                
                logger.info(f"✓ Completed paragraph {i}")
                
            except Exception as e:
                logger.error(f"Error translating paragraph {i}: {e}")
                f.write(f"## Paragraph {i} - ERROR\n\n")
                f.write(f"**German:**\n{current_german}\n\n")
                f.write(f"**Error:**\n{str(e)}\n\n")
                f.write("---\n\n")
                continue
    
    logger.info(f"Translation complete! Output saved to: {args.output}")
    logger.info(f"Translated {len(translations)} paragraphs successfully")

if __name__ == "__main__":
    main()
