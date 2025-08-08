from pydantic import BaseModel, Field
from typing import Dict, Optional

class TranslationCritique(BaseModel):
    """Critique of a single model's translation."""
    model_name: str = Field(description="Name of the model being critiqued")
    strengths: str = Field(description="Strengths of this translation")
    weaknesses: str = Field(description="Weaknesses of this translation")
    philosophical_accuracy_score: int = Field(description="Accuracy score 1-10", ge=1, le=10)
    accessibility_score: int = Field(description="Accessibility score 1-10", ge=1, le=10)

class MetaCommentary(BaseModel):
    """AI model's analysis of competing translations."""
    critic_model: str = Field(description="Which model is doing the analysis")
    paragraph_number: int = Field(description="Which paragraph being analyzed")
    
    critiques: Optional[Dict[str, TranslationCritique]] = Field(
        default_factory=dict,
        description="Analysis of each model's translation"
    )
    
    best_translation: str = Field(
        description="Which model produced the best translation"
    )
    
    reasoning: str = Field(
        description="Detailed argument for why that translation is superior"
    )
    
    thinking: str = Field(
        description="The critic's analytical process and considerations"
    )
    
    overall_insights: str = Field(
        description="What this comparison reveals about philosophical translation"
    )
