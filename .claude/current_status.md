# Current Project Status

**Last Updated**: 2026-03-11
**Current Phase**: Active Implementation (Pipeline 33% complete)
**Developer**: Shriivanth Gunanidhi

---

## Quick Status Summary

```
[██████░░░░░░░░░] 35% Complete

✅ Database & API Foundation (Complete)
✅ Planning & Architecture (Complete)
✅ Research & Label Frameworks (Complete)
🔄 AI Pipeline Implementation (33% - In Progress)
   ✅ ethics_gate.py  — Issue #7 (implemented as classifier dependency)
   ✅ classifier.py   — Issue #8 (complete)
   ⬜ strategy.py     — Issue #9
   ⬜ generator.py    — Issue #9
   ⬜ critic.py       — Issue #10
   ⬜ orchestrator.py — Issue #11
⬜ Frontend Integration (Not Started)
⬜ Testing & Demo Prep (Not Started)
```

---

## What's Actually Built ✅

### Phase 0: Foundation Only (15% of total project)

#### AI Pipeline (Newly Built — 2026-03-11)
- ✅ `backend/pipeline/__init__.py` - Package init
- ✅ `backend/pipeline/ethics_gate.py` - Two-layer gate (hard keywords + DeBERTa zero-shot), `get_classifier()` singleton, returns BLOCKED/AMBIGUOUS/APPROVED
- ✅ `backend/pipeline/classifier.py` - 3 zero-shot classifications (emotion, intent, situation); natural-language labels mapped to canonical underscore keys; reuses shared model from ethics_gate

#### Database Layer
- ✅ `backend/database.py` - SQLAlchemy connection, session management
- ✅ `backend/models.py` - 3 tables defined (Conversation, Message, Classification)
- ✅ `backend/schemas.py` - Pydantic request/response models

#### Basic API Endpoints (NOT wired to AI pipeline yet)
- ✅ `backend/routers/conversations.py` - CRUD operations
- ✅ `backend/routers/chat.py` - **Placeholder only** (returns echo, not real AI)
- ✅ `backend/main.py` - FastAPI app setup

#### Infrastructure
- ✅ Docker Compose (PostgreSQL + Backend + Frontend containers)
- ✅ Environment variables setup
- ✅ Requirements.txt with all dependencies

#### Documentation
- ✅ `CLAUDE.md` - Main AI context file
- ✅ `.claude/project_overview.md`
- ✅ `.claude/architecture.md`
- ✅ `.claude/current_status.md` (this file)

**What This Means**: We can store conversations in a database, but there's NO AI yet. The chat endpoint is fake.

---

## What's NOT Built Yet ❌ (85% of the project)

### The Entire AI Pipeline (0% complete)

**Missing Files** (these are the actual innovation):
```
backend/pipeline/          # DOESN'T EXIST YET
├── ethics_gate.py         # The core ethical gating logic
├── classifier.py          # Emotion/intent/situation detection
├── strategy.py            # Strategy selection algorithm
├── generator.py           # LLM prompt construction
├── critic.py              # Response validation
└── orchestrator.py        # Coordinates all steps
```

**Missing Strategy Files** (human-readable YAML configs):
```
backend/strategies/        # DOESN'T EXIST YET
├── blocked/
│   ├── bereavement.yaml
│   ├── high_risk.yaml
│   └── ambiguous.yaml     # ← YOU CAUGHT THIS MISSING
├── soft_persuasion/
│   ├── social_proof.yaml
│   └── authority.yaml
└── neutral/
    └── informational.yaml
```

**Missing Frontend**:
- No Chatscope UI integration
- Current frontend is empty placeholder

---

## Pipeline Flows (ALL 3 Cases)

### Flow 1: BLOCKED (Vulnerable User)

```
User: "My spouse passed away, I need to cancel our policy"
    ↓
Ethics Gate: BLOCKED (keyword: "passed away")
    ↓
Skip Classifier (waste of compute)
    ↓
Strategy Selector: "blocked/bereavement.yaml"
    ↓
LLM Generator: Empathetic response only, ZERO persuasion
    ↓
Critic: Verify no persuasive language snuck in
    ↓
Response: "I'm very sorry for your loss. Here's the cancellation process..."
```

**Key**: No classification, no persuasion, just empathy + information.

