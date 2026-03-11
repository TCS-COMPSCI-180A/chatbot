# System Architecture: TCS Ethical Persuasion Chatbot

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│                    Chatscope UI Kit Components                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP POST /api/v1/chat
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Python)                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATOR                             │ │
│  │  Coordinates: Gate → Classify → Strategy → Generate → Critic│ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 1: ETHICS GATE                                      │   │
│  │  ├─ Hard-coded rules (keywords: "died", "bankruptcy")     │   │
│  │  └─ DeBERTa v3 Zero-Shot (vulnerable? routine? unclear?)  │   │
│  │     Decision: BLOCKED | APPROVED | AMBIGUOUS              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         │ If BLOCKED → Empathetic response        │
│                         │ If APPROVED → Continue ↓                │
│                         ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 2: CLASSIFIER (3 Zero-Shot Calls)                   │   │
│  │  ├─ Emotion: anxiety? joy? fear? neutral? (Plutchik)      │   │
│  │  ├─ Intent: increase_investment? cancel_policy? advice?   │   │
│  │  └─ Situation: positive/neutral/negative for business     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 3: STRATEGY SELECTOR                                │   │
│  │  ├─ Compliance Override (always block: cancel_policy)     │   │
│  │  ├─ Emotion-First Selection (anxiety → social_proof)      │   │
│  │  └─ Load YAML file (strategies/soft_persuasion/...)       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 4: LLM GENERATOR (GPT-4o-mini)                      │   │
│  │  ├─ Build system prompt from YAML strategy               │   │
│  │  ├─ Include: tone, directives, compliant framing         │   │
│  │  └─ Generate draft response                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 5: CRITIC (Zero-Shot Validation)                    │   │
│  │  ├─ Score: coercive? fear tactics? appropriate?          │   │
│  │  ├─ If score < 7.0 → Rewrite (ONE time max)              │   │
│  │  └─ Return final response                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  STEP 6: DATABASE LOGGER                                  │   │
│  │  └─ Save: conversation, messages, classification trace    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            POSTGRESQL DATABASE (with pgvector)                   │
│  Tables: conversations, messages, classifications                │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Ethics Gate (`backend/pipeline/ethics_gate.py`)

**Purpose**: Fast, cheap gatekeeper. Blocks persuasion in vulnerable contexts.

**Implementation**:
```python
def evaluate(message: str) -> dict:
    # Layer 1: Hard-coded rules (instant, 100% reliable)
    for keyword in HARD_BLOCK_KEYWORDS:
        if keyword in message.lower():
            return {"decision": "BLOCKED", "reason": f"keyword:{keyword}"}

    # Layer 2: Zero-shot SLM (slower, more nuanced)
    result = classifier(message, candidate_labels=[
        "this person is vulnerable or distressed",
        "this is a routine financial inquiry",
        "the context is unclear"
    ])

    # Decision logic
    if "vulnerable" in top_label and confidence > 0.6:
        return {"decision": "BLOCKED"}
    elif "unclear" in top_label:
        return {"decision": "AMBIGUOUS"}
    else:
        return {"decision": "APPROVED"}
```

**Hard Block Keywords** (Always BLOCKED, no exceptions):
```python
HARD_BLOCK_KEYWORDS = [
    "passed away", "death", "died", "funeral", "bereavement",
    "bankruptcy", "foreclosure", "suicide", "grieving",
    "lost my job", "laid off", "can't afford"
]
```

**Why Two Layers?**
- Rules are instant and deterministic (no false negatives)
- Zero-shot catches nuanced vulnerability (e.g., "struggling financially")

**Model**: `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`
- State-of-the-art zero-shot classifier (Jan 2025)
- 184M parameters (fast enough for real-time)
- No training data needed

---

### 2. Classifier (`backend/pipeline/classifier.py`)

**Purpose**: Extract rich context (emotion, intent, situation) to inform strategy selection.

**Only runs if Ethics Gate = APPROVED** (saves compute on blocked messages).

**Three Parallel Classifications**:

