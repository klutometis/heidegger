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

from langchain.globals import set_debug, set_verbose
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
                       choices=["translate", "extract-terms", "generate-configs", "extract-passages", "compare-passages", "meta-commentary", "compile-final-analysis"],
                       help="Operation mode")
    parser.add_argument("--input", "-i", type=Path, default=Path("cleaned_text.md"),
                       help="Input cleaned text file")
    parser.add_argument("--output", "-o", type=Path, default=Path("translation.md"),
                       help="Output translation file")
    parser.add_argument("--model", "-m", default="gpt-4o",
                       help="Model to use (gpt-4o, gpt-4, claude-3-sonnet-20240229, etc.)")
    parser.add_argument("--start", type=int, default=0,
                       help="Start paragraph index")
    parser.add_argument("--end", type=int, default=-1,
                       help="End paragraph index (default: -1 for all paragraphs)")
    parser.add_argument("--context-size", type=int, default=2,
                       help="Number of previous paragraphs for context")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--stream", action="store_true",
                       help="Stream translation output")
    parser.add_argument("--debug", action="store_true",
                       help="Enable LangChain debug mode (logs all events)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable LangChain verbose mode (logs important events)")
    
    # Term extraction specific arguments
    parser.add_argument("--top-terms", type=int, default=50,
                       help="Number of top terms to analyze with LLM")
    parser.add_argument("--min-freq", type=int, default=3,
                       help="Minimum frequency for term inclusion")
    
    # Passage extraction arguments
    parser.add_argument("--files", help="Comma-separated list of translation files to extract from")
    parser.add_argument("--paragraphs", help="Paragraph range to extract (e.g., '75-80')")
    
    # Meta-commentary arguments
    parser.add_argument("--critic-model", help="Model to use for meta-commentary analysis")
    
    # Final analysis compilation arguments
    parser.add_argument("--critiques", help="Comma-separated critique JSON files for final analysis")
    parser.add_argument("--with-summary", action="store_true",
                       help="Generate final summary with GPT (for compile-final-analysis mode)")
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Configure LangChain debugging
    if args.debug:
        set_debug(True)
        logger.info("LangChain debug mode enabled")
    elif args.verbose:
        set_verbose(True)
        logger.info("LangChain verbose mode enabled")
    
    # Check input file exists
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    # Route to appropriate mode
    if args.mode == "extract-terms":
        extract_terms_mode(args, logger)
    elif args.mode == "generate-configs":
        generate_configs_mode(args, logger)
    elif args.mode == "extract-passages":
        extract_passages_mode(args, logger)
    elif args.mode == "compare-passages":
        compare_passages_mode(args, logger)
    elif args.mode == "meta-commentary":
        meta_commentary_mode(args, logger)
    elif args.mode == "compile-final-analysis":
        compile_final_analysis_mode(args, logger)
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
    """Translation mode with progressive output."""
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
    
    # Handle sentinel value and validate range
    total_paragraphs = len(paragraphs)
    end_idx = total_paragraphs if args.end == -1 else args.end
    
    if args.start >= total_paragraphs:
        logger.error(f"Start index {args.start} exceeds total paragraphs ({total_paragraphs})")
        sys.exit(1)
    
    if end_idx > total_paragraphs:
        logger.warning(f"End index {end_idx} exceeds total paragraphs ({total_paragraphs}), using {total_paragraphs}")
        end_idx = total_paragraphs
    
    logger.info(f"Translating paragraphs {args.start} to {end_idx-1} (total: {total_paragraphs} paragraphs)")
    
    # Translation loop
    german_history = []
    english_history = []
    translations = []
    
    # Open file in append mode and write header if file is new
    file_exists = args.output.exists() and args.output.stat().st_size > 0
    
    with open(args.output, 'a', encoding='utf-8') as f:
        # Write header only if file is new/empty
        if not file_exists:
            f.write(f"# Being and Time - Translation\n\n")
            f.write(f"**Model:** {args.model}\n")
            f.write(f"**Started:** {args.start}-{end_idx-1}\n\n")
            f.write("---\n\n")
            f.flush()  # Ensure header is written immediately
        
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
                
                # Write immediately after each translation
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
                f.flush()  # Force write to disk immediately
                
                # Update history (use just the translation text for context)
                german_history.append(current_german)
                english_history.append(structured_result.translation)
                translations.append(structured_result.translation)
                
                logger.info(f"✓ Completed and saved paragraph {i}")
                
            except Exception as e:
                logger.error(f"Error translating paragraph {i}: {e}")
                f.write(f"## Paragraph {i} - ERROR\n\n")
                f.write(f"**German:**\n{current_german}\n\n")
                f.write(f"**Error:**\n{str(e)}\n\n")
                f.write("---\n\n")
                f.flush()
                continue
    
    logger.info(f"Translation complete! Output saved to: {args.output}")
    logger.info(f"Translated {len(translations)} paragraphs successfully")

