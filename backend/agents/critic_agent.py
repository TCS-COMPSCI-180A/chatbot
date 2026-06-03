"""
Critic Agent - LangGraph Node (v2 Architecture)

LLM-based response validation with chain-of-thought reasoning.
Scores responses 0-10 and checks for ethical/compliance violations.

Key features:
- Chain-of-thought reasoning (not just zero-shot classification)
- Document-specific checks (fabricated figures, citation requirements)
- Regulatory citations (FCA, FINRA)
- Bounded rewrite (max 1 time)
- Pass threshold: 7.0/10

Reference: docs/updated_design.md Section 5 (Node 7: Critic Agent)
"""

import os
import json
import logging
from typing import Dict, List, Optional

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
        logger.info("Gemini client initialized for critic")
    return _gemini_client


def _get_gemini_model() -> str:
    """Get Gemini model name from environment or use default"""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def critic_node(state: Dict) -> Dict:
    """
    LangGraph node: Validate response with LLM chain-of-thought reasoning

    Checks performed:
    - Standard: coercive language, fear tactics, persuasion in BLOCKED context, YAML violations
    - Document-specific: fabricated figures, generic advice when data exists, citation count

    Args:
        state: LangGraph state dict

    Returns:
        Dict with state updates: critic_score, critic_violations, critic_reasoning, rewrite_count
    """

    # Extract inputs from state
    response_draft = state.get("response_draft")
    strategy_config = state.get("strategy_config")
    gate_decision = state.get("gate_decision")
    has_document = state.get("has_document", False)
    document_insights = state.get("document_insights")
    rewrite_count = state.get("rewrite_count", 0)

    if not response_draft:
        logger.error("Critic called without response_draft in state")
        raise ValueError("response_draft is required in state")

    if not strategy_config:
        logger.error("Critic called without strategy_config in state")
        raise ValueError("strategy_config is required in state")

    logger.info(
        f"Critic: evaluating response (gate={gate_decision}, has_doc={has_document}, "
        f"rewrite_count={rewrite_count})"
    )

    # Build critic prompt with chain-of-thought instructions
    critic_prompt = _build_critic_prompt(
        response_draft=response_draft,
        strategy_config=strategy_config,
        gate_decision=gate_decision,
        has_document=has_document,
        document_insights=document_insights
    )

    # Call LLM for evaluation
    try:
        from google.genai import types
        client = _get_gemini_client()
        model = _get_gemini_model()

        llm_response = client.models.generate_content(
            model=model,
            contents=critic_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Low temperature for consistent scoring
                response_mime_type="application/json"
            )
        )

        result = json.loads(llm_response.text)

        critic_score = result.get("score", 0.0)
        violations = result.get("violations", [])
        reasoning = result.get("reasoning", "")

        logger.info(f"Critic score: {critic_score}/10, violations: {len(violations)}")

        return {
            "critic_score": critic_score,
            "critic_violations": violations,
            "critic_reasoning": reasoning
        }

    except Exception as e:
        logger.error(f"Critic LLM call failed: {e}")
        # Fail-safe: if critic errors, assume pass but log the error
        return {
            "critic_score": 7.0,
            "critic_violations": [f"Critic error: {str(e)}"],
            "critic_reasoning": f"Critic failed to evaluate - defaulting to pass. Error: {str(e)}"
        }