#### A. Emotion Classification
**Labels** (Based on Plutchik's Wheel + Financial Context):
```python
EMOTION_LABELS = [
    "anxiety_or_worry",           # Financial uncertainty
    "fear_or_apprehension",       # Market volatility concerns
    "neutral_or_calm",            # Rational inquiry
    "anticipation_or_interest",   # Exploring new options
    "sadness_or_grief",           # Loss-related
    "joy_or_contentment",         # Positive financial news
    "anger_or_frustration",       # Service complaint
    "trust_or_acceptance"         # Confidence in advisor
]
```

**Research Basis**:
- Robert Plutchik's Psychoevolutionary Theory of Emotion (1980)
- 8 basic emotions, cross-culturally validated
- Expanded with Ekman's additions for financial context

#### B. Intent Classification
**Labels** (Financial Services Taxonomy):
```python
INTENT_LABELS = [
    # Investment Management
    "increase_investment_contribution",
    "decrease_investment_contribution",
    "inquire_about_investment_performance",

    # Policy Management
    "cancel_policy",
    "purchase_new_policy",
    "modify_coverage",

    # Withdrawals/Assistance
    "make_withdrawal",
    "hardship_withdrawal",

    # Information Seeking
    "general_inquiry",
    "request_explanation",
    "seek_advice",
    "compare_options"
]
```

**Research Basis**:
- Banking/insurance customer journey research
- TCS financial services use cases
- WAND Banking Taxonomy patterns

#### C. Situation Classification
**Labels** (Business Perspective):
```python
SITUATION_LABELS = [
    "positive_for_business",   # User wants to invest more
    "neutral_for_business",    # Informational query
    "negative_for_business"    # User wants to cancel/reduce
]
```

**Why This Matters**: Helps detect when business goals might conflict with ethics.

**Model**: Same DeBERTa v3 instance reused (memory efficient)

---

### 3. Strategy Selector (`backend/pipeline/strategy.py`)

**Purpose**: Choose which persuasion strategy to apply (or block persuasion).

**Selection Algorithm** (Emotion-First):

```python
def select_strategy(gate: dict, classification: dict) -> str:
    # Step 1: Compliance Overrides (ALWAYS win)
    if intent in ["cancel_policy", "hardship_withdrawal"]:
        return "blocked/high_risk"  # Never persuade during cancellation

    # Step 2: Respect Gate Decision
    if gate["decision"] == "BLOCKED":
        return "blocked/bereavement" if "bereavement" in reason else "blocked/high_risk"

    # Step 3: Emotion-Primary Selection
    emotion = classification["emotion"]

    if emotion in ["anxiety_or_worry", "fear_or_apprehension"]:
        return "soft_persuasion/social_proof"  # "Others in your situation..."

    if emotion == "neutral_or_calm" and intent == "seek_advice":
        return "soft_persuasion/authority"  # "Experts recommend..."

    # Default: Informational only
    return "neutral/informational"
```

**Why Emotion-First?**
- Research shows emotion is stronger signal than intent for framing
- Same intent ("increase investment") needs different strategies based on emotion:
  - Anxious user → Social proof (reassurance)
  - Calm user → Authority (expert guidance)

**Strategy Files** (YAML Format):

```yaml
# strategies/soft_persuasion/social_proof.yaml
name: "Social Proof"
principle: "People follow what others like them are doing"
tone: "Informational, evidence-based, supportive"

compliant_framing:
  - "Many customers in similar situations find that..."
  - "Financial planners generally recommend..."

prohibited:
  - "Everyone is doing this"
  - "You'll miss out if you don't"

directives:
  - "Share aggregate data only"
  - "Frame as general patterns, not predictions"
  - "Always include option to decline"
```

**Research Basis**: Robert Cialdini's 7 Principles of Influence
1. Reciprocity
2. Commitment & Consistency
3. Social Proof
4. Authority
5. Liking
6. Scarcity (ethical use only)
7. Unity

---

### 4. LLM Generator (`backend/pipeline/generator.py`)

**Purpose**: Generate final response using structured prompt from strategy YAML.

**Prompt Construction**:
```python
def build_system_prompt(strategy: dict, classification: dict) -> str:
    return f"""You are a financial services assistant for TCS.

USER CONTEXT:
- Emotion: {classification['emotion']}
- Intent: {classification['intent']}

STRATEGY: {strategy['name']}
TONE: {strategy['tone']}

YOU MUST USE FRAMING LIKE:
{strategy['compliant_framing']}

YOU MUST NEVER:
{strategy['prohibited']}

CRITICAL DIRECTIVES:
{strategy['directives']}

Generate a helpful response following these guidelines exactly.
Keep it concise (2-3 paragraphs max).
"""
```

**Model**: OpenAI GPT-4o-mini
- Fast, cost-effective
- Good instruction-following
- Temperature: 0.7 (natural but controlled)
- Max tokens: 300 (keeps responses concise)

**Why Structured Prompts?**
- LLM doesn't decide ethics, it just executes strategy
- All ethical decisions made by earlier pipeline steps
- Strategy YAML is human-reviewable by compliance teams

---

### 5. Critic (`backend/pipeline/critic.py`)

**Purpose**: Validate generated response for ethical/tonal compliance.

**Scoring**:
```python
def score_response(response: str, strategy: dict, gate: dict) -> dict:
    # Zero-shot classification on the RESPONSE
    result = classifier(response, candidate_labels=[
        "response_is_coercive_or_manipulative",
        "response_uses_fear_tactics",
        "response_is_empathetic_and_transparent",
        "response_follows_strategy_guidelines"
    ])

    violations = []
    score = 10.0

    # Check for violations
    if "coercive" in result["labels"][0]:
        violations.append("coercive_language")
        score -= 3.0

    # Special check: BLOCKED contexts must never persuade
    if gate["decision"] == "BLOCKED":
        persuasive_words = ["consider", "recommend", "opportunity"]
        if any(word in response.lower() for word in persuasive_words):
            violations.append("persuasion_in_blocked_context")
            score = 0.0  # Instant fail

    return {"score": score, "violations": violations, "passed": score >= 7.0}
```

**Bounded Rewrite** (ONE time maximum):
```python
def rewrite(original: str, violations: list) -> str:
    # If critic failed, generate ONE rewrite with explicit violation fixing
    rewrite_prompt = f"""
    The following response violated ethical guidelines:
    {original}

    Violations: {violations}

    Rewrite to remove these issues while keeping helpful information.
    """
    return llm.generate(rewrite_prompt, temperature=0.5)
```

**Why Only One Rewrite?**
- Prevents infinite loops
- Forces quality in first generation
- Reduces latency

---

### 6. Database Logger

**Purpose**: Full auditability for compliance review.

**Logged to PostgreSQL**:

**Conversation Table**:
```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    status VARCHAR(50),  -- active, archived, deleted
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Message Table**:
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(50),  -- user, assistant, system
    content TEXT,
    created_at TIMESTAMP,
    metadata JSONB  -- Stores debug info
);
```

**Classification Table** (Audit Trail):
```sql
CREATE TABLE classifications (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    message_id INTEGER REFERENCES messages(id),

    -- Ethics Gate
    gate_decision VARCHAR(50),  -- BLOCKED, APPROVED, AMBIGUOUS
    gate_reason VARCHAR(255),
    gate_confidence FLOAT,

    -- Classifier
    emotion VARCHAR(100),
    emotion_confidence FLOAT,
    intent VARCHAR(100),
    intent_confidence FLOAT,
    situation VARCHAR(100),
    situation_confidence FLOAT,

    -- Strategy
    selected_strategy VARCHAR(255),

    -- Critic
    critic_score FLOAT,
    critic_violations JSONB,
    rewrote BOOLEAN,

    -- Full trace
    raw_classification_data JSONB,
    created_at TIMESTAMP
);
```

**Example Audit Query**:
```sql
-- Find all BLOCKED interactions
SELECT
    c.id,
    m.content as user_message,
    cl.gate_decision,
    cl.gate_reason,
    cl.emotion,
    cl.selected_strategy
FROM conversations c
JOIN messages m ON m.conversation_id = c.id
JOIN classifications cl ON cl.conversation_id = c.id
WHERE cl.gate_decision = 'BLOCKED'
ORDER BY c.created_at DESC;
```

---

## Data Flow Example

### Scenario 1: Vulnerable User (Bereavement)

**Input**: "My spouse recently passed away. I need to cancel our life insurance."

**Step 1 - Ethics Gate**:
```json
{
  "decision": "BLOCKED",
  "reason": "keyword:passed away",
  "confidence": 1.0
}
```
→ **Skip classifier, go straight to empathetic response**

**Step 3 - Strategy Selector**:
```
Path: strategies/blocked/bereavement.yaml
```

**Step 4 - LLM Generator**:
```
System Prompt:
"CRITICAL DIRECTIVES:
- Express sincere condolences
- Provide ONLY requested information
- Do NOT suggest alternatives
- Do NOT attempt to retain policy"
```

**Response**:
```
"I'm very sorry for your loss. Here's the policy cancellation process:
1. Call 1-800-XXX-XXXX with policy number
2. Death certificate required
3. Processing time: 5-7 business days

Would you like me to connect you with a specialist?"
```

**Step 5 - Critic**:
```json
{
  "score": 10.0,
  "violations": [],
  "passed": true
}
```

**Logged to DB**:
```json
{
  "gate_decision": "BLOCKED",
  "gate_reason": "keyword:passed away",
  "emotion": null,
  "intent": null,
  "selected_strategy": "blocked/bereavement",
  "critic_score": 10.0,
  "rewrote": false
}
```

---

### Scenario 2: Approved User (Anxiety about Investment)

**Input**: "I'm worried about increasing my 401k contribution with the market being so volatile."

**Step 1 - Ethics Gate**:
```json
{
  "decision": "APPROVED",
  "reason": "safe_context",
  "confidence": 0.85
}
```
→ **Continue to classifier**

**Step 2 - Classifier**:
```json
{
  "emotion": "anxiety_or_worry",
  "emotion_confidence": 0.89,
  "intent": "increase_investment_contribution",
  "intent_confidence": 0.76,
  "situation": "positive_for_business",
  "situation_confidence": 0.82
}
```

**Step 3 - Strategy Selector**:
```
Emotion: anxiety_or_worry
→ Select: strategies/soft_persuasion/social_proof.yaml
```

**Step 4 - LLM Generator**:
```
System Prompt includes:
"COMPLIANT FRAMING:
- Many customers in similar situations find that...
- Research shows that people who..."

TONE: Informational, evidence-based, supportive
```

**Response**:
```
"Market volatility is a common concern, and it's smart to think carefully
about your contributions. Here's some context that might help:

Many financial planners note that during volatile periods, consistent
contributions can actually benefit from dollar-cost averaging—you buy more
shares when prices are low. Research shows people who maintain contributions
during downturns often see better long-term results.

You have a few options to consider:
1. Increase now by a small amount (even 1% helps over time)
2. Set a future increase date after the market stabilizes
3. Maintain your current contribution

What feels right for your situation?"
```

**Step 5 - Critic**:
```json
{
  "score": 9.0,
  "violations": [],
  "passed": true
}
```

**Logged to DB**: Full trace with all scores

---

## Technology Stack

### Backend
- **Framework**: FastAPI 0.109.0 (async, high-performance)
- **ORM**: SQLAlchemy 2.0.25
- **Database**: PostgreSQL with pgvector extension
- **AI Models**:
  - Classifier: `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` (Hugging Face)
  - Generator: `gpt-4o-mini` (OpenAI)
- **Libraries**: Transformers, PyTorch, python-dotenv

### Frontend
- **Framework**: React 18+ with Vite
- **UI Kit**: `@chatscope/chat-ui-kit-react`
- **HTTP Client**: Axios / Fetch API

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Database**: PostgreSQL 15+ with pgvector
- **Environment**: Python 3.10+, Node 18+

### Development Tools
- **Linting**: Black (Python), Prettier (JS)
- **Testing**: pytest, pytest-asyncio
- **Version Control**: Git

---

## Design Decisions & Rationale

### 1. Why Zero-Shot Models?
- **Speed**: No training data collection or fine-tuning needed
- **Flexibility**: Easy to add new labels without retraining
- **Research-Backed**: DeBERTa v3 is state-of-the-art (Jan 2025)

### 2. Why YAML for Strategies?
- **Human-Readable**: Compliance teams can review without code knowledge
- **Version-Controlled**: Track changes in Git
- **Tunable**: Edit behavior without redeploying backend
- **AI-Editable**: LLM can read and interpret strategy files

### 3. Why Emotion-First Strategy Selection?
- **Research**: Emotion is stronger signal than intent for framing (behavioral economics)
- **Example**: "increase investment" + anxiety needs different approach than + joy
- **Alignment**: Cialdini's principles work best when matched to emotional state

### 4. Why Sequential Pipeline (not parallel)?
- **Efficiency**: Don't waste compute classifying blocked messages
- **Clear Boundaries**: Each step has single responsibility
- **Debuggability**: Easy to trace where decisions are made
- **Cost**: Zero-shot models are expensive, only run when needed

### 5. Why Bounded Rewrite (max 1)?
- **Latency**: Each LLM call adds ~1-2 seconds
- **Quality**: Forces good first generation
- **Determinism**: Prevents infinite loops

---

**Last Updated**: 2026-03-10
**Maintained By**: Rounak Rao
**Review**: Update this file when architectural decisions change
