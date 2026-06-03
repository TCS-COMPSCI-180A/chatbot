"""
Strategy Agent - LangGraph Node (v2 Architecture)

LLM agent that reasons about which strategy to select based on:
1. Ethics gate decision
2. Compliance overrides (fraud, account closure, loan modification)
3. Document context (NEW: document_grounded path)
4. Emotion + intent classification
5. Default fallback

Type: LLM (uses OpenAI GPT-4o-mini to reason through priority list)

Key changes from v1:
- BLOCKED → human handoff (no AI response)
- Document-grounded strategies for uploaded documents
- Compliance-blocked intents (fraud, close account, loan modification)
- LLM reasons through selection instead of hard-coded rules

Reference: docs/updated_design.md Section 5 (Node 5: Strategy Agent)
"""

import yaml
import os
import json
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Strategy files directory
STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "..", "strategies")

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
    return _gemini_client


def load_strategy(strategy_path: str) -> Dict:
    """
    Load strategy YAML file

    Args:
        strategy_path: Relative path like "soft_persuasion/social_proof" or "blocked/bereavement"

    Returns:
        Parsed YAML dict with strategy configuration

    Raises:
        FileNotFoundError: If strategy file doesn't exist
    """
    full_path = os.path.join(STRATEGIES_DIR, f"{strategy_path}.yaml")

    if not os.path.exists(full_path):
        logger.error(f"Strategy file not found: {full_path}")
        raise FileNotFoundError(f"Strategy not found: {strategy_path}")

    with open(full_path, 'r') as f:
        strategy = yaml.safe_load(f)

    logger.info(f"Loaded strategy: {strategy.get('name', strategy_path)}")
    return strategy


def _select_strategy_with_llm(
    message: str,
    gate_decision: str,
    gate_reason: str,
    intent: Optional[str],
    emotion: Optional[str],
    situation: Optional[str],
    has_document: bool,
    document_type: Optional[str]
) -> tuple[str, str]:
    """
    Use LLM to reason about strategy selection

    Returns:
        (strategy_path, reasoning)
    """
    system_prompt = """You are a strategy selection agent for an ethical banking chatbot.

Your job is to select the most appropriate response strategy based on the customer's context.

SELECTION PRIORITY (follow in order):

1. Compliance overrides (ALWAYS win, even if gate = APPROVED):
   - intent == "report_fraudulent_activity" → "blocked/fraud_report"
   - intent == "close_bank_account" → "blocked/high_risk" (no retention attempts)
   - intent == "request_loan_modification" → "blocked/financial_hardship"

2. Gate overrides:
   - gate_decision == "AMBIGUOUS" → "blocked/ambiguous" (ask clarifying questions)

3. Document-grounded path (only if document is uploaded):
   - has_document == True AND intent in ["seek_banking_advice", "request_explanation", "general_banking_inquiry"]
     → "document_grounded/statement_analysis" (for bank_statement, credit_card_statement, savings_statement)
     → "document_grounded/loan_analysis" (for loan_agreement, mortgage_statement, auto_loan_statement)

4. Emotion-first selection:
   - emotion contains "anxiety" OR "worry" OR "fear" OR "apprehension" → "soft_persuasion/social_proof"
   - emotion contains "neutral" OR "calm" AND intent == "seek_banking_advice" → "soft_persuasion/authority"
   - emotion contains "trust" OR "acceptance" AND situation is positive/neutral → "soft_persuasion/reciprocity"

5. Default fallback:
   → "neutral/informational"

AVAILABLE STRATEGIES:
- blocked/fraud_report
- blocked/high_risk
- blocked/financial_hardship
- blocked/ambiguous
- document_grounded/statement_analysis
- document_grounded/loan_analysis
- soft_persuasion/social_proof
- soft_persuasion/authority
- soft_persuasion/reciprocity
- neutral/informational

OUTPUT FORMAT (JSON):
{
  "strategy_path": "category/strategy_name",
  "reasoning": "Explain which priority level triggered and why this strategy is appropriate"
}"""

    user_prompt = f"""Select the appropriate strategy for this customer interaction.

CUSTOMER MESSAGE:
"{message}"

CONTEXT:
- Gate decision: {gate_decision}
- Gate reason: {gate_reason}
- Detected emotion: {emotion}
- Detected intent: {intent}
- Business situation: {situation}
- Has uploaded document: {has_document}
- Document type: {document_type}

Reason through the priority list and select the most appropriate strategy. Return JSON only."""

    try:
        from google.genai import types
        client = _get_gemini_client()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        strategy_path = result.get("strategy_path", "neutral/informational")
        reasoning = result.get("reasoning", "")

        return strategy_path, reasoning

    except Exception as e:
        logger.error(f"LLM strategy selection failed: {e}")
        return "neutral/informational", f"LLM error - fallback to safe default. Error: {str(e)}"