def extract_passages_mode(args, logger):
    """Extract specific paragraphs from multiple translation files to JSON."""
    import json
    import dataclasses
    from datetime import datetime
    from translation_parser import TranslationParser
    
    if not args.files:
        logger.error("--files argument required for extract-passages mode")
        sys.exit(1)
    
    if not args.paragraphs:
        logger.error("--paragraphs argument required for extract-passages mode")
        sys.exit(1)
    
    # Parse paragraph range
    try:
        if '-' in args.paragraphs:
            start, end = map(int, args.paragraphs.split('-'))
            paragraph_numbers = list(range(start, end + 1))
        else:
            paragraph_numbers = [int(args.paragraphs)]
    except ValueError:
        logger.error(f"Invalid paragraph range: {args.paragraphs}. Use format '75-80' or '77'")
        sys.exit(1)
    
    # Parse file list
    file_paths = [Path(f.strip()) for f in args.files.split(',')]
    
    # Validate files exist
    for file_path in file_paths:
        if not file_path.exists():
            logger.error(f"Translation file not found: {file_path}")
            sys.exit(1)
    
    logger.info(f"Extracting paragraphs {args.paragraphs} from {len(file_paths)} translation files")
    
    # Extract data structure
    extracted_data = {
        "paragraph_range": args.paragraphs,
        "paragraph_numbers": paragraph_numbers,
        "extracted_date": datetime.now().isoformat(),
        "models": {}
    }
    
    for file_path in file_paths:
        logger.info(f"Parsing {file_path.name}...")
        
        # Determine model name from filename
        model_name = file_path.stem.replace('full_translation_', '')
        
        try:
            parser = TranslationParser(file_path)
            stats = parser.get_statistics()
            logger.info(f"  {file_path.name}: {stats}")
            
            # Extract requested paragraphs
            model_data = {}
            for para_num in paragraph_numbers:
                paragraph = parser.get_paragraph(para_num)
                if paragraph:
                    # Convert dataclass to dict for JSON serialization
                    para_dict = dataclasses.asdict(paragraph)
                    model_data[str(para_num)] = para_dict
                    logger.debug(f"  Extracted paragraph {para_num}")
                else:
                    logger.warning(f"  Paragraph {para_num} not found in {file_path.name}")
                    model_data[str(para_num)] = None
            
            extracted_data["models"][model_name] = model_data
            logger.info(f"  ✓ Extracted {len([p for p in model_data.values() if p is not None])} paragraphs")
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            extracted_data["models"][model_name] = {"error": str(e)}
    
    # Save to JSON
    logger.info(f"Saving extracted passages to {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)
    
    # Summary
    total_extracted = sum(
        len([p for p in model_data.values() if p is not None and not isinstance(p, dict) or "error" not in p])
        for model_data in extracted_data["models"].values()
        if not isinstance(model_data, dict) or "error" not in model_data
    )
    
    logger.info(f"✓ Extraction complete!")
    logger.info(f"  Paragraphs requested: {len(paragraph_numbers)}")
    logger.info(f"  Models processed: {len(file_paths)}")
    logger.info(f"  Total paragraphs extracted: {total_extracted}")
    logger.info(f"  Output: {args.output}")

def compare_passages_mode(args, logger):
    """Generate markdown comparison from extracted passages JSON."""
    import json
    from datetime import datetime
    
    if not args.input or not args.input.exists():
        logger.error(f"Input JSON file required and must exist: {args.input}")
        sys.exit(1)
    
    if not args.paragraphs:
        logger.error("--paragraphs argument required to specify which paragraphs to compare")
        sys.exit(1)
    
    # Parse paragraph selection (subset of what's in the JSON)
    try:
        if '-' in args.paragraphs:
            start, end = map(int, args.paragraphs.split('-'))
            selected_paragraphs = list(range(start, end + 1))
        else:
            selected_paragraphs = [int(args.paragraphs)]
    except ValueError:
        logger.error(f"Invalid paragraph range: {args.paragraphs}. Use format '75-80' or '77'")
        sys.exit(1)
    
    # Load extracted data
    logger.info(f"Loading extracted passages from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    available_paragraphs = data.get("paragraph_numbers", [])
    models = data.get("models", {})
    
    # Validate selected paragraphs are available
    missing = [p for p in selected_paragraphs if p not in available_paragraphs]
    if missing:
        logger.error(f"Paragraphs {missing} not found in extracted data. Available: {available_paragraphs}")
        sys.exit(1)
    
    logger.info(f"Comparing paragraphs {selected_paragraphs} from {len(models)} models")
    
    # Generate comparison markdown
    markdown_content = []
    markdown_content.append(f"# Philosophical Translation Comparison - Paragraph{'s' if len(selected_paragraphs) > 1 else ''} {args.paragraphs}")
    markdown_content.append("")
    markdown_content.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from {args.input}*")
    markdown_content.append("")
    
    for para_num in selected_paragraphs:
        markdown_content.append(f"## Paragraph {para_num}")
        markdown_content.append("")
        
        # Get German original (should be same across all models)
        german_text = None
        for model_name, model_data in models.items():
            if isinstance(model_data, dict) and str(para_num) in model_data:
                para_data = model_data[str(para_num)]
                if para_data and isinstance(para_data, dict):
                    german_text = para_data.get('german_text', '').strip()
                    break
        
        if german_text:
            markdown_content.append("### German Original")
            markdown_content.append("")
            markdown_content.append(german_text)
            markdown_content.append("")
        
        # Compare each model's translation
        for model_name, model_data in models.items():
            if isinstance(model_data, dict) and "error" in model_data:
                logger.warning(f"Skipping {model_name} due to parsing error: {model_data['error']}")
                continue
                
            markdown_content.append(f"### {model_name.upper()} Translation")
            markdown_content.append("")
            
            if str(para_num) in model_data and model_data[str(para_num)]:
                para_data = model_data[str(para_num)]
                
                if para_data.get('error_message'):
                    markdown_content.append(f"**Error:** {para_data['error_message']}")
                    markdown_content.append("")
                    continue
                
                # English translation
                if para_data.get('english_translation'):
                    markdown_content.append(f"**English:**")
                    markdown_content.append(para_data['english_translation'].strip())
                    markdown_content.append("")
                
                # Translator's reasoning
                if para_data.get('thinking'):
                    markdown_content.append(f"**Translator's Notes:**")
                    markdown_content.append(para_data['thinking'].strip())
                    markdown_content.append("")
                
                # Key terms
                if para_data.get('key_terms'):
                    terms = para_data['key_terms']
                    if terms and len(terms) > 0:
                        markdown_content.append(f"**Key Terms:** {', '.join(terms)}")
                        markdown_content.append("")
                
                # Uncertainties
                if para_data.get('uncertainties'):
                    uncertainties = para_data['uncertainties']
                    if uncertainties and len(uncertainties) > 0:
                        markdown_content.append(f"**Translation Uncertainties:**")
                        for uncertainty in uncertainties:
                            markdown_content.append(f"- {uncertainty}")
                        markdown_content.append("")
            else:
                markdown_content.append("**No translation data available**")
                markdown_content.append("")
        
        if len(selected_paragraphs) > 1:
            markdown_content.append("---")
            markdown_content.append("")
    
    # Add summary analysis section
    markdown_content.append("## Comparative Analysis")
    markdown_content.append("")
    markdown_content.append("### Terminological Approaches")
    markdown_content.append("*[Space for analysis of how each model handles key German philosophical terms]*")
    markdown_content.append("")
    markdown_content.append("### Translation Strategies")
    markdown_content.append("*[Space for analysis of literal vs interpretive approaches]*")
    markdown_content.append("")
    markdown_content.append("### Philosophical Reasoning Quality")
    markdown_content.append("*[Space for evaluation of the depth and accuracy of each model's commentary]*")
    markdown_content.append("")
    
    # Save comparison
    markdown_text = '\n'.join(markdown_content)
    logger.info(f"Writing comparison to {args.output}")
    
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    logger.info(f"✓ Comparison complete!")
    logger.info(f"  Paragraphs compared: {len(selected_paragraphs)}")
    logger.info(f"  Models compared: {len([m for m in models.keys() if not isinstance(models[m], dict) or 'error' not in models[m]])}")
    logger.info(f"  Output: {args.output}")

def meta_commentary_mode(args, logger):
    """Generate AI meta-commentary on competing translations."""
    import json
    from meta_analysis import MetaCommentary, TranslationCritique
    from translator import Translator
    from prompt_builder import TranslationPromptBuilder
    
    if not args.input or not args.input.exists():
        logger.error(f"Input JSON file required and must exist: {args.input}")
        sys.exit(1)
    
    if not args.critic_model:
        logger.error("--critic-model argument required for meta-commentary mode")
        sys.exit(1)
    
    if not args.paragraphs:
        logger.error("--paragraphs argument required to specify which paragraph to analyze")
        sys.exit(1)
    
    # Parse single paragraph (meta-commentary works best on one paragraph at a time)
    try:
        paragraph_number = int(args.paragraphs)
    except ValueError:
        logger.error("Meta-commentary mode requires a single paragraph number, not a range")
        sys.exit(1)
    
    # Load extracted data
    logger.info(f"Loading extracted passages from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models = data.get("models", {})
    available_paragraphs = data.get("paragraph_numbers", [])
    
    if paragraph_number not in available_paragraphs:
        logger.error(f"Paragraph {paragraph_number} not found. Available: {available_paragraphs}")
        sys.exit(1)
    
    logger.info(f"Generating meta-commentary for paragraph {paragraph_number} using {args.critic_model}")
    
    # Extract clean comparison data
    comparison_data = {
        "paragraph_number": paragraph_number,
        "german_original": "",
        "translations": {}
    }
    
    for model_name, model_data in models.items():
        if isinstance(model_data, dict) and "error" in model_data:
            logger.warning(f"Skipping {model_name} due to parsing error")
            continue
            
        para_data = model_data.get(str(paragraph_number))
        if not para_data or para_data.get('error_message'):
            logger.warning(f"Skipping {model_name} - no valid translation for paragraph {paragraph_number}")
            continue
        
        # Get German original (same for all models)
        if not comparison_data["german_original"]:
            comparison_data["german_original"] = para_data.get('german_text', '').strip()
        
        # Extract key elements for comparison
        translation_summary = {
            "english": para_data.get('english_translation', '').strip(),
            "key_reasoning": para_data.get('thinking', '').strip()[:500] + "..." if len(para_data.get('thinking', '')) > 500 else para_data.get('thinking', '').strip(),
            "key_terms": para_data.get('key_terms', []),
            "uncertainties": para_data.get('uncertainties', [])
        }
        
        comparison_data["translations"][model_name] = translation_summary
    
    if len(comparison_data["translations"]) < 2:
        logger.error(f"Need at least 2 valid translations to compare. Found: {len(comparison_data['translations'])}")
        sys.exit(1)
    
    # Create critique prompt
    critique_prompt = f"""You are analyzing different AI translations of this Heidegger passage from "Being and Time". 

# German Original (Paragraph {paragraph_number})
{comparison_data['german_original']}

# Competing Translations

"""
    
    for model_name, trans_data in comparison_data["translations"].items():
        critique_prompt += f"""## {model_name.upper()} Translation
**English:** {trans_data['english']}

**Key Reasoning:** {trans_data['key_reasoning']}

**Key Terms:** {', '.join(trans_data['key_terms']) if trans_data['key_terms'] else 'None listed'}

**Uncertainties:** {'; '.join(trans_data['uncertainties']) if trans_data['uncertainties'] else 'None listed'}

"""
    
    critique_prompt += """
# Your Task

Analyze all translations and provide:

1. **Critique each translation** - strengths, weaknesses, philosophical accuracy (score 1-10)
2. **Identify the best translation** - which model produced the most philosophically sound result?
3. **Defend your choice** - detailed argument for why it's superior 
4. **Show your reasoning** - your analytical process and key considerations
5. **Overall insights** - what this reveals about AI philosophical translation

Focus on: terminology choices, phenomenological fidelity, accessibility vs precision, interpretive depth.

Be thorough, specific, and fair in your analysis. You may critique your own translation if others are superior.
"""
    
    # Generate critique using the specified critic model
    logger.info(f"Generating critique with {args.critic_model}...")
    critic = Translator(args.critic_model)
    
    # Use structured output for meta-commentary
    if args.critic_model.startswith("gemini") or args.critic_model.startswith("claude") or args.critic_model.startswith("grok"):
        # Use PydanticOutputParser for problematic models
        from langchain_core.output_parsers import PydanticOutputParser
        parser = PydanticOutputParser(pydantic_object=MetaCommentary)
        format_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")
        critique_prompt += f"\n\n# Output Format\n\nRespond with valid JSON in this exact format:\n{format_instructions}"
        structured_llm = critic.model | parser
    else:
        # Clean approach for GPT
        structured_llm = critic.model.with_structured_output(MetaCommentary)
    
    # Create simple prompt template
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in philosophical translation, analyzing different AI approaches to translating Heidegger."),
        ("human", "{critique_prompt}")
    ])
    
    # Generate critique
    try:
        chain = prompt_template | structured_llm
        result = chain.invoke({"critique_prompt": critique_prompt})
        
        # Handle different response formats
        if isinstance(result, dict) and 'parsed' in result:
            meta_commentary = result['parsed'] 
        else:
            meta_commentary = result
        
        if not meta_commentary:
            logger.error("Failed to generate meta-commentary")
            sys.exit(1)
        
        logger.info(f"Generated critique: {len(critique_prompt)} char prompt -> {meta_commentary.critic_model} analysis")
        
    except Exception as e:
        logger.error(f"Error generating meta-commentary: {e}")
        sys.exit(1)
    
    # Save structured result
    output_data = {
        "paragraph_number": paragraph_number,
        "critic_model": args.critic_model,
        "generated_at": json.dumps(comparison_data, indent=2, ensure_ascii=False),  # Include source data
        "meta_commentary": {
            "critic_model": meta_commentary.critic_model,
            "paragraph_number": meta_commentary.paragraph_number,
            "critiques": {k: {
                "model_name": v.model_name,
                "strengths": v.strengths, 
                "weaknesses": v.weaknesses,
                "philosophical_accuracy_score": v.philosophical_accuracy_score,
                "accessibility_score": v.accessibility_score
            } for k, v in meta_commentary.critiques.items()},
            "best_translation": meta_commentary.best_translation,
            "reasoning": meta_commentary.reasoning,
            "thinking": meta_commentary.thinking,
            "overall_insights": meta_commentary.overall_insights
        }
    }
    
    logger.info(f"Saving meta-commentary to {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Meta-commentary complete!")
    logger.info(f"  Paragraph analyzed: {paragraph_number}")
    logger.info(f"  Translations compared: {len(comparison_data['translations'])}")
    logger.info(f"  Critic model: {args.critic_model}")
    logger.info(f"  Best translation (according to {args.critic_model}): {meta_commentary.best_translation}")
    logger.info(f"  Output: {args.output}")

def generate_final_summary(analysis_file: Path, translation_choices: dict, accuracy_scores: dict, num_translations: int, num_critiques: int, logger) -> str:
    """Generate concluding summary using GPT."""
    from translator import Translator
    
    # Load the complete analysis that was just written
    with open(analysis_file, 'r', encoding='utf-8') as f:
        full_analysis = f.read()
    
    # Create GPT translator
    translator = Translator(model_name="gpt-4o")
    
    # Build context about the experiment results
    consensus_info = ""
    if translation_choices:
        choice_counts = {}
        for choice in translation_choices.values():
            choice_counts[choice] = choice_counts.get(choice, 0) + 1
        
        if choice_counts:
            most_popular = max(choice_counts, key=choice_counts.get)
            consensus_info = f"Key finding: {most_popular} received {choice_counts[most_popular]} out of {len(translation_choices)} votes as the best translation."
    
    prompt = f"""You are analyzing a completed AI translation experiment. Read this full analysis and write a concluding summary that synthesizes what happened and what it reveals.

EXPERIMENT CONTEXT:
- {num_translations} AI models each translated the same Heidegger paragraph
- Then all {num_critiques} models critiqued all translations and chose the best one
- {consensus_info}

FULL ANALYSIS:
{full_analysis}

Write a final section titled "## Conclusion: What This Experiment Revealed" that covers:

1. **What actually happened**: Brief recap of the experimental process (4 translations → 4 critiques)
2. **The key finding**: Which translation was preferred and the level of consensus/disagreement
3. **Meta-commentary insights**: What this reveals about AI's capability for philosophical evaluation
4. **Broader significance**: What this means for AI-assisted scholarly work and transparent reasoning

Keep it concise but insightful (~300-500 words). Write in academic tone. Focus on what this experiment actually demonstrates about AI philosophical reasoning capabilities."""

    # Use simple completion
    from langchain_core.prompts import ChatPromptTemplate
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in AI and philosophical scholarship, writing a conclusion for an experimental study."),
        ("human", "{prompt}")
    ])
    
    chain = prompt_template | translator.model
    response = chain.invoke({"prompt": prompt})
    
    return response.content

