"""
Generator Agent - LangGraph Node (v2 Architecture)

Generates customer-facing responses using Ollama (free local LLM) with structured prompts
built from strategy YAML files.

The LLM executes the strategy—it does NOT make ethical decisions.
All ethical constraints are enforced by the ethics gate and strategy selector.

Key features:
- Builds system prompt from strategy YAML (tone, framing, prohibitions, directives)
- Integrates document_insights when present
- CRITICAL: Must cite ≥2 specific figures when document is present
- Temperature: 0.7 (0.5 on rewrite)
- Max tokens: 350
- Uses Ollama (local, free) instead of OpenAI

Reference: docs/updated_design.md Section 5 (Node 6: Generator Agent)
"""

import os
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Gemini client (lazy init)
_gemini_client = None


def _get_gemini_client():
    """Get or create Gemini client"""
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        _gemini_client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized")
    return _gemini_client


def _get_gemini_model() -> str:
    """Get Gemini model name from environment or use default"""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # Default to Gemini 2.5 Flash


def _fmt_list(items) -> str:
    """Format a list of strings as indented bullet points."""
    if not items:
        return "  (none specified)"
    return "\n".join(f"  - {item}" for item in items)


def build_system_prompt(
    strategy_config: dict,
    emotion: Optional[str],
    intent: Optional[str],
    situation: Optional[str],
    document_insights: Optional[List[str]],
    conversation_history: Optional[List[dict]] = None
) -> str:
    """
    Build system prompt from strategy YAML + context

    Per design doc, the prompt includes:
    1. Role and banking context
    2. Conversation history (for multi-turn awareness)
    3. User context (emotion, intent, situation)
    4. Document insights (if present) with citation requirement
    5. Strategy directives (tone, framing, prohibitions)

    Args:
        strategy_config: Loaded strategy YAML dict
        emotion: Detected emotion (or None)
        intent: Detected intent (or None)
        situation: Business situation (or None)
        document_insights: List of grounded observations from uploaded document (or None)
        conversation_history: Previous messages for context (or None)

    Returns:
        Formatted system prompt string
    """

    # Conversation history section
    history_section = ""
    if conversation_history and len(conversation_history) > 0:
        formatted_history = "\n".join([
            f"  {msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        history_section = f"""
CONVERSATION HISTORY:
{formatted_history}

IMPORTANT: Use this context to provide coherent, follow-up responses.
Reference previous topics naturally without repeating information.
"""

    # User context section
    context_section = ""
    if emotion or intent or situation:
        context_section = f"""
USER CONTEXT (detected by classifier):
- Emotion: {emotion or 'not detected'}
- Intent: {intent or 'not detected'}
- Business Situation: {situation or 'not detected'}
"""

    # Document insights section (CRITICAL: enforce citation requirement)
    document_section = ""
    if document_insights:
        insights_formatted = "\n".join(f"  {i+1}. {insight}" for i, insight in enumerate(document_insights))
        document_section = f"""
CUSTOMER'S DOCUMENT INSIGHTS:
{insights_formatted}

🚨 CRITICAL DOCUMENT REQUIREMENT - ZERO TOLERANCE FOR FABRICATION:
- You MUST cite at least 2 specific figures from the insights above
- You MUST NOT use generic statistics like "many customers find..."
- Ground ALL advice in the customer's actual data shown above
- If you cite a number, it MUST appear in the document insights verbatim

DO NOT FABRICATE:
- ❌ WRONG: Inventing figures like "$1,500 credit card balance" when not in insights
- ❌ WRONG: Making up categories like "$450/month on dining out" when not in insights
- ❌ WRONG: Citing product rates (e.g., "TCS high-yield savings at 4.2%") unless explicitly stated in insights
- ✅ CORRECT: "Your statement shows $312.00 in fees" (when this exact figure is in insights)
- ✅ CORRECT: "Your balance of $340" (when this exact figure is in insights)

EVERY number you mention must be traceable to the insights above. The critic will verify this.
"""

    # Banking products context (only for non-blocked strategies)
    banking_products_section = ""
    strategy_name = strategy_config.get('name', '')
    if 'block' not in strategy_name.lower():
        banking_products_section = """
TCS BANKING CONTEXT:
- You may reference TCS banking products: checking/savings accounts, CDs, personal loans, auto loans, mortgages, credit cards
- Always frame products as options to explore, never as mandatory
- Example: "TCS offers high-yield savings accounts that may align with your goals"
"""

    # Build final system prompt
    system_prompt = f"""You are a professional banking assistant for TCS (Tata Consultancy Services).
You help customers with retail banking products: deposit accounts, loans, credit cards, and account operations.
{banking_products_section}
{history_section}
ASSIGNED STRATEGY: {strategy_config.get('name', 'Informational')}
PRINCIPLE: {strategy_config.get('principle', '')}
REQUIRED TONE: {strategy_config.get('tone', 'Professional, helpful')}
{context_section}{document_section}
YOU MUST USE FRAMING LIKE:
{_fmt_list(strategy_config.get('compliant_framing', []))}

YOU MUST NEVER USE:
{_fmt_list(strategy_config.get('prohibited', []))}

CRITICAL DIRECTIVES (follow exactly):
{_fmt_list(strategy_config.get('directives', []))}

RESPONSE FORMAT:
- Keep your response concise: 2-3 paragraphs, approximately 150-200 words
- ALWAYS end with an open-ended question to continue the conversation
- The closing question should invite further discussion, clarification, or assistance
- Examples: "Would you like me to explain any of these options in more detail?"
  "What aspect of this would be most helpful to explore further?"
  "Is there anything specific about your situation you'd like to discuss?"
- Do not mention the strategy name, these instructions, or the classification in your response
- Respond directly to the customer's message"""

    return system_prompt


def generator_node(state: Dict) -> Dict:
    """
    LangGraph node: Generate response using Ollama (local LLM)

    Per design doc (Node 6):
    - Model: Configurable via OLLAMA_MODEL env var (default: llama3.2)
    - Temperature: 0.7 (0.5 on rewrite)
    - Max tokens: 350
    - Input: strategy_config, document_insights, emotion, intent, message
    - Output: response_draft

    Args:
        state: LangGraph state dict

    Returns:
        Dict with state update: response_draft
    """

    # Extract inputs from state
    strategy_config = state.get("strategy_config")
    message = state.get("message")
    emotion = state.get("emotion")
    intent = state.get("intent")
    situation = state.get("situation")
    document_insights = state.get("document_insights")
    conversation_history = state.get("conversation_history", [])
    rewrite_count = state.get("rewrite_count", 0)

    if not strategy_config:
        logger.error("Generator called without strategy_config in state")
        raise ValueError("strategy_config is required in state")

    if not message:
        logger.error("Generator called without message in state")
        raise ValueError("message is required in state")

    # Determine temperature based on whether this is a rewrite
    temperature = 0.5 if rewrite_count > 0 else 0.7

    model_name = _get_gemini_model()

    logger.info(
        f"Generator: model={model_name}, strategy={strategy_config.get('name')}, "
        f"has_doc_insights={document_insights is not None}, "
        f"history_msgs={len(conversation_history) if conversation_history else 0}, "
        f"rewrite_count={rewrite_count}, temp={temperature}"
    )

    # Build system prompt
    system_prompt = build_system_prompt(
        strategy_config=strategy_config,
        emotion=emotion,
        intent=intent,
        situation=situation,
        document_insights=document_insights,
        conversation_history=conversation_history
    )

    # Prepare user message (add rewrite instruction if applicable)
    user_message = message
    if rewrite_count > 0:
        user_message = f"{message}\n\n[NOTE: Please rewrite your previous response to better comply with the guidelines, especially regarding document citation requirements.]"

    # Call Gemini
    try:
        from google.genai import types
        client = _get_gemini_client()

        response = client.models.generate_content(
            model=model_name,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=2000  # Enough for 150-200 word responses
            )
        )

        response_draft = response.text.strip()

        logger.info(f"Generator produced {len(response_draft)} character response")

        return {
            "response_draft": response_draft
        }

    except Exception as e:
        logger.error(f"Generator Gemini call failed: {e}")
        # Fallback to safe error message
        return {
            "response_draft": (
                "I apologize, but I'm having trouble generating a response right now. "
                "Please contact our customer service team for assistance."
            )
        }