---

### Flow 2: APPROVED (Safe to Persuade)

```
User: "I'm worried about increasing my 401k with market volatility"
    ↓
Ethics Gate: APPROVED (no vulnerability detected)
    ↓
Classifier:
  - Emotion: anxiety_or_worry (0.89 confidence)
  - Intent: increase_investment (0.76)
  - Situation: positive_for_business (0.82)
    ↓
Strategy Selector: "soft_persuasion/social_proof.yaml" (emotion-driven)
    ↓
LLM Generator: "Many customers in similar situations find that..."
    ↓
Critic: Score 9.0/10, no violations
    ↓
Response: Soft persuasion with social proof framing
```

**Key**: Full pipeline, persuasion allowed but controlled by strategy YAML.

---

### Flow 3: AMBIGUOUS (← YOU CAUGHT THIS MISSING)

```
User: "Not sure what to do with my savings"
    ↓
Ethics Gate: AMBIGUOUS (context unclear, could be vulnerable)
    ↓
Strategy Selector: "blocked/ambiguous.yaml"
    ↓
LLM Generator: Ask clarifying questions, no persuasion yet
    ↓
Critic: Verify response is questioning, not persuading
    ↓
Response: "I'd be happy to help! Could you tell me more about:
           - What prompted you to think about your savings now?
           - Are you looking to grow them, or access them soon?
           - Is there anything specific you're concerned about?"
```

**Key**: When uncertain, ask questions. Never persuade ambiguous contexts.

**Implementation**:
```python
# ethics_gate.py
if "unclear" in top_label and confidence > 0.5:
    return {"decision": "AMBIGUOUS", "reason": "unclear_context"}

# strategy.py
if gate["decision"] == "AMBIGUOUS":
    return "blocked/ambiguous"  # Clarification strategy
```

**New Strategy File Needed**:
```yaml
# strategies/blocked/ambiguous.yaml
name: "Clarification Request"
principle: "When uncertain, ask questions before persuading"
tone: "Curious, helpful, non-directive"

compliant_framing:
  - "Could you tell me more about..."
  - "To help me understand, can you share..."
  - "What prompted you to think about this now?"

prohibited:
  - "You should consider..."
  - "Have you thought about..."
  - ANY persuasive framing

directives:
  - "Ask 2-3 open-ended questions"
  - "No recommendations until context is clear"
  - "Keep response brief (1 paragraph max)"
  - "Store clarification attempt in conversation metadata"

when_to_use:
  - "Ethics gate returns AMBIGUOUS"
  - "Context is genuinely unclear"

when_not_to_use:
  - "Never use as excuse to delay blocking vulnerable users"
```

**Follow-up Flow** (after clarification):
```
User: "I just lost my job and need to withdraw everything"
    ↓
Ethics Gate: BLOCKED (hardship detected in follow-up)
    ↓
Strategy: "blocked/high_risk.yaml"
    ↓
Response: Empathetic, informational only
```

---

## What's Next (Corrected Priority Order) 📋

### Day 1 Morning: Strategy Files & Ethics Gate (4 hours)

#### Task 1.1: Create Strategy YAML Files (1 hour)
**Location**: `backend/strategies/`

**Files to Create** (6 total, not 5):
```
backend/strategies/
├── blocked/
│   ├── bereavement.yaml          # Loss/death keywords
│   ├── high_risk.yaml             # General vulnerability
│   └── ambiguous.yaml             # ← NEW: Clarification workflow
├── soft_persuasion/
│   ├── social_proof.yaml          # Anxiety/fear emotions
│   └── authority.yaml             # Calm advice-seeking
└── neutral/
    └── informational.yaml         # Default safe response
```

**Template**: See architecture.md for YAML structure

**Acceptance Criteria**:
- [ ] All 6 YAML files created
- [ ] `ambiguous.yaml` focuses on asking questions
- [ ] Content is research-backed
- [ ] Files loadable with `yaml.safe_load()`

#### Task 1.2: Implement Ethics Gate (2 hours)
**Location**: `backend/pipeline/ethics_gate.py`

