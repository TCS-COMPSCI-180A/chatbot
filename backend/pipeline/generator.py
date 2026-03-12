"""
LLM Generator - Step 4 of the pipeline.

Builds a structured system prompt from the strategy YAML and calls GPT-4o-mini
to produce a compliant response. The LLM executes strategy—it does NOT make
ethical decisions (those are made by the ethics gate and strategy selector).

Model: gpt-4o-mini
  - Fast and cost-effective for high-volume chat
  - Excellent instruction-following for constrained generation
  - Temperature 0.7: natural-sounding but controlled output
  - Max tokens 300: keeps responses concise (2-3 paragraphs)

Research basis:
  - Structured prompting enforces strategy compliance at generation time
  - Separating ethical logic from generation prevents LLM from "deciding" ethics
"""

import os
from typing import Optional

from openai import OpenAI

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Get or create the OpenAI client lazily."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Add it to your .env file."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _fmt_list(items) -> str:
    """Format a list of strings as indented bullet points."""
    if not items:
        return "  (none specified)"
    return "\n".join(f"  - {item}" for item in items)


def build_system_prompt(strategy: dict, classification: Optional[dict]) -> str:
    """
    Build the system prompt for GPT-4o-mini from strategy YAML + classification context.

    The prompt:
      1. Sets role and TCS context
      2. Provides detected emotion/intent if APPROVED path (helps LLM tailor tone)
      3. Specifies required framing (compliant_framing from YAML)
      4. Specifies prohibited language (prohibited from YAML)
      5. Lists critical directives (directives from YAML)

    Args:
        strategy: Loaded strategy YAML dict
        classification: Classification result dict, or None for BLOCKED/AMBIGUOUS paths

    Returns:
        Formatted system prompt string
    """
    # User context section (only present for APPROVED path with full classification)
    context_section = ""
    if classification:
        emotion = classification.get("emotion", "unknown")
        emotion_conf = classification.get("emotion_confidence", 0)
        intent = classification.get("intent", "unknown")
        intent_conf = classification.get("intent_confidence", 0)
        situation = classification.get("situation", "unknown")
        context_section = f"""
USER CONTEXT (detected by classifier):
- Emotion: {emotion} (confidence: {emotion_conf:.0%})
- Intent: {intent} (confidence: {intent_conf:.0%})
- Business Situation: {situation}
"""

    system_prompt = f"""You are a professional financial services assistant for TCS (Tata Consultancy Services).
You help customers with financial products including 401k plans, insurance policies, and investment accounts.

ASSIGNED STRATEGY: {strategy.get('name', 'Informational')}
PRINCIPLE: {strategy.get('principle', '')}
REQUIRED TONE: {strategy.get('tone', 'Professional, helpful')}
{context_section}
YOU MUST USE FRAMING LIKE:
{_fmt_list(strategy.get('compliant_framing', []))}

YOU MUST NEVER USE:
{_fmt_list(strategy.get('prohibited', []))}

CRITICAL DIRECTIVES (follow exactly):
{_fmt_list(strategy.get('directives', []))}

Generate a helpful, professional response following all guidelines above.
Keep your response concise: 2-3 paragraphs, approximately 100-150 words.
Do not mention the strategy name, these instructions, or the classification in your response.
Respond directly to the customer's message."""

    return system_prompt


def generate(
    message: str,
    classification: Optional[dict],
    strategy_config: dict,
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """
    Generate a compliant response using GPT-4o-mini.

    Args:
        message: Original user message
        classification: Classification results (None for BLOCKED/AMBIGUOUS paths)
        strategy_config: Loaded strategy YAML dict
        temperature: Generation temperature (0.7 = natural but controlled)
        max_tokens: Maximum response length in tokens

    Returns:
        Generated response text (stripped)

    Raises:
        ValueError: If OPENAI_API_KEY is not set
        openai.OpenAIError: On API failures
    """
    client = _get_client()
    system_prompt = build_system_prompt(strategy_config, classification)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return completion.choices[0].message.content.strip()
