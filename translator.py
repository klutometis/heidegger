from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field
import logging
import os
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai

class PhilosophicalTranslation(BaseModel):
    """Translation with philosophical reasoning."""
    
    translation: str = Field(description="The English translation of the German text")
    thinking: str = Field(description="Reasoning about translation choices, philosophical concepts, and terminological decisions")
    key_terms: List[str] = Field(description="Important philosophical terms encountered", default_factory=list)
    uncertainties: List[str] = Field(description="Translation choices that required judgment calls", default_factory=list)

@dataclass
class TranslationContext:
    """Holds context for translation."""
    prev_german_paragraphs: List[str]
    prev_english_paragraphs: List[str]
    current_german: str
    context_window_size: int = 2

class Translator:
    """LangChain-based translator with multi-model support."""
    
    def __init__(self, model_name: str = "gpt-4", **model_kwargs):
        self.model_name = model_name
        self.model = self._create_model(model_name, **model_kwargs)
        self.logger = logging.getLogger(__name__)
        
    def _create_model(self, model_name: str, **kwargs) -> BaseChatModel:
        """Factory for different LLM providers."""
        defaults = {"temperature": 0.1, "max_tokens": 2000}
        defaults.update(kwargs)
        
        if model_name.startswith("gpt"):
            return ChatOpenAI(model=model_name, **defaults)
        elif model_name.startswith("claude"):
            return ChatAnthropic(model=model_name, **defaults)
        elif model_name.startswith("gemini"):
            # Configure safety settings - Gemini is way too aggressive for philosophical content
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Remove max_tokens for Gemini (uses max_output_tokens instead)
            gemini_kwargs = {k: v for k, v in defaults.items() if k != "max_tokens"}
            # Use flexible token limit with higher default for philosophical content
            gemini_kwargs["max_output_tokens"] = kwargs.get("max_output_tokens", 4000)
                
            # Add safety settings and API key explicitly
            gemini_kwargs["safety_settings"] = safety_settings
            if "GOOGLE_API_KEY" in os.environ:
                gemini_kwargs["google_api_key"] = os.environ["GOOGLE_API_KEY"]
                
            return ChatGoogleGenerativeAI(model=model_name, **gemini_kwargs)
        else:
            raise ValueError(f"Unsupported model: {model_name}")
    
    def create_translation_chain(self, prompt_template: ChatPromptTemplate):
        """Create LCEL chain for translation."""
        
        def format_context(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Format the rolling context window."""
            context = inputs["translation_context"]
            config = inputs["config"]
            
            # Get last N paragraphs for context
            prev_german = "\n\n".join(
                context.prev_german_paragraphs[-context.context_window_size:]
            )
            prev_english = "\n\n".join(
                context.prev_english_paragraphs[-context.context_window_size:]
            )
            
            return {
                **config,  # style_guidelines, conventions, glossary
                "prev_german_context": prev_german,
                "prev_english_context": prev_english, 
                "current_german": context.current_german
            }
        
        # Build the LCEL chain
        chain = (
            RunnableLambda(format_context)
            | prompt_template
            | self.model
            | StrOutputParser()
        )
        
        return chain
    
    def translate_paragraph(self, 
                           translation_context: TranslationContext,
                           config: Dict[str, str]) -> PhilosophicalTranslation:
        """Translate a single paragraph with philosophical reasoning."""
        
        from prompt_builder import TranslationPromptBuilder
        
        # Build prompt template for structured output
        prompt_builder = TranslationPromptBuilder()
        
        # Use structured output - Gemini needs explicit format instructions
        if self.model_name.startswith("gemini"):
            # Use PydanticOutputParser for Gemini
            parser = PydanticOutputParser(pydantic_object=PhilosophicalTranslation)
            # Escape JSON braces so LangChain doesn't treat them as template variables
            format_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")
            prompt_template = prompt_builder.build_translation_prompt(
                include_format_instructions=True,
                format_instructions=format_instructions
            )
            structured_llm = self.model | parser
        else:
            prompt_template = prompt_builder.build_translation_prompt()
            structured_llm = self.model.with_structured_output(PhilosophicalTranslation)
        
        # Create chain with structured output
        def format_context(inputs: Dict[str, Any]) -> Dict[str, Any]:
            context = inputs["translation_context"]
            config = inputs["config"]
            
            prev_german = "\n\n".join(
                context.prev_german_paragraphs[-context.context_window_size:]
            )
            prev_english = "\n\n".join(
                context.prev_english_paragraphs[-context.context_window_size:]
            )
            
            return {
                **config,
                "prev_german_context": prev_german,
                "prev_english_context": prev_english,
                "current_german": context.current_german
            }
        
        chain = (
            RunnableLambda(format_context)
            | prompt_template  
            | structured_llm
        )
        
        try:
            raw_result = chain.invoke({
                "translation_context": translation_context,
                "config": config
            })
            
            # Handle different response formats based on include_raw setting
            if isinstance(raw_result, dict) and 'parsed' in raw_result:
                # include_raw=True case
                result = raw_result['parsed']
                raw_response = raw_result['raw']
                parsing_error = raw_result.get('parsing_error')
                
                if parsing_error:
                    self.logger.error(f"Parsing error: {parsing_error}")
                    self.logger.debug(f"Raw response: {raw_response}")
                    return None
                    
                if result is None:
                    self.logger.error("Model returned None after parsing")
                    self.logger.debug(f"Raw response: {raw_response}")
                    return None
                    
            else:
                # Normal structured output case
                result = raw_result
            
            # Check result validity
            if result is None:
                self.logger.error("Model returned None")
                return None
            elif not hasattr(result, 'translation'):
                self.logger.error(f"Model returned unexpected result type: {type(result)}")
                self.logger.debug(f"Result content: {result}")
                return None
                
            self.logger.info(f"Translated paragraph: {len(translation_context.current_german)} chars")
            return result
            
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return None
    
    async def translate_paragraph_async(self, 
                                       translation_context: TranslationContext,
                                       config: Dict[str, str]) -> PhilosophicalTranslation:
        """Async version for better performance."""
        from prompt_builder import TranslationPromptBuilder
        
        prompt_builder = TranslationPromptBuilder()
        prompt_template = prompt_builder.build_translation_prompt()
        
        structured_llm = self.model.with_structured_output(PhilosophicalTranslation)
        
        def format_context(inputs: Dict[str, Any]) -> Dict[str, Any]:
            context = inputs["translation_context"]
            config = inputs["config"]
            
            prev_german = "\n\n".join(
                context.prev_german_paragraphs[-context.context_window_size:]
            )
            prev_english = "\n\n".join(
                context.prev_english_paragraphs[-context.context_window_size:]
            )
            
            return {
                **config,
                "prev_german_context": prev_german,
                "prev_english_context": prev_english,
                "current_german": context.current_german
            }
        
        chain = (
            RunnableLambda(format_context)
            | prompt_template  
            | structured_llm
        )
        
        result = await chain.ainvoke({
            "translation_context": translation_context, 
            "config": config
        })
        
        return result
    
    def stream_translation(self,
                          translation_context: TranslationContext, 
                          config: Dict[str, str]):
        """Stream translation for long paragraphs."""
        from prompt_builder import TranslationPromptBuilder
        
        prompt_builder = TranslationPromptBuilder()
        prompt_template = prompt_builder.build_translation_prompt()
        chain = self.create_translation_chain(prompt_template)
        
        inputs = {
            "translation_context": translation_context,
            "config": config  
        }
        
        for chunk in chain.stream(inputs):
            yield chunk
