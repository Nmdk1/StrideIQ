"""
AI-Powered Knowledge Extraction

Uses Claude/GPT-4 to extract coaching principles from text.
"""
import os
import json
import logging
from typing import Dict, List, Optional
from openai import OpenAI
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Initialize AI clients
openai_client = None
anthropic_client = None

try:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
except Exception as e:
    logger.warning(f"OpenAI client not initialized: {e}")

try:
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        anthropic_client = Anthropic(api_key=anthropic_api_key)
except Exception as e:
    logger.warning(f"Anthropic client not initialized: {e}")


def _call_ai(prompt: str, model_preference: str = "claude") -> Optional[str]:
    """
    Call AI model for extraction.
    
    Args:
        prompt: Prompt for AI
        model_preference: "claude" or "gpt4"
        
    Returns:
        AI response text or None
    """
    # Try Claude first (default)
    if model_preference == "claude" and anthropic_client:
        try:
            response = anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
    
    # Fallback to GPT-4
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
    
    logger.error("No AI client available")
    return None


def extract_vdot_formula(text: str) -> Optional[Dict]:
    """
    Extract VDOT formula and pace tables from text.
    
    Returns:
        Dictionary with VDOT formula, pace tables, and training zones
    """
    prompt = f"""Extract VDOT (Jack Daniels' Running Formula) information from this text.

Focus on:
1. VDOT calculation formula
2. Training pace tables (E, M, T, I, R paces)
3. VDOT-to-pace conversion tables
4. Training zone definitions

Return as JSON with structure:
{{
    "vdot_formula": "formula description",
    "pace_tables": {{"E": "...", "M": "...", "T": "...", "I": "...", "R": "..."}},
    "training_zones": {{"description": "...", "heart_rate_ranges": "..."}},
    "vdot_to_pace": "conversion method"
}}

Text excerpt:
{text[:8000]}  # Limit to avoid token limits
"""
    
    response = _call_ai(prompt, "claude")
    if not response:
        return None
    
    try:
        # Try to extract JSON from response
        if "{" in response and "}" in response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        else:
            return {"extracted_text": response}
    except Exception as e:
        logger.error(f"Error parsing VDOT extraction: {e}")
        return {"extracted_text": response}


def extract_periodization_principles(text: str, methodology: str) -> Optional[Dict]:
    """
    Extract periodization model from text.
    
    Returns:
        Dictionary with periodization phases and rules
    """
    prompt = f"""Extract periodization and training phase principles from this {methodology} text.

Focus on:
1. Training phases (base, build, peak, taper, etc.)
2. Phase duration guidelines
3. Training load progression rules
4. Phase transition criteria
5. Recovery periods

Return as JSON:
{{
    "phases": [
        {{"name": "...", "duration": "...", "focus": "...", "load": "..."}}
    ],
    "progression_rules": "...",
    "transition_criteria": "..."
}}

Text excerpt:
{text[:8000]}
"""
    
    response = _call_ai(prompt, "claude")
    if not response:
        return None
    
    try:
        if "{" in response and "}" in response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            return json.loads(response[json_start:json_end])
        return {"extracted_text": response}
    except Exception as e:
        logger.error(f"Error parsing periodization extraction: {e}")
        return {"extracted_text": response}


def extract_general_principles(text: str, source: str, methodology: str) -> Optional[Dict]:
    """
    Extract general coaching principles from text.
    
    Returns:
        Dictionary with general principles, workout types, recovery guidelines
    """
    prompt = f"""Extract key coaching principles from {source} ({methodology} methodology).

Extract:
1. Core training principles
2. Workout types and descriptions
3. Recovery guidelines
4. Injury prevention strategies
5. Key formulas or calculations
6. Training intensity guidelines

Return as JSON:
{{
    "core_principles": ["principle1", "principle2", ...],
    "workout_types": [
        {{"name": "...", "description": "...", "purpose": "...", "intensity": "..."}}
    ],
    "recovery_guidelines": "...",
    "injury_prevention": "...",
    "key_formulas": ["formula1", "formula2", ...]
}}

Text excerpt (first 10000 chars):
{text[:10000]}
"""
    
    response = _call_ai(prompt, "claude")
    if not response:
        return None
    
    try:
        if "{" in response and "}" in response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            return json.loads(response[json_start:json_end])
        return {"extracted_text": response}
    except Exception as e:
        logger.error(f"Error parsing general principles: {e}")
        return {"extracted_text": response}


def chunk_text_for_extraction(text: str, chunk_size: int = 10000) -> List[str]:
    """
    Chunk text into manageable pieces for AI extraction.
    
    Args:
        text: Full text
        chunk_size: Target chunk size in characters
        
    Returns:
        List of text chunks
    """
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