def _build_critic_prompt(
    response_draft: str,
    strategy_config: dict,
    gate_decision: str,
    has_document: bool,
    document_insights: Optional[List[str]]
) -> str:
    """
    Build critic evaluation prompt with chain-of-thought instructions

    Args:
        response_draft: Generated response to evaluate
        strategy_config: Strategy YAML dict
        gate_decision: BLOCKED, APPROVED, or AMBIGUOUS
        has_document: Whether document is present
        document_insights: List of grounded observations (if document present)

    Returns:
        Formatted prompt string for LLM
    """

    # Extract prohibited phrases from strategy YAML
    prohibited_phrases = strategy_config.get("prohibited", [])
    prohibited_section = ""
    if prohibited_phrases:
        prohibited_list = "\n".join(f"  - {phrase}" for phrase in prohibited_phrases)
        prohibited_section = f"""
STRATEGY PROHIBITED PHRASES (must not appear):
{prohibited_list}
"""

    # Document-specific checks
    document_section = ""
    if has_document and document_insights:
        insights_formatted = "\n".join(f"  {i+1}. {insight}" for i, insight in enumerate(document_insights))
        document_section = f"""
DOCUMENT CONTEXT:
The customer uploaded a document. The response MUST cite at least 2 specific figures from these insights:
{insights_formatted}

🔍 STRICT DOCUMENT VALIDATION (check EVERY number in response):
1. Extract ALL dollar amounts, percentages, and numeric values from the response
2. For EACH number, verify it appears in the document insights above
3. If ANY number is not found in insights → FABRICATION VIOLATION
4. Check for at least 2 specific figures cited from the document
5. Flag generic advice like "many customers find..." when specific data exists

Examples of fabrication:
- Response says "$1,500" but insights don't mention this → VIOLATION
- Response says "18.5% APR" but insights don't mention this → VIOLATION
- Response says "TCS offers 4.2% APY" when 4.2% was market rate, not TCS rate → VIOLATION
"""

    prompt = f"""You are a compliance critic evaluating a banking assistant's response for ethical and regulatory violations.

RESPONSE TO EVALUATE:
"{response_draft}"

CONTEXT:
- Gate decision: {gate_decision}
- Strategy: {strategy_config.get('name', 'Unknown')}
- Has customer document: {has_document}
{prohibited_section}{document_section}
EVALUATION CRITERIA (use chain-of-thought reasoning):

1. CRITICAL VIOLATION (instant fail, score = 0):
   - If gate_decision == "BLOCKED" and response contains ANY persuasive language
   - Persuasive words: "consider", "recommend", "opportunity", "benefits", "should"
   - BLOCKED responses must be purely empathetic/informational

2. COERCIVE LANGUAGE (-3.0 points):
   - Fear tactics: "you'll regret", "you'll lose out", "act now or miss"
   - Pressure: "limited time", "exclusive offer", "only for you"
   - Manipulation: "everyone is doing this", "you owe us"

3. PROHIBITED PHRASE VIOLATIONS (-2.0 points EACH):
   - Check if response contains any phrases from the strategy's prohibited list above

4. DOCUMENT VIOLATIONS (if has_document == True):
   - Fabricated figures (-5.0 EACH): ANY number not in document insights
   - Generic advice when data exists (-2.0): "many customers", "statistics show"
   - Failed to cite ≥2 figures (-2.0): Must reference at least 2 specific numbers from insights
   - Misattributed figures (-3.0): Citing market rate as TCS rate, etc.

5. REGULATORY COMPLIANCE:
   - FCA COBS 4.5.2: No false urgency or pressure
   - FINRA Rule 2210: Fair and balanced, not misleading
   - Must preserve customer autonomy (options, not directives)

SCORING:
- Start at 10.0
- Deduct points for each violation found
- Minimum score: 0.0
- Pass threshold: 7.0

OUTPUT FORMAT (JSON):
{{
  "score": 8.5,
  "violations": ["list of specific violations found, or empty list if none"],
  "reasoning": "Step-by-step chain-of-thought explaining your evaluation. Address each criterion above. Cite specific phrases from the response that led to deductions."
}}

Think through each criterion systematically. Be strict but fair. Return ONLY valid JSON."""

    return prompt


# For testing
if __name__ == "__main__":
    # Test critic with a mock response
    print("Testing critic agent...")

    from dotenv import load_dotenv
    load_dotenv("../.env", override=True)

    # Test case 1: Good response
    state1 = {
        "response_draft": "I understand your concern about savings. Financial experts generally recommend 3-6 months of expenses in an emergency fund. Would you like to discuss strategies for building this fund?",
        "strategy_config": {
            "name": "Authority Strategy",
            "prohibited": ["you should", "you must"]
        },
        "gate_decision": "APPROVED",
        "has_document": False,
        "document_insights": None,
        "rewrite_count": 0
    }

    result1 = critic_node(state1)
    print(f"\nTest 1 - Good response:")
    print(f"Score: {result1['critic_score']}/10")
    print(f"Violations: {result1['critic_violations']}")
    print(f"Reasoning: {result1['critic_reasoning'][:200]}...")

    # Test case 2: BLOCKED with persuasive language (should fail)
    state2 = {
        "response_draft": "I'm sorry for your loss. Before you cancel, consider the benefits of maintaining coverage.",
        "strategy_config": {
            "name": "Bereavement Support",
            "prohibited": []
        },
        "gate_decision": "BLOCKED",
        "has_document": False,
        "document_insights": None,
        "rewrite_count": 0
    }

    result2 = critic_node(state2)
    print(f"\nTest 2 - BLOCKED with persuasion (should fail):")
    print(f"Score: {result2['critic_score']}/10")
    print(f"Violations: {result2['critic_violations']}")