**New Requirements** (with AMBIGUOUS handling):
```python
def evaluate(message: str) -> dict:
    # Layer 1: Hard rules
    if any(kw in message.lower() for kw in HARD_BLOCK_KEYWORDS):
        return {"decision": "BLOCKED", "reason": f"keyword:{kw}", "confidence": 1.0}

    # Layer 2: Zero-shot
    result = classifier(message, candidate_labels=[
        "this person is vulnerable or distressed",
        "this is a routine financial inquiry",
        "the context is unclear"
    ])

    if "vulnerable" in top_label and score > 0.6:
        return {"decision": "BLOCKED", ...}
    elif "unclear" in top_label and score > 0.5:
        return {"decision": "AMBIGUOUS", ...}  # ← NEW
    else:
        return {"decision": "APPROVED", ...}
```

**Test Cases** (3 scenarios now):
```python
# Should BLOCK
assert evaluate("My spouse died")["decision"] == "BLOCKED"

# Should APPROVE
assert evaluate("I want to increase my 401k")["decision"] == "APPROVED"

# Should be AMBIGUOUS
assert evaluate("Not sure what to do")["decision"] == "AMBIGUOUS"
```

**Acceptance Criteria**:
- [ ] Returns one of 3 decisions: BLOCKED, APPROVED, AMBIGUOUS
- [ ] Hard keywords always BLOCKED
- [ ] Ambiguous threshold: 0.5 confidence
- [ ] Model loads lazily

#### Task 1.3: Update Orchestrator Flow (for AMBIGUOUS) (30 min)
**Location**: `backend/pipeline/orchestrator.py` (will be created later)

**Add AMBIGUOUS Handling**:
```python
async def run_pipeline(message: str) -> dict:
    gate = ethics_gate.evaluate(message)

    if gate["decision"] == "BLOCKED":
        # Empathetic response, skip classifier
        ...

    elif gate["decision"] == "AMBIGUOUS":
        # Ask clarifying questions, skip classifier
        strategy_path = "blocked/ambiguous"
        strategy_config = load_strategy(strategy_path)
        response = generator.generate(message, {}, strategy_config)
        # Note: Skip critic for clarification (always safe)
        return {"response": response, "debug": {...}}

    else:  # APPROVED
        # Full pipeline
        classification = classifier.classify(message)
        ...
```

**Acceptance Criteria**:
- [ ] AMBIGUOUS triggers clarification workflow
- [ ] Skips classifier (no need to analyze unclear context)
- [ ] Skips critic (clarification questions are always safe)
- [ ] Logs AMBIGUOUS decision to database

---

### Day 1 Afternoon: Classifier & Strategy Selector (3 hours)

#### Task 1.4: Implement Classifier (2 hours)
**Location**: `backend/pipeline/classifier.py`

**Note**: Only runs if gate = APPROVED (not for BLOCKED or AMBIGUOUS)

- [ ] Emotion classification (8 labels)
- [ ] Intent classification (10 labels)
- [ ] Situation classification (3 labels)
- [ ] Return dict with all 3 + confidence scores

**Acceptance Criteria**:
- [ ] Returns structured dict
- [ ] Reuses model from ethics_gate
- [ ] Only called when gate = APPROVED

#### Task 1.5: Implement Strategy Selector (1 hour)
**Location**: `backend/pipeline/strategy.py`

**Updated Selection Logic** (includes AMBIGUOUS):
```python
def select_strategy(gate: dict, classification: dict) -> str:
    # Step 1: Handle gate decisions first
    if gate["decision"] == "BLOCKED":
        if "bereavement" in gate.get("reason", ""):
            return "blocked/bereavement"
        return "blocked/high_risk"

    if gate["decision"] == "AMBIGUOUS":
        return "blocked/ambiguous"  # ← NEW

    # Step 2: Compliance overrides (for APPROVED only)
    if classification["intent"] in ["cancel_policy", "hardship_withdrawal"]:
        return "blocked/high_risk"  # Override even if APPROVED

    # Step 3: Emotion-first selection
    emotion = classification["emotion"]
    if emotion in ["anxiety_or_worry", "fear_or_apprehension"]:
        return "soft_persuasion/social_proof"
    if emotion == "neutral_or_calm" and classification["intent"] == "seek_advice":
        return "soft_persuasion/authority"

    return "neutral/informational"
```

**Acceptance Criteria**:
- [ ] AMBIGUOUS always returns "blocked/ambiguous"
- [ ] Compliance overrides work
- [ ] Emotion-first logic implemented
- [ ] YAML loader works

