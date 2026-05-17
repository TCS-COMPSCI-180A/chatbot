# Updated System Design: TCS Banking Ethical Persuasion Chatbot

**Version**: 2.0 — Agentic LangGraph Architecture with Document Analysis
**Date**: 2026-04-09
**Authors**: Team Avengers (COMPSCI 180A/B)
**Sponsor**: Tata Consultancy Services

---

## Table of Contents

1. [Domain Scope: Banking Only](#1-domain-scope-banking-only)
2. [What Changed from v1](#2-what-changed-from-v1)
3. [Architecture Overview](#3-architecture-overview)
4. [Full Graph Workflow](#4-full-graph-workflow)
5. [Node-by-Node Specification](#5-node-by-node-specification)
6. [Tool Functions](#6-tool-functions)
7. [State Schema](#7-state-schema)
8. [Updated Taxonomies](#8-updated-taxonomies)
9. [Strategy File Structure](#9-strategy-file-structure)
10. [Work Split: 5 Members](#10-work-split-5-members)

---

## 1. Domain Scope: Banking Only

This version narrows the domain from general financial services to **retail banking** exclusively.

### In Scope

| Category | Examples |
|---|---|
| Deposit accounts | Checking, savings, money market, CDs |
| Lending | Personal loans, auto loans, mortgages, HELOCs |
| Credit products | Credit cards, credit limit changes |
| Account operations | Transactions, wire transfers, ACH, overdraft |
| Banking fees | Overdraft fees, maintenance fees, dispute resolution |
| Credit reporting | Credit score, utilization, payment history (from customer's own report) |

### Out of Scope (Explicitly Removed)

| Category | Reason |
|---|---|
| 401k / retirement accounts | Investment management domain |
| Life / health insurance | Insurance domain |
| Mutual funds, ETFs, stocks | Brokerage domain |
| General wealth planning | Advisory / investment domain |
| Tax advice | Accounting domain |

---

## 2. What Changed from v1

| Component | v1 (Original) | v2 (This Design) |
|---|---|---|
| Orchestration | Custom `orchestrator.py` with if/else | LangGraph `StateGraph` with typed state |
| Node order | Gate first, classifier after | Classifier first, gate second — classifier context informs gate |
| Gate | DeBERTa zero-shot (no reasoning) | DeBERTa (hard rules) + document-type awareness |
| Gate decisions | BLOCKED / APPROVED / AMBIGUOUS | PASS / BLOCKED (ambiguous defaults to PASS + neutral strategy) |
| Classifier | 3 DeBERTa zero-shot calls, single message | LLM with chain-of-thought, multi-turn history |
| Document analysis | Separate parallel node | Merged into Classifier Agent — runs inline when `has_document` |
| Strategy | Rule-based lookup | LLM agent reading YAML + document insights |
| Critic | DeBERTa zero-shot scoring | LLM with chain-of-thought, regulation citations |
| Document support | None | Full RAG: parse → embed → retrieve → ground response |
| Tool access | None | Direct `@tool` functions (no server) — called natively by LangGraph agents |
| Domain | General financial services | Banking only |
| Strategy files | 6 YAML files | 9 YAML files (adds `document_grounded/` category) |
| Parallel execution | Sequential only | Sequential — classifier handles doc analysis inline |

### What Did NOT Change

- **Ethics gate remains hard-coded + SLM** — not LLM-powered. This is intentional. The gate must be deterministic and manipulation-proof. A persuasion-based prompt injection cannot convince a keyword checker to approve a message containing "bankruptcy."
- **Bounded rewrite (max 1)** — still enforced in the critic loop.
- **YAML strategy files** — still human-editable by compliance teams without code changes.
- **Full PostgreSQL audit trail** — every decision, every score, every rewrite logged.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Chatscope)                                       │
│  POST /api/v1/chat  { message, document?, session_id }              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND                                                     │
│                                                                     │
│  chat.py router → LangGraph app.invoke(state)                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  LANGGRAPH STATE GRAPH                                        │  │
│  │                                                               │  │
│  │  entry → classifier → ethics_gate → [routing] →              │  │
│  │  generator → critic → [loop or END] → logger                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  POSTGRESQL + PGVECTOR                                        │  │
│  │  - conversations, messages, classifications tables            │  │
│  │  - document_chunks table (pgvector)                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI 0.109+ |
| Graph orchestration | LangGraph 0.2+ |
| SLM (ethics gate, doc classify) | DeBERTa v3 (`MoritzLaurer/deberta-v3-base-zeroshot-v2.0`) |
| LLM (all agents) | GPT-4o-mini (OpenAI) |
| PDF parsing | PDFPlumber |
| OCR | Tesseract (pytesseract) |
| Vector store | pgvector (PostgreSQL extension) |
| Embeddings | `text-embedding-3-small` (OpenAI) |
| ORM | SQLAlchemy 2.0 |
| Frontend | React 18 + Chatscope UI Kit |

---

## 4. Full Graph Workflow

### Graph Diagram

```
INPUT
{ message: str, document?: bytes, session_id: str }
         │
         ▼
┌─────────────────────────────────────────────────────┐
│   ENTRY NODE                                        │
│                                                     │
│   - Load session metadata                           │
│   - Load chat_history from DB                       │
│   - Set has_document flag                           │
│   - If document: parse + classify + extract + embed │
│     (PDFPlumber / pytesseract → document_chunks)    │
│                                                     │
│   Writes to state:                                  │
│   - chat_history                                    │
│   - has_document                                    │
│   - document_text, document_type                    │
│   - document_figures, document_doc_id               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│   CLASSIFIER AGENT  (LLM + Tools)                   │
│                                                     │
│   Tools:                                            │
│   - get_conversation_history()                      │
│   - lookup_banking_regulation()                     │
│   - retrieve_relevant_chunks()    (if has_document) │
│   - get_current_banking_rates()   (if has_document) │
│   - calculate_banking_metrics()   (if has_document) │
│                                                     │
│   Output:                                           │
│   - emotion (Plutchik)                              │
│   - intent (banking taxonomy)                       │
│   - situation (business perspective)                │
│   - classification_reasoning                        │
│   - document_insights (list, if has_document)       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│   ETHICS GATE NODE  (deterministic — NOT LLM)        │
│                                                      │
│   Layer 1: Hard keyword rules (instant, 100% recall) │
│   Layer 2: DeBERTa v3 zero-shot SLM                  │
│   Layer 3: Document-type check                       │
│     - foreclosure_notice → BLOCKED                   │
│     - bankruptcy_filing  → BLOCKED                   │
│                                                      │
│   Output: PASS | BLOCKED                             │
└────────────┬──────────────────────────────┬──────────┘
             │                              │
           PASS                          BLOCKED
             │                              │
             ▼                              ▼
┌────────────────────────┐    ┌─────────────────────────┐
│   STRATEGY AGENT (LLM) │    │  load blocked/ YAML     │
│                        │    │  set strategy_config     │
│   Priority order:      │    └──────────────┬──────────┘
│   1. Compliance        │                   │
│      overrides         │                   │
│   2. Document-grounded │                   │
│      path (if doc)     │                   │
│   3. Emotion-first     │                   │
│   4. Default neutral   │                   │
│                        │                   │
│   Output:              │                   │
│   - strategy_path      │                   │
│   - strategy_config    │                   │
│   - strategy_reasoning │                   │
└──────────┬─────────────┘                   │
           └─────────────────┬───────────────┘
                             │
                             ▼
          ┌──────────────────────────────────────┐
          │   GENERATOR AGENT  (GPT-4o-mini)     │
          │                                      │
          │   Inputs:                            │
          │   - strategy_config (YAML)           │
          │   - document_insights (if present)   │
          │   - emotion, intent, chat_history    │
          │                                      │
          │   If document present:               │
          │   MUST cite ≥2 specific figures      │
          │   CANNOT use generic statistics      │
          │                                      │
          │   Output: response_draft             │
          └───────────────────┬──────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │   CRITIC AGENT  (LLM + chain-of-thought)
          │                                      │
          │   Checks:                            │
          │   - Coercive / manipulative language │
          │   - Prohibited framing (from YAML)   │
          │   - FCA COBS 4.5.2: no false urgency │
          │   - BLOCKED context: zero persuasion │
          │   - Doc present: figures cited ≥2    │
          │   - Doc present: no fabricated data  │
          │                                      │
          │   Score < 7.0 → rewrite (max 1 time) │
          │   Score ≥ 7.0 → pass                 │
          └────────┬──────────────────┬──────────┘
                   │                  │
                passed             failed
             (score≥7 or         (score<7,
              rewrite=1)          rewrite=0)
                   │                  │
                   │                  ▼
                   │       ┌──────────────────────┐
                   │       │  GENERATOR (rewrite) │
                   │       │  temperature=0.5     │
                   │       └──────────┬───────────┘
                   │                  │
                   │                  ▼
                   │       ┌──────────────────────┐
                   │       │  CRITIC (re-score)   │
                   │       └──────────┬───────────┘
                   │                  │
                   └─────────┬────────┘
                             │
                             ▼
          ┌──────────────────────────────────────┐
          │   DB LOGGER NODE                     │
          │                                      │
          │   Logs to classifications table:     │
          │   - gate_decision + reason           │
          │   - emotion, intent, situation       │
          │   - strategy_path                    │
          │   - critic_score + violations        │
          │   - rewrite_count                    │
          │   - document_type (if present)       │
          │   - full debug_trace JSON            │
          └───────────────────┬──────────────────┘
                              │
                              ▼
                       FINAL RESPONSE
```



### Routing Logic (Conditional Edges)

```python
# After ethics gate
def route_after_gate(state) -> str:
    if state["gate_decision"] == "BLOCKED":
        return "generator"        # strategy_config already set to blocked/ YAML
    return "strategy"             # PASS: proceed to strategy selection

# After critic
def route_after_critic(state) -> str:
    passed = state["critic_score"] >= 7.0
    at_limit = state["rewrite_count"] >= 1
    if passed or at_limit:
        return "logger"
    return "generator"            # trigger one rewrite
```

---

## 5. Node-by-Node Specification

### Node 1: Entry Node

| Property | Value |
|---|---|
| Type | Deterministic function (no LLM) |
| Runs | Always, first |
| Input | `message`, `document_bytes`, `session_id` |
| Output | `chat_history`, `has_document`, `document_text`, `document_type`, `document_figures`, `document_doc_id` |

**Responsibilities:**
- Load `chat_history` from the database for the current session
- If `document_bytes` is present: parse (PDFPlumber or pytesseract), classify document type (DeBERTa v3), extract key figures, chunk and embed into pgvector
- Set `has_document = True/False` in state

**Document types recognized:**

```
bank_statement          → balances, fees, transaction patterns
loan_agreement          → APR, principal, term, payment, penalties
mortgage_statement      → P&I breakdown, escrow, remaining balance
credit_card_statement   → balance, APR, utilization, minimum payment
cd_savings_statement    → balance, APY, maturity date, interest earned
credit_report           → FICO score, utilization %, derogatory marks
foreclosure_notice      → triggers BLOCKED at ethics gate
bankruptcy_filing       → triggers BLOCKED at ethics gate
```

---

### Node 2: Classifier Agent

| Property | Value |
|---|---|
| Type | LLM agent with tool access |
| Runs | Always, after Entry Node |
| Input | `message`, `chat_history`, `session_id`, `has_document` |
| Output | `emotion`, `intent`, `situation`, `classification_reasoning`, `document_insights` (if doc) |
| Tools | `get_conversation_history`, `lookup_banking_regulation`, `retrieve_relevant_chunks` (if doc), `get_current_banking_rates` (if doc), `calculate_banking_metrics` (if doc) |

The classifier reads full conversation history before classifying, so emotion and intent reflect multi-turn context, not just the current message. When a document is present, it also performs document analysis inline — retrieving relevant chunks, computing metrics, and producing `document_insights` for the generator.

**Example — multi-turn context matters:**
```
Turn 1: "What are your mortgage rates?"  (neutral)
Turn 2: "I'm worried about my payment"   → fear_or_apprehension (about existing loan)
                                          without history → anxiety_or_worry (wrong)
```

---

### Node 3: Ethics Gate Node

| Property | Value |
|---|---|
| Type | Hard rules + DeBERTa v3 SLM (deterministic — NOT LLM) |
| Runs | Always, after Classifier |
| Input | `message`, `document_type` (if present), `intent` (from classifier) |
| Output | `gate_decision`, `gate_reason`, `gate_confidence` |
| Tools | None |

**Decision layers (in order):**

1. Document type hard block (`foreclosure_notice`, `bankruptcy_filing` → BLOCKED immediately)
2. Hard keyword match in message (see keyword list in Section 8)
3. Compliance-blocked intents from classifier (`report_fraudulent_activity`, `close_bank_account`, `request_loan_modification` → BLOCKED)
4. DeBERTa v3 zero-shot: `["vulnerable/distressed", "routine banking inquiry"]`
5. Confidence threshold: vulnerable > 0.6 → BLOCKED; else PASS

**Output values:** `PASS` | `BLOCKED` (AMBIGUOUS removed — ambiguous cases now default to PASS with neutral/informational strategy)

---

### Node 4: Strategy Agent

| Property | Value |
|---|---|
| Type | LLM |
| Runs when | `gate_decision == "PASS"` |
| Input | `emotion`, `intent`, `situation`, `has_document`, `document_type` |
| Output | `strategy_path`, `strategy_config`, `strategy_reasoning` |
| Tools | None |

When `gate_decision == "BLOCKED"`, this node is skipped — the Entry/Gate path directly sets `strategy_config` from the appropriate `blocked/` YAML.

**Selection priority:**

```
1. Compliance overrides (always win):
   - intent == "report_fraudulent_activity" → blocked/fraud_report
   - intent == "close_bank_account"         → blocked/high_risk (no retention)
   - intent == "request_loan_modification"  → blocked/financial_hardship

2. Document-grounded path:
   - has_document == True AND
     intent in ["seek_banking_advice", "request_explanation", "general_banking_inquiry"]
       → document_grounded/statement_analysis  (bank_statement, credit_card_statement)
       → document_grounded/loan_analysis       (loan_agreement, mortgage_statement)

3. Emotion-first selection:
   - anxiety_or_worry / fear_or_apprehension  → soft_persuasion/social_proof
   - neutral_or_calm + seek_banking_advice    → soft_persuasion/authority
   - trust_or_acceptance + loyal indicators  → soft_persuasion/reciprocity

4. Default:
   → neutral/informational
```

---

### Node 5: Generator Agent

| Property | Value |
|---|---|
| Type | GPT-4o-mini |
| Input | `strategy_config`, `document_insights`, `emotion`, `intent`, `chat_history`, `message` |
| Output | `response_draft` |
| Temperature | 0.7 (0.5 on rewrite) |
| Max tokens | 350 |

**Critical constraint when document is present:**
The system prompt explicitly requires citing at least 2 specific figures from `document_insights`. Generic statistics ("many customers find...") are prohibited when specific document data exists.

---

### Node 6: Critic Agent

| Property | Value |
|---|---|
| Type | LLM with chain-of-thought reasoning |
| Input | `response_draft`, `strategy_config`, `gate_decision`, `has_document`, `document_insights` |
| Output | `critic_score`, `critic_violations`, `critic_reasoning` |
| Pass threshold | 7.0 / 10.0 |
| Max rewrites | 1 |

**Checks performed:**

```
Standard checks (all responses):
  - Coercive or manipulative language         (-3.0)
  - Fear tactics or false urgency             (-3.0)
  - Persuasion in BLOCKED context             (-10.0, instant fail)
  - Violates YAML prohibited list             (-2.0)

Document-specific checks (when has_document):
  - Fabricated figures not in document        (-3.0)
  - Generic advice when specific data exists  (-2.0)
  - Failed to cite ≥2 document figures        (-1.5)
```

---

### Node 7: DB Logger Node

Logs the full state to the `classifications` table. Unchanged from v1 schema, with two new columns: `document_type` and `document_doc_id`.

---

## 6. Tool Functions

Tools are plain Python functions decorated with `@tool` from LangChain and bound directly to LLM agents via `.bind_tools()`. There is no separate MCP server — tools are imported and called natively within the LangGraph graph.

```python
from langchain_core.tools import tool

tools = [get_conversation_history, lookup_banking_regulation, retrieve_relevant_chunks, ...]
llm_with_tools = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)
```

### Category 1: Document Tools

```python
parse_pdf_document(file_bytes: bytes) -> str
  # Extract raw text from a PDF. Uses PDFPlumber; falls back to OCR if no text layer.

ocr_image_document(file_bytes: bytes) -> str
  # Extract text from JPG/PNG/TIFF via Tesseract. Preprocesses for contrast/deskew.

classify_banking_document(text: str) -> str
  # Identify document type via DeBERTa v3 zero-shot.
  # Returns: bank_statement | loan_agreement | mortgage_statement |
  #          credit_card_statement | cd_savings_statement | credit_report |
  #          foreclosure_notice | bankruptcy_filing | unknown

extract_banking_figures(text: str, doc_type: str) -> dict
  # Pull structured key figures using regex + LLM hybrid.
  # bank_statement:        { current_balance, avg_balance, total_fees, overdraft_total }
  # loan_agreement:        { principal, apr, monthly_payment, term_months }
  # mortgage_statement:    { principal_balance, interest_rate, monthly_payment, escrow_balance }
  # credit_card_statement: { balance, apr, min_payment, credit_limit, utilization_pct }

chunk_and_embed_document(text: str, session_id: str) -> str
  # Split into 512-token chunks (50-token overlap), embed with text-embedding-3-small,
  # store in pgvector document_chunks table. Returns doc_id UUID.

retrieve_relevant_chunks(query: str, doc_id: str, top_k: int = 4) -> list[str]
  # Cosine similarity search over pgvector. Embeds query on the fly. Used by Classifier Agent.
```

### Category 2: Banking Metrics Tools

```python
calculate_banking_metrics(figures: dict, doc_type: str) -> dict
  # Pure calculation — no LLM. Derives metrics from extracted figures.
  # bank_statement:        { annualized_fees, fee_pct_of_balance, overdraft_risk_score }
  # loan_agreement:        { total_interest_remaining, break_even_months_to_refinance }
  # credit_card_statement: { monthly_interest_cost, payoff_months_at_min_payment,
  #                          utilization_category: "good|fair|poor" }

get_current_banking_rates(product_type: str) -> dict
  # Static lookup table updated quarterly. Not real-time. Always disclose illustrative nature.
  # "hysa"          → { apy: 4.2, source: "national_avg_2026" }
  # "cd_12_month"   → { apy: 4.8 }
  # "mortgage_30yr" → { rate: 6.9 }
  # "personal_loan" → { apr_range: [9.5, 24.0] }
```

### Category 3: Context Tools

```python
get_conversation_history(session_id: str, turns: int = 5) -> list[dict]
  # SQLAlchemy query. Returns { role, content, created_at } dicts, most recent first.
  # Used by Classifier Agent to reason over full conversation context.

get_session_document_id(session_id: str) -> str | None
  # Returns doc_id if a document was uploaded earlier in this session, else None.
  # Supports multi-turn: user uploads once, asks multiple questions across turns.
```

### Category 4: Knowledge & Audit Tools

```python
lookup_banking_regulation(topic: str) -> str
  # Static knowledge base. Returns short excerpt of relevant regulatory guidance.
  # "overdraft_fees" → FCA/CFPB fee disclosure guidance
  # "fca_cobs_4"     → FCA COBS 4.5 communications rules
  # "fair_lending"   → Equal Credit Opportunity Act summary
  # Used by Classifier and Critic to cite specific violations.

log_pipeline_decision(session_id: str, node: str, decision: dict) -> None
  # Write structured decision record to audit log (debug_trace JSON column).
  # Called by each node to create granular trail beyond the DB logger.
```

---

## 7. State Schema

```python
from typing import TypedDict, Optional, Literal

class BankingPipelineState(TypedDict):

    # ── Input ────────────────────────────────────────────────────
    message: str
    session_id: str
    document_bytes: Optional[bytes]     # raw upload, None if no doc

    # ── Entry Node ───────────────────────────────────────────────
    chat_history: list[dict]            # loaded from DB by Entry Node
    has_document: bool
    document_text: Optional[str]        # full parsed text
    document_type: Optional[str]        # bank_statement | loan_agreement | ...
    document_figures: Optional[dict]    # extracted key numbers
    document_doc_id: Optional[str]      # pgvector doc UUID

    # ── Classifier ───────────────────────────────────────────────
    emotion: Optional[str]
    intent: Optional[str]
    situation: Optional[str]
    classification_reasoning: Optional[str]
    document_insights: Optional[list]   # grounded observations (if has_document)

    # ── Ethics Gate ──────────────────────────────────────────────
    gate_decision: Literal["PASS", "BLOCKED"]
    gate_reason: str
    gate_confidence: float

    # ── Strategy ─────────────────────────────────────────────────
    strategy_path: Optional[str]
    strategy_config: Optional[dict]
    strategy_reasoning: Optional[str]

    # ── Generation & Critic ──────────────────────────────────────
    response_draft: Optional[str]
    critic_score: Optional[float]
    critic_violations: Optional[list]
    critic_reasoning: Optional[str]
    rewrite_count: int                  # enforced max: 1

    # ── Output ───────────────────────────────────────────────────
    final_response: str
    debug_trace: dict                   # full audit log, written to DB
```

---

## 8. Updated Taxonomies

### Emotion Labels (Plutchik — unchanged)

```python
EMOTION_LABELS = [
    "anxiety_or_worry",         # uncertainty about a financial decision
    "fear_or_apprehension",     # specific fear about existing obligation
    "neutral_or_calm",          # rational inquiry
    "anticipation_or_interest", # exploring new banking options
    "sadness_or_grief",         # loss-related
    "joy_or_contentment",       # positive financial news
    "anger_or_frustration",     # service complaint, fee dispute
    "trust_or_acceptance"       # confidence in the bank
]
```

### Banking Intent Labels (Updated — investment/insurance removed)

```python
BANKING_INTENT_LABELS = [
    # Account Management
    "check_account_balance",
    "review_transaction_history",
    "dispute_transaction",
    "close_bank_account",
    "open_new_account",

    # Lending
    "apply_for_personal_loan",
    "apply_for_auto_loan",
    "apply_for_mortgage",
    "inquire_about_loan_terms",
    "request_loan_modification",
    "refinance_loan",

    # Credit Cards
    "inquire_about_credit_card",
    "dispute_credit_charge",
    "request_credit_limit_increase",

    # Savings & CDs
    "inquire_about_cd_rates",
    "inquire_about_interest_rates",
    "make_deposit_or_transfer",

    # Fees & Issues
    "dispute_bank_fee",
    "overdraft_inquiry",
    "request_fee_waiver",
    "report_fraudulent_activity",

    # General
    "general_banking_inquiry",
    "seek_banking_advice",
    "request_explanation"
]
```

### Hard Block Keywords (Banking-Scoped)

```python
HARD_BLOCK_KEYWORDS = [
    # Financial hardship
    "can't afford", "can't make payments", "behind on payments",
    "about to default", "missed payments", "facing foreclosure",
    "foreclosure notice", "bankruptcy", "filing for bankruptcy",
    "eviction", "losing my home", "wage garnishment",

    # Life events
    "passed away", "death", "died", "funeral", "bereavement",
    "lost my job", "laid off",

    # Crisis
    "can't pay rent", "desperate", "going through divorce",
]

# Compliance-blocked intents (never persuade even if gate = APPROVED)
COMPLIANCE_BLOCKED_INTENTS = [
    "report_fraudulent_activity",   # escalate only, no advice, no upsell
    "close_bank_account",           # no retention attempts
    "request_loan_modification",    # hardship signal — informational only
]
```

---

## 9. Strategy File Structure

```
backend/strategies/
├── blocked/
│   ├── financial_hardship.yaml    # can't pay, bankruptcy, foreclosure
│   ├── bereavement.yaml           # death, estate management
│   └── fraud_report.yaml          # fraudulent activity → escalate only
│
├── soft_persuasion/
│   ├── social_proof.yaml          # anxiety/fear → peer data reassurance
│   ├── authority.yaml             # calm advice-seeking → expert guidance
│   └── reciprocity.yaml           # loyal customer → relevant product offer
│
├── document_grounded/             # NEW: used when document is present
│   ├── statement_analysis.yaml    # bank/CC statement → fee/savings advice
│   └── loan_analysis.yaml         # loan/mortgage doc → rate/refinance advice
│
└── neutral/
    └── informational.yaml         # default — factual, no persuasion
```

### New Strategy Type: `document_grounded`

```yaml
# strategies/document_grounded/statement_analysis.yaml
name: "Statement-Grounded Advice"
principle: "Advice grounded in the customer's actual data is more trusted and actionable than generic statistics"
tone: "Analytical, specific, supportive — like a trusted advisor who read your statement"

compliant_framing:
  - "Based on your statement, [specific figure]..."
  - "Your statement shows [X], which means..."
  - "Comparing your current [rate/balance] to available options..."
  - "Over the past [period] in your account, [observation]..."

prohibited:
  - "Many customers find that..."       # generic — use their actual data
  - "Statistics show..."                # generic — cite their document
  - Any figure not present in document_insights
  - Recommendations without tying them to a specific problem in the document

directives:
  - "Cite at least 2 specific figures from the document"
  - "Provide 2-3 numbered action items"
  - "Each action item must reference the specific document evidence"
  - "Include approximate savings or impact where calculable"
  - "End with one open question to confirm the customer's priority"

when_to_use:
  - "Document present AND intent is seek_banking_advice, request_explanation, or general_banking_inquiry"

when_not_to_use:
  - "Gate is BLOCKED"
  - "Document present but user is asking something unrelated to the document"
```

---

## 10. Work Split: 5 Members

The work is divided into 5 parallel tracks. Each track is independently implementable — tracks only converge at integration (Week 3). The division is roughly equal in effort and complexity.

---

### Member 1 — LangGraph Orchestration & Graph Architecture

**Core responsibility**: Build the LangGraph state graph, define all nodes, edges, conditional routing, and parallel execution. This is the backbone that everyone else's work plugs into.

**Deliverables:**

```
backend/
├── graph/
│   ├── __init__.py
│   ├── state.py              # BankingPipelineState TypedDict
│   ├── graph.py              # StateGraph definition, all edges, compile()
│   ├── routing.py            # route_after_gate(), route_after_critic()
│   └── runner.py             # run_pipeline() replaces orchestrator.py
```

**Tasks:**
- Define `BankingPipelineState` TypedDict (Section 7)
- Set up `StateGraph`, register all 7 nodes as stubs initially
- Implement conditional edges: `route_after_gate` (PASS → strategy, BLOCKED → generator), `route_after_critic` (pass/fail/rewrite)
- Wire `graph.py` into `backend/routers/chat.py` (replace orchestrator call)
- Write integration test: run full graph with mock nodes, verify state flows correctly
- Maintain graph visualization export (LangGraph can export Mermaid diagrams)

**Dependencies on others**: Needs stub interfaces from each other member (function signatures, not implementations). Start with mock nodes that return hardcoded state.

**Key note**: No parallel fanout needed — document analysis is now merged into the Classifier Agent node. The graph is fully sequential: entry → classifier → gate → strategy → generator → critic → logger.

---

### Member 2 — Classifier Agent + Ethics Gate

**Core responsibility**: Build the Classifier Agent (runs first) and port the deterministic Ethics Gate (runs second). The classifier now runs before the gate so that intent context can inform the gate's compliance-blocked intent check.

**Deliverables:**

```
backend/
├── agents/
│   ├── __init__.py
│   ├── classifier_agent.py   # LLM agent: emotion, intent, situation, doc_insights
│   └── ethics_gate.py        # Hard rules + DeBERTa + compliance intent check
```

**Tasks:**
- Build classifier agent using LangChain's tool-calling pattern (`bind_tools`)
- Bind tools: `get_conversation_history`, `lookup_banking_regulation`, `retrieve_relevant_chunks` (if doc), `get_current_banking_rates` (if doc), `calculate_banking_metrics` (if doc)
- Classifier produces `document_insights` inline when `has_document == True` (no separate doc analysis node)
- Port ethics gate from v1 (`pipeline/ethics_gate.py`) to new path
- Add compliance-blocked intent check: if classifier returns `report_fraudulent_activity`, `close_bank_account`, or `request_loan_modification` → BLOCKED
- Add document-type awareness: `foreclosure_notice` and `bankruptcy_filing` → BLOCKED
- Update hard block keywords to banking scope (Section 8)
- Remove AMBIGUOUS state — replace with PASS + neutral/informational strategy
- Update emotion labels (unchanged), intent labels (banking-scoped, Section 8), situation labels
- Write unit tests for both PASS and BLOCKED gate decisions
- Write unit tests for classifier: verify multi-turn context changes classification

**Key difference from v1**: Classifier runs before the gate. It calls `get_conversation_history()` and optionally document tools, so both emotion/intent and `document_insights` are fully populated before the gate evaluates compliance.

**Example behavior to test:**
```
Turn 1: "What are your mortgage rates?"  (neutral)
Turn 2: "I'm worried about my payment"   (with history: fear_or_apprehension about loan)
                                          (without history: anxiety_or_worry — wrong)
```

---

### Member 3 — Document Ingestion + Tool Functions

**Core responsibility**: Build the document processing pipeline (Entry Node) and implement all `@tool`-decorated functions that the Classifier Agent calls. There is no separate Document Analysis Agent — the Classifier handles analysis inline using these tools.

**Deliverables:**

```
backend/
├── document/
│   ├── __init__.py
│   ├── ingestion.py                  # parse, classify, extract, embed (called by Entry Node)
│   ├── extractors.py                 # doc-type-specific figure extraction
│   └── retrieval.py                  # pgvector chunk retrieval
├── tools/
│   ├── __init__.py
│   ├── document_tools.py             # @tool: parse, classify, extract, embed, retrieve
│   ├── metrics_tools.py              # @tool: calculate_banking_metrics, get_current_rates
│   ├── context_tools.py              # @tool: get_conversation_history, get_session_doc_id
│   └── audit_tools.py               # @tool: log_pipeline_decision
```

**New database table:**
```sql
CREATE TABLE document_chunks (
    id          SERIAL PRIMARY KEY,
    doc_id      UUID NOT NULL,
    session_id  VARCHAR(255),
    chunk_index INTEGER,
    chunk_text  TEXT,
    embedding   vector(1536),         -- text-embedding-3-small
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops);
```

**Tasks:**
- Implement `parse_pdf_document` using PDFPlumber (fallback to pytesseract if no text layer)
- Implement `ocr_image_document` using pytesseract (preprocess for contrast/deskew)
- Implement `classify_banking_document` using DeBERTa zero-shot (reuse SLM instance from gate)
- Implement `extract_banking_figures` for each document type (regex + LLM hybrid)
- Implement `chunk_and_embed_document`: 512-token chunks, 50-token overlap, embed with `text-embedding-3-small`, store in pgvector
- Implement `retrieve_relevant_chunks`: cosine similarity via pgvector
- Implement `calculate_banking_metrics` as pure Python (no LLM) — see Section 6 for output schema
- Implement `get_current_banking_rates` as static lookup dict
- Implement `get_conversation_history` and `get_session_document_id` via SQLAlchemy queries
- Implement `log_pipeline_decision` — writes to `debug_trace` JSON column
- Decorate all functions with `@tool` from `langchain_core.tools`
- Write unit tests: upload a sample bank statement PDF, verify extraction and retrieval
- Handle edge cases: password-protected PDFs, blurry scans, multi-page documents

**Coordination note**: Member 2 (Classifier Agent) will import and bind these `@tool` functions directly. Agree on function signatures before either starts implementation.

---

### Member 4 — Strategy Agent + Generator Agent + Critic Agent + YAML Files

**Core responsibility**: Build the three "reasoning" agents in the middle and end of the pipeline, and create the new `document_grounded` strategy YAML files.

**Deliverables:**

```
backend/
├── agents/
│   ├── strategy_agent.py             # LLM: selects strategy path
│   ├── generator_agent.py            # GPT-4o-mini: drafts response
│   └── critic_agent.py               # LLM with CoT: validates + scores
├── strategies/
│   ├── blocked/
│   │   ├── financial_hardship.yaml
│   │   ├── bereavement.yaml
│   │   └── fraud_report.yaml
│   ├── soft_persuasion/
│   │   ├── social_proof.yaml
│   │   ├── authority.yaml
│   │   └── reciprocity.yaml          # NEW
│   ├── document_grounded/            # NEW category
│   │   ├── statement_analysis.yaml
│   │   └── loan_analysis.yaml
│   └── neutral/
│       └── informational.yaml
```

**Tasks:**
- Port strategy selector logic to LangGraph node (banking-scoped, Section 5 Node 4)
- Add document-grounded path: if `has_document` and advice-seeking intent → `document_grounded/`
- Port generator to LangGraph node — add constraint: cite document figures when present
- Build critic as LLM agent with chain-of-thought: reads `strategy_config.prohibited`, cites specific violations with regulation references
- Add document-specific critic checks (fabricated figures, generic advice when data exists)
- Write all 9 YAML strategy files (see Section 9 for `statement_analysis.yaml` template)
- Write unit tests: critic should fail a response that says "many customers find" when a bank statement was provided
- Write unit tests: critic should pass the same response when no document is present

**Key challenge**: The strategy agent must handle the case where `has_document == True` but the user's question is unrelated to the document (e.g., uploaded a bank statement but asked "what is APR?"). In that case, fall through to emotion-first selection, not document_grounded.

---

### Member 5 — Frontend + API Integration

**Core responsibility**: Update the FastAPI endpoints to handle file uploads and build the document upload UI in React. No MCP server — tools are `@tool` functions defined by Member 3 and imported directly by agents.

**Deliverables:**

```
backend/routers/
└── chat.py                       # Updated: multipart/form-data, calls graph runner

frontend/src/
├── components/
│   ├── ChatWindow.jsx
│   └── DocumentUpload.jsx        # NEW: drag-drop file upload
└── App.jsx                       # Wire DocumentUpload into chat flow
```

**Tasks:**
- Update `chat.py` router to accept `multipart/form-data` (message + optional file)
- Pass `document_bytes` into `BankingPipelineState` when file is present
- Build `DocumentUpload.jsx` React component: drag-drop or click-to-upload, shows filename on success
- Wire document upload into chat submit: if file selected, include in `multipart/form-data` request
- Show document context indicator in chat UI when a document is active in the session
- End-to-end test: upload a PDF via frontend, verify it flows through the full pipeline

**Coordination note**: Member 3 owns the `@tool` function implementations. Member 5 only needs to ensure the raw `file_bytes` arrive at the Entry Node via the router — no tool wiring required here.

---

### Integration Week (All Members)

After each member completes their track independently:

```
Day 1: Replace mock nodes in graph with real implementations (Member 1 leads)
Day 2: End-to-end test with all 3 scenarios:
        - BLOCKED (bereavement message)
        - PASS without document (anxiety about loan)
        - PASS with document (bank statement + savings advice)
Day 3: Load testing, latency profiling, demo prep
```

**Expected latencies per path:**

| Path | Expected Latency |
|---|---|
| BLOCKED (keyword match) | < 0.5s |
| PASS, no document | ~4–5s (classifier + strategy + generator + critic) |
| PASS, with document | ~6–8s (classifier does doc analysis inline, then rest) |

---

## Dependency Map

```
Member 1 (Graph)       ←── depends on ──→  All members (needs node interfaces)
Member 2 (Class+Gate)  ←── imports tools ── Member 3 (binds @tool functions)
Member 3 (Tools+Docs)  ──── independent ──── provides @tool functions to Member 2
Member 4 (Strategy+    ──── independent ─────────────────────────────────────────
          Generator+
          Critic+YAML)
Member 5 (Frontend)    ──── independent ──── only touches chat.py router + React UI
```

**Start order recommendation:**
- Week 1: Member 3 builds `@tool` functions + document ingestion (unblocks Member 2)
- Week 1: Members 2, 4 build their agents independently once Member 3 agrees on tool signatures
- Week 1: Member 5 builds frontend + updates `chat.py` router (fully independent)
- Week 1: Member 1 builds graph with all-mock nodes, verifies routing logic
- Week 2: Member 2 imports Member 3's tools and wires them into the Classifier Agent
- Week 2: Member 1 replaces mock nodes with real implementations one at a time
- Week 3: Full integration, testing, demo prep

---

*Last Updated: 2026-04-09*
*This document supersedes `.claude/architecture.md` for v2 design decisions.*
*Update `.claude/current_status.md` as implementation progresses.*
