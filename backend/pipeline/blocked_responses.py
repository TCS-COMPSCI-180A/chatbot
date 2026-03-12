"""
Blocked Response Builder — backend/pipeline/blocked_responses.py
================================================================
Generates empathetic, persuasion-free responses for BLOCKED / AMBIGUOUS
Ethics Gate results.

Core rule: when a user is vulnerable we ONLY provide what they asked for.
No upselling. No retention. No persuasion. Ever.
"""

from enum import Enum


# =============================================================================
# Vulnerability categories (maps to FCA four vulnerability drivers)
# =============================================================================
class BlockedCategory(str, Enum):
    BEREAVEMENT  = "bereavement"    # FCA: Life events
    BANKRUPTCY   = "bankruptcy"     # FCA: Resilience
    JOB_LOSS     = "job_loss"       # FCA: Life events / Resilience
    CANNOT_AFFORD = "cannot_afford" # FCA: Resilience
    SUICIDE      = "suicide"        # FCA: Health
    HIGH_RISK    = "high_risk"      # Model-detected — catch-all
    AMBIGUOUS    = "ambiguous"      # Context unclear


# =============================================================================
# Keyword → Category
# =============================================================================
KEYWORD_TO_CATEGORY: dict[str, BlockedCategory] = {
    "passed away":  BlockedCategory.BEREAVEMENT,
    "death":        BlockedCategory.BEREAVEMENT,
    "died":         BlockedCategory.BEREAVEMENT,
    "funeral":      BlockedCategory.BEREAVEMENT,
    "bereavement":  BlockedCategory.BEREAVEMENT,
    "grieving":     BlockedCategory.BEREAVEMENT,

    "suicide":      BlockedCategory.SUICIDE,

    "bankruptcy":   BlockedCategory.BANKRUPTCY,
    "foreclosure":  BlockedCategory.BANKRUPTCY,

    "lost my job":  BlockedCategory.JOB_LOSS,
    "laid off":     BlockedCategory.JOB_LOSS,

    "can't afford": BlockedCategory.CANNOT_AFFORD,
}

# =============================================================================
# Response templates — empathetic, zero persuasion
# =============================================================================
BLOCKED_RESPONSES: dict[BlockedCategory, str] = {
    BlockedCategory.BEREAVEMENT: (
        "I'm truly sorry for your loss. We're here to make this as "
        "straightforward as possible during this difficult time.\n\n"
        "To process your request please contact our bereavement support team:\n"
        "  • Phone: 1-800-XXX-XXXX  (Mon–Fri, 8am–6pm)\n"
        "  • Or reply here and a specialist will reach you within one business day.\n\n"
        "We will take care of everything you need."
    ),

    BlockedCategory.SUICIDE: (
        "I'm concerned about what you've shared and I want to make sure "
        "you're okay. If you're in crisis, please reach out now:\n\n"
        "  • National Suicide Prevention Lifeline: 988  (call or text, 24/7)\n"
        "  • Crisis Text Line: Text HOME to 741741\n\n"
        "For your account, our team is here whenever you're ready: 1-800-XXX-XXXX. "
        "Please take care of yourself first."
    ),

    BlockedCategory.BANKRUPTCY: (
        "I understand you're going through a very difficult time. "
        "Our financial hardship specialists are best placed to help you:\n\n"
        "  • Hardship Support Line: 1-800-XXX-XXXX  (Mon–Fri, 9am–5pm)\n\n"
        "They can walk you through exactly what applies to your account "
        "with no pressure."
    ),

    BlockedCategory.JOB_LOSS: (
        "I'm sorry to hear you're facing this situation. We have a dedicated "
        "hardship team who can discuss what relief options may be available:\n\n"
        "  • Hardship Line: 1-800-XXX-XXXX  (Mon–Fri, 9am–5pm)\n"
        "  • Or request a callback at a time that suits you.\n\n"
        "There's no pressure — we just want to make sure you have the right information."
    ),

    BlockedCategory.CANNOT_AFFORD: (
        "Thank you for letting us know. Our hardship support team can review "
        "what options are available for your situation:\n\n"
        "  • Hardship Line: 1-800-XXX-XXXX  (Mon–Fri, 9am–5pm)\n\n"
        "They're there to help, not to pressure you."
    ),

    BlockedCategory.HIGH_RISK: (
        "It sounds like you may be going through a difficult time. I'd like to "
        "make sure you get the right support rather than a generic response.\n\n"
        "A specialist can help with exactly what you need:\n"
        "  • Support Line: 1-800-XXX-XXXX  (Mon–Fri, 8am–6pm)\n\n"
        "If you'd prefer, share a little more detail here and I'll point you "
        "in the right direction."
    ),

    BlockedCategory.AMBIGUOUS: (
        "I want to make sure I understand your situation before responding. "
        "Could you tell me a bit more about what you need?\n\n"
        "Alternatively, a specialist is available to help directly:\n"
        "  • Support Line: 1-800-XXX-XXXX  (Mon–Fri, 8am–6pm)"
    ),
}


# =============================================================================
# Public interface
# =============================================================================
def get_blocked_response(gate_result: dict) -> str:
    """
    Return the appropriate empathetic response for a BLOCKED/AMBIGUOUS gate result.

    Parameters
    ----------
    gate_result : dict  — as returned by ethics_gate.evaluate()

    Returns
    -------
    str — safe, empathetic response ready to send to the user.
    """
    if gate_result.get("decision") == "AMBIGUOUS":
        return BLOCKED_RESPONSES[BlockedCategory.AMBIGUOUS]

    category = resolve_category(gate_result)
    return BLOCKED_RESPONSES[category]


def resolve_category(gate_result: dict) -> BlockedCategory:
    """Resolve the BlockedCategory from a gate result dict."""
    reason = gate_result.get("reason", "")
    if reason.startswith("keyword:"):
        keyword = reason.split("keyword:", 1)[1]
        return KEYWORD_TO_CATEGORY.get(keyword, BlockedCategory.HIGH_RISK)
    return BlockedCategory.HIGH_RISK