---

### Day 1 Evening: Frontend Integration (30 minutes)
- [ ] Install Chatscope
- [ ] Replace App.jsx
- [ ] Wire to POST /api/v1/chat
- [ ] Test in browser

---

### Day 2 Morning: Generator & Critic (4 hours)
- [ ] LLM Generator (2h)
- [ ] Critic (2h)

---

### Day 2 Afternoon: Orchestrator & Integration (3 hours)
- [ ] Orchestrator with AMBIGUOUS flow (2h)
- [ ] Wire into chat.py (1h)

---

### Day 2 Evening: Testing & Demo (2 hours)

**Test Cases** (4 scenarios now):

1. **BLOCKED - Bereavement**
   ```
   Input: "My spouse passed away"
   Expected: Empathy only, no persuasion
   ```

2. **AMBIGUOUS - Unclear Context**
   ```
   Input: "Not sure what to do with my savings"
   Expected: Clarifying questions, no persuasion
   ```

3. **APPROVED - Anxiety**
   ```
   Input: "Worried about market volatility"
   Expected: Social proof strategy
   ```

4. **APPROVED - Calm Advice Seeking**
   ```
   Input: "What do experts recommend?"
   Expected: Authority strategy
   ```

---

## Known Issues / Blockers

**None currently** - Ready to start implementation

---

## File Structure (Reality Check)

```
/Users/Rounak/chatbot/
├── backend/
│   ├── ✅ database.py
│   ├── ✅ models.py
│   ├── ✅ schemas.py
│   ├── ✅ main.py
│   ├── routers/
│   │   ├── ✅ conversations.py
│   │   └── ⚠️  chat.py (placeholder, NOT real AI yet)
│   ├── ❌ pipeline/              # DOESN'T EXIST (0% done)
│   │   ├── ❌ ethics_gate.py
│   │   ├── ❌ classifier.py
│   │   ├── ❌ strategy.py
│   │   ├── ❌ generator.py
│   │   ├── ❌ critic.py
│   │   └── ❌ orchestrator.py
│   └── ❌ strategies/            # DOESN'T EXIST
│       ├── ❌ blocked/
│       │   ├── ❌ bereavement.yaml
│       │   ├── ❌ high_risk.yaml
│       │   └── ❌ ambiguous.yaml     # ← NEW
│       ├── ❌ soft_persuasion/
│       └── ❌ neutral/
├── frontend/
│   └── ❌ src/App.jsx (needs Chatscope)
├── ✅ docker-compose.yml
├── ✅ CLAUDE.md
└── .claude/
    ├── ✅ project_overview.md
    ├── ✅ architecture.md
    └── ✅ current_status.md
```

**Legend**:
- ✅ Complete and working
- ⚠️ Exists but placeholder only
- ❌ Doesn't exist yet (needs to be built)

---

## Progress Tracking (Honest)

**Estimated Total Hours**: 14-16 hours
**Hours Completed**: ~2 hours (infrastructure only)
**Hours Remaining**: ~12-14 hours
**Actual Progress**: 15% (not 60%!)

**Day 1 Goals**:
- [ ] 6 Strategy YAML files (1h)
- [ ] Ethics Gate with AMBIGUOUS (2h)
- [ ] Classifier (2h)
- [ ] Strategy Selector with AMBIGUOUS (1h)
- [ ] Frontend (30min)

**Day 2 Goals**:
- [ ] Generator (2h)
- [ ] Critic (2h)
- [ ] Orchestrator with AMBIGUOUS flow (2h)
- [ ] Integration & Testing (2h)
- [ ] Demo Prep (1h)

---

## Summary of Fixes

**What You Caught**:
1. ✅ AMBIGUOUS workflow was missing → Added full clarification flow
2. ✅ Progress was wrong (60% → 15%) → Fixed to be realistic

**What's New**:
- `strategies/blocked/ambiguous.yaml` - Clarification strategy
- AMBIGUOUS handling in ethics_gate, strategy selector, orchestrator
- Test case for AMBIGUOUS scenario
- Honest progress tracking (we've built infrastructure, not AI)

---

**Status**: Ready to start Day 1 implementation
**Next Action**: Create 6 strategy YAML files (including ambiguous.yaml)