def compile_final_analysis_mode(args, logger):
    """Compile comprehensive final analysis from passages and critiques."""
    import json
    from datetime import datetime
    from pathlib import Path
    
    if not args.input or not args.input.exists():
        logger.error(f"Input passages JSON file required and must exist: {args.input}")
        sys.exit(1)
    
    if not args.critiques:
        logger.error("--critiques argument required for final analysis compilation")
        sys.exit(1)
    
    if not args.paragraphs:
        logger.error("--paragraphs argument required to specify which paragraph to analyze")
        sys.exit(1)
    
    # Parse single paragraph
    try:
        paragraph_number = int(args.paragraphs)
    except ValueError:
        logger.error("Final analysis mode requires a single paragraph number, not a range")
        sys.exit(1)
    
    # Load passages data
    logger.info(f"Loading passages from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        passages_data = json.load(f)
    
    # Load critique files
    critique_files = [Path(f.strip()) for f in args.critiques.split(',')]
    critiques = {}
    
    logger.info(f"Loading {len(critique_files)} critique files...")
    for critique_file in critique_files:
        if not critique_file.exists():
            logger.error(f"Critique file not found: {critique_file}")
            sys.exit(1)
        
        with open(critique_file, 'r', encoding='utf-8') as f:
            critique_data = json.load(f)
            critic_model = critique_data.get('critic_model', critique_file.stem.replace('_critiques_paragraph_77', ''))
            critiques[critic_model] = critique_data['meta_commentary']
            logger.info(f"  Loaded critique from {critic_model}")
    
    # Extract paragraph data
    models = passages_data.get("models", {})
    paragraph_data = {}
    german_original = ""
    
    for model_name, model_data in models.items():
        if isinstance(model_data, dict) and str(paragraph_number) in model_data:
            para_data = model_data[str(paragraph_number)]
            if para_data and not para_data.get('error_message'):
                paragraph_data[model_name] = para_data
                if not german_original:
                    german_original = para_data.get('german_text', '').strip()
    
    if len(paragraph_data) < 2:
        logger.error(f"Need at least 2 valid translations. Found: {len(paragraph_data)}")
        sys.exit(1)
    
    logger.info(f"Compiling final analysis for paragraph {paragraph_number}")
    logger.info(f"  Translations: {list(paragraph_data.keys())}")
    logger.info(f"  Critiques: {list(critiques.keys())}")
    
    # Generate comprehensive markdown
    markdown_lines = []
    
    # Header
    markdown_lines.extend([
        f"# Four Minds on Being: AI Analysis of Heidegger Paragraph {paragraph_number}",
        "",
        "*An exploration of AI philosophical reasoning through comparative translation analysis*",
        "",
        f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ""
    ])
    
    # German Original
    markdown_lines.extend([
        "## German Original",
        "",
        german_original,
        ""
    ])
    
    # Four AI Translations
    markdown_lines.extend([
        "## Four AI Translations",
        ""
    ])
    
    for model_name, para_data in paragraph_data.items():
        markdown_lines.extend([
            f"### {model_name.upper()} Translation",
            "",
            "**English:**",
            para_data.get('english_translation', '').strip(),
            ""
        ])
        
        if para_data.get('thinking'):
            markdown_lines.extend([
                "**Translator's Notes:**",
                para_data['thinking'].strip(),
                ""
            ])
        
        if para_data.get('key_terms'):
            terms = para_data['key_terms']
            if terms:
                markdown_lines.extend([
                    f"**Key Terms:** {', '.join(terms)}",
                    ""
                ])
        
        if para_data.get('uncertainties'):
            uncertainties = para_data['uncertainties']
            if uncertainties:
                markdown_lines.extend([
                    "**Translation Uncertainties:**"
                ])
                for uncertainty in uncertainties:
                    markdown_lines.append(f"- {uncertainty}")
                markdown_lines.append("")
        
        markdown_lines.append("---")
        markdown_lines.append("")
    
    # AI Philosophical Debate
    markdown_lines.extend([
        "## The AI Philosophical Debate",
        "",
        "*Each model analyzes all four translations and defends their choice of the best approach*",
        ""
    ])
    
    translation_choices = {}
    accuracy_scores = {}
    
    for critic_model, critique_data in critiques.items():
        markdown_lines.extend([
            f"### {critic_model.upper()}'s Analysis",
            ""
        ])
        
        best_choice = critique_data.get('best_translation', 'Unknown')
        translation_choices[critic_model] = best_choice
        
        markdown_lines.extend([
            f"**Verdict:** {best_choice} translation is best",
            ""
        ])
        
        # Extract scores
        model_critiques = critique_data.get('critiques', {})
        if model_critiques:
            markdown_lines.append("**Philosophical Accuracy Scores:**")
            model_scores = {}
            for model_key, critique in model_critiques.items():
                if isinstance(critique, dict):
                    score = critique.get('philosophical_accuracy_score', 'N/A')
                    model_scores[model_key] = score
                    markdown_lines.append(f"- {model_key}: {score}/10")
            accuracy_scores[critic_model] = model_scores
            markdown_lines.append("")
        
        # Reasoning
        reasoning = critique_data.get('reasoning', '').strip()
        if reasoning:
            markdown_lines.extend([
                "**Reasoning:**",
                reasoning,
                ""
            ])
        
        markdown_lines.extend([
            "---",
            ""
        ])
    
    # Cross-Analysis
    markdown_lines.extend([
        "## Cross-Analysis: Where Models Agree and Disagree",
        ""
    ])
    
    # Translation Choice Consensus
    markdown_lines.extend([
        "### Translation Choice Consensus",
        ""
    ])
    
    for critic_model, choice in translation_choices.items():
        markdown_lines.append(f"- **{critic_model.upper()} chose:** {choice}")
    
    markdown_lines.append("")
    
    # Identify consensus
    choice_counts = {}
    for choice in translation_choices.values():
        choice_counts[choice] = choice_counts.get(choice, 0) + 1
    
    if choice_counts:
        most_popular = max(choice_counts, key=choice_counts.get)
        if choice_counts[most_popular] > 1:
            markdown_lines.extend([
                f"**Consensus:** {most_popular} received {choice_counts[most_popular]} votes as the best translation.",
                ""
            ])
    
    # Philosophical Accuracy Patterns
    if accuracy_scores:
        markdown_lines.extend([
            "### Philosophical Accuracy Score Summary",
            ""
        ])
        
        # Calculate average scores for each translation
        model_averages = {}
        for critic_scores in accuracy_scores.values():
            for model, score in critic_scores.items():
                if isinstance(score, (int, float)):
                    if model not in model_averages:
                        model_averages[model] = []
                    model_averages[model].append(score)
        
        for model, scores in model_averages.items():
            if scores:
                avg_score = sum(scores) / len(scores)
                markdown_lines.append(f"- **{model}:** Average {avg_score:.1f}/10 (from {len(scores)} critics)")
        
        markdown_lines.append("")
    
    # Insights
    markdown_lines.extend([
        "## Insights: What This Reveals About AI Translation",
        "",
        "### The Meta-Commentary Phenomenon",
        "",
        "This analysis reveals that AI models can:",
        "",
        "1. **Self-evaluate critically** - Models can identify weaknesses in their own translations",
        "2. **Recognize philosophical nuance** - They distinguish between technical accuracy and accessibility", 
        "3. **Apply consistent criteria** - Terminology choices, phenomenological fidelity, readability",
        "4. **Demonstrate reasoning transparency** - Show why specific translation choices matter philosophically",
        "",
        "### Implications for Philosophical Translation",
        "",
        "The comparative analysis demonstrates:",
        "",
        "- **Translation as interpretation** - Different valid approaches to the same philosophical concepts",
        "- **AI reasoning diversity** - Models prioritize different aspects (precision vs accessibility)",
        "- **Educational value** - Transparent reasoning helps readers understand translation challenges",
        "- **Scholarly apparatus evolution** - AI can create new forms of annotated, reasoned translations",
        "",
        "---",
        "",
        "*This analysis demonstrates transparent AI reasoning applied to philosophical translation, creating new*",
        "*possibilities for educational and scholarly engagement with complex texts.*"
    ])
    
    # Write final document
    markdown_content = '\n'.join(markdown_lines)
    
    logger.info(f"Writing final analysis to {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    # Generate final summary if requested
    if args.with_summary:
        logger.info("Generating final summary with GPT...")
        try:
            summary = generate_final_summary(args.output, translation_choices, accuracy_scores, len(paragraph_data), len(critiques), logger)
            
            # Append summary to the file
            with open(args.output, 'a', encoding='utf-8') as f:
                f.write("\n\n" + summary)
            
            logger.info("✓ Added GPT-generated summary to final analysis")
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            logger.info("Final analysis saved without summary")
    
    logger.info(f"✓ Final analysis complete!")
    logger.info(f"  Paragraph analyzed: {paragraph_number}")
    logger.info(f"  Translations compared: {len(paragraph_data)}")
    logger.info(f"  AI critics: {len(critiques)}")
    logger.info(f"  Consensus choice: {most_popular if 'most_popular' in locals() else 'No consensus'}")
    logger.info(f"  Output: {args.output}")

if __name__ == "__main__":
    main()