def strategy_node(state: Dict) -> Dict:
    """
    LangGraph node: LLM agent that selects strategy based on reasoning

    This is an LLM agent (not hard-coded rules). The LLM reasons through the
    priority list and selects the appropriate strategy.

    Selection Priority (from design doc Section 5):
    1. BLOCKED → human handoff (no AI response)
    2. Compliance overrides (fraud, close account, loan modification)
    3. AMBIGUOUS → blocked/ambiguous (ask clarifying questions)
    4. Document-grounded path (if document + advice-seeking intent)
    5. Emotion-first selection
    6. Default → neutral/informational

    Args:
        state: LangGraph state dict with gate_decision, emotion, intent, has_document, etc.

    Returns:
        Dict of state updates: strategy_path, strategy_config, strategy_reasoning
        OR human_handoff=True for BLOCKED cases
    """

    # Extract relevant fields from state
    gate_decision = state.get("gate_decision")
    gate_reason = state.get("gate_reason", "")
    intent = state.get("intent")
    emotion = state.get("emotion")
    situation = state.get("situation")
    has_document = state.get("has_document", False)
    document_type = state.get("document_type")
    message = state.get("message", "")

    logger.info(
        f"Strategy Agent: gate={gate_decision}, intent={intent}, "
        f"emotion={emotion}, has_doc={has_document}, doc_type={document_type}"
    )

    # ═══════════════════════════════════════════════════════════════
    # HARD RULE: BLOCKED → Human Handoff (NO LLM reasoning needed)
    # ═══════════════════════════════════════════════════════════════
    # This is a non-negotiable safety rule - no LLM can override
    if gate_decision == "BLOCKED":
        logger.warning(
            f"BLOCKED case detected (reason: {gate_reason}). "
            "Routing to human handoff - no AI response will be generated."
        )
        return {
            "human_handoff": True,
            "handoff_reason": gate_reason,
            "strategy_path": None,
            "strategy_config": None,
            "strategy_reasoning": (
                f"Gate BLOCKED due to: {gate_reason}. "
                "This case requires human intervention. No persuasion allowed."
            )
        }

    # ═══════════════════════════════════════════════════════════════
    # LLM REASONING: For all non-BLOCKED cases
    # ═══════════════════════════════════════════════════════════════

    strategy_path, reasoning = _select_strategy_with_llm(
        message=message,
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        intent=intent,
        emotion=emotion,
        situation=situation,
        has_document=has_document,
        document_type=document_type
    )

    logger.info(f"LLM selected strategy: {strategy_path}")
    logger.info(f"LLM reasoning: {reasoning}")

    # Validate strategy path exists
    try:
        strategy_config = load_strategy(strategy_path)
    except FileNotFoundError:
        logger.error(f"LLM selected non-existent strategy: {strategy_path}. Falling back to neutral/informational")
        strategy_path = "neutral/informational"
        strategy_config = load_strategy(strategy_path)
        reasoning += " [FALLBACK: LLM selected invalid strategy]"

    return {
        "strategy_path": strategy_path,
        "strategy_config": strategy_config,
        "strategy_reasoning": reasoning,
        "human_handoff": False
    }

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 2: Compliance Overrides (even if APPROVED)
    # ═══════════════════════════════════════════════════════════════
    if intent in COMPLIANCE_BLOCKED_INTENTS:
        if intent == "report_fraudulent_activity":
            strategy_path = "blocked/fraud_report"
            reasoning = "Fraud report detected - escalate immediately, no advice or upsell"
        elif intent == "close_bank_account":
            strategy_path = "blocked/high_risk"
            reasoning = "Account closure intent - no retention attempts allowed"
        elif intent == "request_loan_modification":
            strategy_path = "blocked/financial_hardship"
            reasoning = "Loan modification request signals financial hardship - informational only"
        else:
            strategy_path = "blocked/high_risk"
            reasoning = f"Compliance-blocked intent: {intent}"

        logger.info(f"Compliance override: {strategy_path}")
        return {
            "strategy_path": strategy_path,
            "strategy_config": load_strategy(strategy_path),
            "strategy_reasoning": reasoning,
            "human_handoff": False
        }

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 3: AMBIGUOUS → Ask clarifying questions
    # ═══════════════════════════════════════════════════════════════
    if gate_decision == "AMBIGUOUS":
        strategy_path = "blocked/ambiguous"
        reasoning = "Context unclear - asking clarifying questions before proceeding"
        logger.info("AMBIGUOUS gate - selecting clarification strategy")
        return {
            "strategy_path": strategy_path,
            "strategy_config": load_strategy(strategy_path),
            "strategy_reasoning": reasoning,
            "human_handoff": False
        }

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 4: Document-Grounded Path (NEW in v2)
    # ═══════════════════════════════════════════════════════════════
    # Only trigger if:
    # - Document is present
    # - Intent is advice-seeking or explanation-seeking
    # - User question is actually about the document (not unrelated)

    advice_seeking_intents = [
        "seek_banking_advice",
        "request_explanation",
        "general_banking_inquiry"
    ]

    if has_document and intent in advice_seeking_intents:
        # Choose strategy based on document type
        if document_type in LOAN_DOCUMENT_TYPES:
            strategy_path = "document_grounded/loan_analysis"
            reasoning = (
                f"Document present ({document_type}) + advice-seeking intent. "
                "Using document-grounded loan analysis strategy."
            )
        elif document_type in STATEMENT_DOCUMENT_TYPES:
            strategy_path = "document_grounded/statement_analysis"
            reasoning = (
                f"Document present ({document_type}) + advice-seeking intent. "
                "Using document-grounded statement analysis strategy."
            )
        else:
            # Unknown document type - fall through to emotion-first
            logger.warning(
                f"Document present but unknown type: {document_type}. "
                "Falling through to emotion-first selection."
            )
            strategy_path = None

        if strategy_path:
            logger.info(f"Document-grounded path: {strategy_path}")
            return {
                "strategy_path": strategy_path,
                "strategy_config": load_strategy(strategy_path),
                "strategy_reasoning": reasoning,
                "human_handoff": False
            }

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 5: Emotion-First Selection
    # ═══════════════════════════════════════════════════════════════
    # Research shows emotion is a stronger signal than intent for framing

    # High anxiety/fear/worry → Social proof (reassurance)
    if emotion and any(keyword in emotion.lower() for keyword in ["anxiety", "worry", "fear", "apprehension"]):
        strategy_path = "soft_persuasion/social_proof"
        reasoning = (
            f"Emotion: {emotion} - using social proof strategy "
            "(peer data for reassurance without pressure)"
        )
        logger.info(f"Emotion-first: anxiety/fear detected → {strategy_path}")
        return {
            "strategy_path": strategy_path,
            "strategy_config": load_strategy(strategy_path),
            "strategy_reasoning": reasoning,
            "human_handoff": False
        }

    # Calm/trust + advice-seeking → Authority (expert guidance)
    calm_emotions = ["neutral", "calm", "trust", "acceptance", "confidence"]
    if emotion and any(keyword in emotion.lower() for keyword in calm_emotions):
        if intent == "seek_banking_advice":
            strategy_path = "soft_persuasion/authority"
            reasoning = (
                f"Emotion: {emotion} + advice-seeking intent - using authority strategy "
                "(expert guidance for rational decision-making)"
            )
            logger.info(f"Emotion-first: calm + advice → {strategy_path}")
            return {
                "strategy_path": strategy_path,
                "strategy_config": load_strategy(strategy_path),
                "strategy_reasoning": reasoning,
                "human_handoff": False
            }

    # Trust/acceptance + positive situation → Reciprocity (loyalty-based offer)
    if emotion and any(keyword in emotion.lower() for keyword in ["trust", "acceptance"]):
        if situation == "positive_for_business" or situation == "neutral_for_business":
            strategy_path = "soft_persuasion/reciprocity"
            reasoning = (
                f"Emotion: {emotion} + {situation} - using reciprocity strategy "
                "(acknowledge loyalty, offer value in return)"
            )
            logger.info(f"Emotion-first: trust + positive → {strategy_path}")
            return {
                "strategy_path": strategy_path,
                "strategy_config": load_strategy(strategy_path),
                "strategy_reasoning": reasoning,
                "human_handoff": False
            }

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 6: Default Fallback → Neutral/Informational
    # ═══════════════════════════════════════════════════════════════
    strategy_path = "neutral/informational"
    reasoning = (
        f"No specific strategy matched (emotion={emotion}, intent={intent}). "
        "Defaulting to neutral informational response."
    )
    logger.info(f"Default fallback: {strategy_path}")
    return {
        "strategy_path": strategy_path,
        "strategy_config": load_strategy(strategy_path),
        "strategy_reasoning": reasoning,
        "human_handoff": False
    }
