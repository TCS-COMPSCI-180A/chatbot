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
6. [MCP Tools Catalog](#6-mcp-tools-catalog)
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
| Gate | DeBERTa zero-shot (no reasoning) | DeBERTa (hard rules) + document-type awareness |
| Classifier | 3 DeBERTa zero-shot calls, single message | LLM with chain-of-thought, multi-turn history |
| Strategy | Rule-based lookup | LLM agent reading YAML + document insights |
| Critic | DeBERTa zero-shot scoring | LLM with chain-of-thought, regulation citations |
| Document support | None | Full RAG: parse → embed → retrieve → ground response |
| Tool access | None | MCP server with 12 tools across 4 categories |
| Domain | General financial services | Banking only |
| Strategy files | 6 YAML files | 9 YAML files (adds `document_grounded/` category) |
| Parallel execution | Sequential only | Classifier + Document Analysis run in parallel |

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
│  │  document_ingestion → ethics_gate → [routing] →              │  │
│  │  [parallel: classifier + document_analysis] →                │  │
│  │  strategy → generator → critic → [loop or END]               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────────────────────────┐  │
│  │  MCP SERVER       │   │  POSTGRESQL + PGVECTOR               │  │
│  │  12 tools across  │   │  - conversations, messages,          │  │
│  │  4 categories     │   │    classifications tables            │  │
│  └──────────────────┘   │  - document_chunks table (pgvector)  │  │
│                          └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI 0.109+ |
| Graph orchestration | LangGraph 0.2+ |
| SLM (ethics gate, doc classify) | DeBERTa v3 (`MoritzLaurer/deberta-v3-base-zeroshot-v2.0`) |
| LLM (all agents) | GPT-4o-mini (OpenAI) |
| Tool protocol | MCP (Model Context Protocol) |
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
┌─────────────────────────────────┐
│   DOCUMENT INGESTION NODE       │  ← Skipped if no document
│   parse_pdf / ocr_image         │
│   classify_banking_document     │
│   extract_banking_figures       │
│   chunk_and_embed_document      │
│                                 │
│   Writes to state:              │
│   - document_text               │
│   - document_type               │
│   - document_figures            │
│   - document_doc_id             │
└────────────────┬────────────────┘
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
│   Output: BLOCKED | APPROVED | AMBIGUOUS             │
└────────┬───────────────────┬──────────────┬──────────┘
         │                   │              │
      BLOCKED            AMBIGUOUS       APPROVED
         │                   │              │
         ▼                   ▼              │
  ┌────────────┐    ┌──────────────────┐   │
  │  select    │    │  select          │   │
  │  blocked/  │    │  blocked/        │   │
  │  YAML      │    │  ambiguous.yaml  │   │
  └─────┬──────┘    └───────┬──────────┘   │
        │                   │              │
        │                   │              ▼
        │                   │  ┌────────────────────────────────────────┐
        │                   │  │  PARALLEL EXECUTION (LangGraph fanout) │
        │                   │  │                                        │
        │                   │  │  ┌─────────────────────────────────┐  │
        │                   │  │  │  CLASSIFIER AGENT               │  │
        │                   │  │  │  (LLM + tools)                  │  │
        │                   │  │  │                                 │  │
        │                   │  │  │  Tools used:                    │  │
        │                   │  │  │  - get_conversation_history()   │  │
        │                   │  │  │  - lookup_banking_regulation()  │  │
        │                   │  │  │                                 │  │
        │                   │  │  │  Output:                        │  │
        │                   │  │  │  - emotion (Plutchik)           │  │
        │                   │  │  │  - intent (banking taxonomy)    │  │
        │                   │  │  │  - situation (biz perspective)  │  │
        │                   │  │  │  - classification_reasoning     │  │
        │                   │  │  └─────────────────────────────────┘  │
        │                   │  │                                        │
        │                   │  │  ┌─────────────────────────────────┐  │
        │                   │  │  │  DOCUMENT ANALYSIS AGENT        │  │  ← Only if
        │                   │  │  │  (LLM + tools)                  │  │    has_document
        │                   │  │  │                                 │  │
        │                   │  │  │  Tools used:                    │  │
        │                   │  │  │  - retrieve_relevant_chunks()   │  │
        │                   │  │  │  - get_current_rates()          │  │
        │                   │  │  │  - calculate_banking_metrics()  │  │
        │                   │  │  │                                 │  │
        │                   │  │  │  Output:                        │  │
        │                   │  │  │  - document_insights (list)     │  │
        │                   │  │  │  - specific figures from doc    │  │
        │                   │  │  │  - action items grounded in doc │  │
        │                   │  │  └─────────────────────────────────┘  │
        │                   │  └──────────────────┬─────────────────────┘
        │                   │                     │ (fanin — merge state)
        │                   │                     ▼
        │                   │     ┌───────────────────────────────────┐
        │                   │     │  STRATEGY AGENT  (LLM)            │
        │                   │     │                                   │
        │                   │     │  Priority order:                  │
        │                   │     │  1. Compliance overrides          │
        │                   │     │     (fraud, close_account →       │
        │                   │     │      never persuade)              │
        │                   │     │  2. Document-grounded path        │
        │                   │     │     (has_document + advice intent │
        │                   │     │      → document_grounded/ YAML)   │
        │                   │     │  3. Emotion-first selection       │
        │                   │     │     (anxiety → social_proof)      │
        │                   │     │  4. Default: neutral/informational│
        │                   │     │                                   │
        │                   │     │  Output: strategy_path,           │
        │                   │     │          strategy_config,         │
        │                   │     │          strategy_reasoning       │
        │                   │     └────────────────┬──────────────────┘
        │                   │                      │
        │                   │                      ▼
        │                   │     ┌───────────────────────────────────┐
        │                   │     │  GENERATOR AGENT  (GPT-4o-mini)   │
        │                   │     │                                   │
        │                   │     │  Inputs:                          │
        │                   │     │  - strategy YAML (tone,           │
        │                   │     │    compliant_framing, prohibited) │
        │                   │     │  - document_insights (if present) │
        │                   │     │  - emotion, intent from classifier│
        │                   │     │                                   │
        │                   │     │  If document present:             │
        │                   │     │  MUST cite ≥2 specific figures    │
        │                   │     │  CANNOT use generic statistics    │
        │                   │     └────────────────┬──────────────────┘
        ▼                   ▼                      ▼
┌────────────────────────────────────────────────────────────┐
│  CRITIC AGENT  (LLM with chain-of-thought)                 │
│                                                            │
│  Checks:                                                   │
│  - Is the response coercive or manipulative?               │
│  - Does it use prohibited framing from the strategy YAML?  │
│  - If document present: are figures cited correctly?       │
│  - FCA COBS 4.5.2: no false urgency                        │
│  - If gate was BLOCKED: zero persuasion allowed            │
│                                                            │
│  Score < 7.0 → rewrite (max 1 time, then force pass)       │
│  Score ≥ 7.0 → pass                                        │
└─────────────────────────────┬──────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
           passed          failed          failed
           (score≥7)      (score<7,      (score<7,
              │           rewrite=0)     rewrite=1)
              │               │               │
              │               ▼               │
              │       ┌────────────┐          │
              │       │ GENERATOR  │          │
              │       │ (rewrite)  │          │
              │       └─────┬──────┘          │
              │             │                 │
              │             ▼                 │
              │       ┌────────────┐          │
              │       │  CRITIC    │          │
              │       │ (re-score) │          │
              │       └─────┬──────┘          │
              │             │                 │
              └─────────────┴─────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  DATABASE LOGGER              │
              │                               │
              │  Logs to classifications      │
              │  table:                       │
              │  - gate_decision + reason     │
              │  - emotion, intent, situation │
              │  - strategy_path              │
              │  - critic_score + violations  │
              │  - rewrite_count              │
              │  - document_type (if present) │
              │  - full debug_trace JSON      │
              └───────────────┬───────────────┘
                              │
                              ▼
                       FINAL RESPONSE
```

### Routing Logic (Conditional Edges)

```python
# After ethics gate
def route_after_gate(state) -> str:
    decision = state["gate_decision"]
    if decision == "BLOCKED":
        return "strategy"         # skip classifier, load blocked/ YAML
    if decision == "AMBIGUOUS":
        return "strategy"         # skip classifier, load ambiguous YAML
    return "parallel_start"       # fan out to classifier + doc analysis

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

### Node 1: Document Ingestion

| Property | Value |
|---|---|
| Type | Deterministic function (no LLM) |
| Runs when | `has_document == True` |
| Input | `document_bytes`, `session_id` |
| Output | `document_text`, `document_type`, `document_figures`, `document_doc_id` |
| Tools called | `parse_pdf_document`, `classify_banking_document`, `extract_banking_figures`, `chunk_and_embed_document` |

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

### Node 2: Ethics Gate

| Property | Value |
|---|---|
| Type | Hard rules + DeBERTa v3 SLM (deterministic) |
| MUST run | Always, first, unconditionally |
| Input | `message`, `document_type` (if present) |
| Output | `gate_decision`, `gate_reason`, `gate_confidence` |
| Tools called | None — deterministic only |

**Decision layers (in order):**

1. Document type hard block (`foreclosure_notice`, `bankruptcy_filing` → BLOCKED immediately)
2. Hard keyword match in message (see keyword list in Section 8)
3. DeBERTa v3 zero-shot: `["vulnerable/distressed", "routine banking inquiry", "context is unclear"]`
4. Confidence thresholds: vulnerable > 0.6 → BLOCKED; unclear > 0.5 → AMBIGUOUS; else APPROVED

---

### Node 3: Classifier Agent

| Property | Value |
|---|---|
| Type | LLM agent with tool access |
| Runs when | `gate_decision == "APPROVED"` |
| Input | `message`, `session_id` |
| Output | `emotion`, `intent`, `situation`, `classification_reasoning` |
| Tools called | `get_conversation_history`, `lookup_banking_regulation` |

The key upgrade from v1: the classifier agent reads conversation history to classify in context, not just on the current message. A user who asked about mortgage rates two turns ago and now says "I'm worried about my payment" is expressing `fear_or_apprehension` about an existing loan, not `anxiety_or_worry` about a new decision — this distinction changes the strategy selected.

---

### Node 4: Document Analysis Agent

| Property | Value |
|---|---|
| Type | LLM agent with tool access |
| Runs when | `gate_decision == "APPROVED"` AND `has_document == True` |
| Runs parallel with | Classifier Agent |
| Input | `message`, `document_doc_id`, `document_figures` |
| Output | `document_insights` (list of grounded observations) |
| Tools called | `retrieve_relevant_chunks`, `get_current_rates`, `calculate_banking_metrics` |

**What this agent produces (example for bank statement + "how can I save more"):**

```
document_insights: [
    "Your statement shows $312 in overdraft fees over 90 days ($1,248 annualized).",
    "You have 3 recurring streaming subscriptions totaling $267/month.",
    "Your average daily balance is $340 — below the $500 threshold to waive your $12 monthly fee.",
    "Current HYSA rate at comparable banks: 4.2% APY vs your savings rate of 0.01%.",
]
```

These are the inputs to the generator. The response is grounded in the customer's actual data, not generic banking advice.

---

### Node 5: Strategy Agent

| Property | Value |
|---|---|
| Type | LLM |
| Input | `gate_decision`, `emotion`, `intent`, `situation`, `document_insights` |
| Output | `strategy_path`, `strategy_config`, `strategy_reasoning` |
| Tools called | None |

**Selection priority:**

```
1. Compliance overrides (always win):
   - intent == "report_fraudulent_activity" → blocked/fraud_report
   - intent == "close_bank_account"         → blocked/high_risk (no retention)
   - intent == "request_loan_modification"  → blocked/financial_hardship

2. Gate overrides:
   - gate_decision == "BLOCKED"    → blocked/bereavement or blocked/financial_hardship
   - gate_decision == "AMBIGUOUS"  → blocked/ambiguous

3. Document-grounded path (NEW):
   - has_document == True AND
     intent in ["seek_banking_advice", "request_explanation", "general_banking_inquiry"]
       → document_grounded/statement_analysis  (for bank_statement, credit_card_statement)
       → document_grounded/loan_analysis       (for loan_agreement, mortgage_statement)

4. Emotion-first selection:
   - anxiety_or_worry / fear_or_apprehension  → soft_persuasion/social_proof
   - neutral_or_calm + seek_banking_advice    → soft_persuasion/authority
   - trust_or_acceptance + loyal indicators  → soft_persuasion/reciprocity

5. Default:
   → neutral/informational
```

---

### Node 6: Generator Agent

| Property | Value |
|---|---|
| Type | GPT-4o-mini |
| Input | `strategy_config`, `document_insights`, `emotion`, `intent`, `message` |
| Output | `response_draft` |
| Temperature | 0.7 (0.5 on rewrite) |
| Max tokens | 350 |

**Critical constraint when document is present:**
The system prompt explicitly requires citing at least 2 specific figures from `document_insights`. Generic statistics ("many customers find...") are prohibited when specific document data exists.

---

### Node 7: Critic Agent

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

### Node 8: Database Logger

Logs the full state to the `classifications` table. Unchanged from v1 schema, with two new columns: `document_type` and `document_doc_id`.

---

## 6. MCP Tools Catalog

The MCP server exposes 12 tools across 4 categories. All agents in the LangGraph graph call tools through this server.

### Category 1: Document Tools

These tools handle the full document lifecycle from raw bytes to queryable vector chunks.

```
parse_pdf_document(file_bytes: bytes) → str
  Purpose: Extract raw text from a PDF file
  Used by: Document Ingestion Node
  Returns: Raw text string (may be multi-page)
  Notes: Uses PDFPlumber. Falls back to OCR if text layer is absent.

ocr_image_document(file_bytes: bytes) → str
  Purpose: Extract text from an image (JPG, PNG, TIFF) via OCR
  Used by: Document Ingestion Node
  Returns: Raw text string
  Notes: Uses Tesseract. Preprocesses image for contrast/deskew.

classify_banking_document(text: str) → str
  Purpose: Identify the type of banking document from its content
  Used by: Document Ingestion Node
  Returns: One of: bank_statement | loan_agreement | mortgage_statement |
           credit_card_statement | cd_savings_statement | credit_report |
           foreclosure_notice | bankruptcy_filing | unknown
  Notes: DeBERTa v3 zero-shot with banking document labels.

extract_banking_figures(text: str, doc_type: str) → dict
  Purpose: Pull structured key figures from the document text
  Used by: Document Ingestion Node
  Returns: Dict of key figures appropriate for doc_type. Examples:
    bank_statement:   { current_balance, avg_balance, total_fees,
                        overdraft_count, overdraft_total, top_merchants }
    loan_agreement:   { principal, apr, monthly_payment, term_months,
                        remaining_balance, prepayment_penalty }
    mortgage_statement: { principal_balance, interest_rate, monthly_payment,
                          escrow_balance, payoff_amount }
    credit_card_statement: { balance, apr, min_payment, credit_limit,
                              utilization_pct, statement_date }
  Notes: Regex + LLM extraction hybrid. Logs extraction confidence.

chunk_and_embed_document(text: str, session_id: str) → str
  Purpose: Split document into chunks, embed each, store in pgvector
  Used by: Document Ingestion Node
  Returns: doc_id (UUID string) — used for retrieval later
  Notes: Chunk size 512 tokens, 50-token overlap.
         Uses text-embedding-3-small. Stores in document_chunks table.

retrieve_relevant_chunks(query: str, doc_id: str, top_k: int = 4) → list[str]
  Purpose: Semantic search over the stored document chunks
  Used by: Document Analysis Agent
  Returns: List of the top_k most relevant text chunks
  Notes: Cosine similarity via pgvector. Query is embedded on the fly.
```

---

### Category 2: Banking Metrics Tools

These tools perform calculations and rate lookups that ground advice in real numbers.

```
calculate_banking_metrics(figures: dict, doc_type: str) → dict
  Purpose: Compute derived financial metrics from extracted figures
  Used by: Document Analysis Agent
  Returns: Dict of computed metrics. Examples:
    For bank_statement:
      { annualized_fees, fee_pct_of_balance, avg_transaction_count,
        overdraft_risk_score, savings_gap_vs_emergency_fund }
    For loan_agreement:
      { total_interest_remaining, effective_monthly_rate,
        break_even_months_to_refinance }
    For credit_card_statement:
      { monthly_interest_cost, payoff_months_at_min_payment,
        utilization_category: "good|fair|poor" }
  Notes: Pure calculation — no LLM. Returns numbers only.

get_current_banking_rates(product_type: str) → dict
  Purpose: Return current market rates for comparison in advice
  Used by: Document Analysis Agent
  Returns: Rate information for the requested product. Examples:
    product_type: "hysa"         → { apy: 4.2, source: "national_avg_2026" }
    product_type: "cd_12_month"  → { apy: 4.8 }
    product_type: "mortgage_30yr"→ { rate: 6.9 }
    product_type: "personal_loan"→ { apr_range: [9.5, 24.0] }
  Notes: Static lookup table updated quarterly. Not real-time market data.
         Always disclose this is illustrative, not a guaranteed offer.
```

---

### Category 3: Context Tools

These tools give agents memory — access to conversation history and session state.

```
get_conversation_history(session_id: str, turns: int = 5) → list[dict]
  Purpose: Retrieve prior messages in this conversation
  Used by: Classifier Agent
  Returns: List of { role, content, created_at } dicts, most recent first
  Notes: Classifier uses this to classify emotion/intent in full context,
         not just the current message.

get_session_document_id(session_id: str) → str | None
  Purpose: Check if a document was uploaded earlier in this session
  Used by: Document Analysis Agent, Strategy Agent
  Returns: doc_id string if document exists for session, None otherwise
  Notes: Supports multi-turn document conversations — user uploads once,
         asks multiple questions across turns.
```

---

### Category 4: Knowledge & Audit Tools

```
lookup_banking_regulation(topic: str) → str
  Purpose: Return relevant regulatory text for a given topic
  Used by: Classifier Agent, Critic Agent
  Returns: Short excerpt of relevant regulatory guidance
  Examples:
    topic: "overdraft_fees"     → FCA/CFPB guidance on fee disclosure
    topic: "fca_cobs_4"         → FCA COBS 4.5 communications rules
    topic: "fair_lending"       → Equal Credit Opportunity Act summary
    topic: "tcpa_consent"       → Telephone Consumer Protection Act basics
  Notes: Static knowledge base. Used by critic to cite specific violations.

log_pipeline_decision(session_id: str, node: str, decision: dict) → None
  Purpose: Write a structured decision record to the audit log
  Used by: All agent nodes
  Returns: None
  Notes: Each node calls this to create a granular audit trail beyond
         what the DB logger captures. Stored in debug_trace JSON column.
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

    # ── Document Processing ──────────────────────────────────────
    has_document: bool
    document_text: Optional[str]        # full parsed text
    document_type: Optional[str]        # bank_statement | loan_agreement | ...
    document_figures: Optional[dict]    # extracted key numbers
    document_doc_id: Optional[str]      # pgvector doc UUID
    document_insights: Optional[list]   # grounded observations for generator

    # ── Ethics Gate ──────────────────────────────────────────────
    gate_decision: Literal["BLOCKED", "APPROVED", "AMBIGUOUS"]
    gate_reason: str
    gate_confidence: float

    # ── Classification ───────────────────────────────────────────
    emotion: Optional[str]
    intent: Optional[str]
    situation: Optional[str]
    classification_reasoning: Optional[str]   # LLM chain-of-thought

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
│   ├── fraud_report.yaml          # fraudulent activity → escalate only
│   └── ambiguous.yaml             # unclear context → ask questions
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
  - "Gate is BLOCKED or AMBIGUOUS"
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
- Set up `StateGraph`, register all 8 nodes as stubs initially
- Implement all conditional edges (`route_after_gate`, `route_after_critic`)
- Implement parallel fanout/fanin for classifier + document analysis
- Wire `graph.py` into `backend/routers/chat.py` (replace orchestrator call)
- Write integration test: run full graph with mock nodes, verify state flows correctly
- Maintain graph visualization export (LangGraph can export Mermaid diagrams)

**Dependencies on others**: Needs stub interfaces from each other member (function signatures, not implementations). Start with mock nodes that return hardcoded state.

**Key technical challenge**: LangGraph parallel execution — use `Send` API or `add_node` with a fan-out pattern to run classifier and document analysis concurrently, then merge state.

---

### Member 2 — Ethics Gate + Classifier Agent

**Core responsibility**: Keep the deterministic ethics gate working and upgrade the classifier from zero-shot SLM to an LLM agent with multi-turn context awareness.

**Deliverables:**

```
backend/
├── agents/
│   ├── __init__.py
│   ├── ethics_gate.py        # Hard rules + DeBERTa + document_type check
│   └── classifier_agent.py   # LLM agent: emotion, intent, situation
```

**Tasks:**
- Port ethics gate from v1 (`pipeline/ethics_gate.py`) to new path
- Add document-type awareness: `foreclosure_notice` and `bankruptcy_filing` → BLOCKED
- Update hard block keywords to banking scope (Section 8)
- Build classifier agent using LangChain's tool-calling pattern
- Integrate `get_conversation_history` tool so classifier reasons over prior turns
- Integrate `lookup_banking_regulation` tool (stub the MCP call initially)
- Update emotion labels (unchanged), intent labels (banking-scoped, Section 8), situation labels
- Write unit tests for all 3 gate decisions (BLOCKED, APPROVED, AMBIGUOUS)
- Write unit tests for classifier: verify multi-turn context changes classification

**Key difference from v1**: The classifier is now a ReAct agent inside a LangGraph node. It calls `get_conversation_history()` before classifying, so its output reflects the full conversation, not just the last message.

**Example behavior to test:**
```
Turn 1: "What are your mortgage rates?"  (neutral)
Turn 2: "I'm worried about my payment"   (with history: fear_or_apprehension about loan)
                                          (without history: anxiety_or_worry — wrong)
```

---

### Member 3 — Document Ingestion + Document Analysis Agent

**Core responsibility**: Build the entire document processing pipeline — from raw file upload to grounded insights that the generator can cite.

**Deliverables:**

```
backend/
├── agents/
│   └── document_analysis_agent.py    # LLM agent: retrieve, analyze, ground
├── document/
│   ├── __init__.py
│   ├── ingestion.py                  # parse, classify, extract, embed
│   ├── extractors.py                 # doc-type-specific figure extraction
│   └── retrieval.py                  # pgvector chunk retrieval
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
- Implement `parse_pdf_document` using PDFPlumber
- Implement `ocr_image_document` using pytesseract
- Implement `classify_banking_document` using DeBERTa zero-shot (reuse SLM instance)
- Implement `extract_banking_figures` for each document type (regex + LLM hybrid)
- Implement `chunk_and_embed_document`: chunking, embedding via OpenAI, store in pgvector
- Implement `retrieve_relevant_chunks`: cosine similarity query against pgvector
- Build document analysis agent: LLM that reads retrieved chunks + calls `get_current_banking_rates` and `calculate_banking_metrics`
- Write unit tests: upload a sample bank statement PDF, verify extraction and retrieval
- Handle edge cases: password-protected PDFs, blurry scans, multi-page documents

**Frontend integration needed** (coordinate with Member 5): The chat endpoint needs to accept `multipart/form-data` (not just JSON) to receive the file. Member 3 owns the backend handler; Member 5 owns the file upload UI component.

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
│   │   ├── fraud_report.yaml
│   │   └── ambiguous.yaml
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
- Port strategy selector logic to LangGraph node (banking-scoped, Section 5 Node 5)
- Add document-grounded path: if `has_document` and advice-seeking intent → `document_grounded/`
- Port generator to LangGraph node — add constraint: cite document figures when present
- Build critic as LLM agent with chain-of-thought: reads `strategy_config.prohibited`, cites specific violations with regulation references
- Add document-specific critic checks (fabricated figures, generic advice when data exists)
- Write all 9 YAML strategy files (see Section 9 for `statement_analysis.yaml` template)
- Write unit tests: critic should fail a response that says "many customers find" when a bank statement was provided
- Write unit tests: critic should pass the same response when no document is present

**Key challenge**: The strategy agent must handle the case where `has_document == True` but the user's question is unrelated to the document (e.g., uploaded a bank statement but asked "what is APR?"). In that case, fall through to emotion-first selection, not document_grounded.

---

### Member 5 — MCP Server + Frontend + API Integration

**Core responsibility**: Build the MCP server that all agents call, update the FastAPI endpoints to handle file uploads, and update the frontend with a document upload UI.

**Deliverables:**

```
backend/
├── mcp/
│   ├── __init__.py
│   ├── server.py                 # MCP server definition
│   ├── tools/
│   │   ├── document_tools.py     # parse, classify, extract, embed, retrieve
│   │   ├── metrics_tools.py      # calculate_banking_metrics, get_current_rates
│   │   ├── context_tools.py      # get_conversation_history, get_session_doc_id
│   │   └── audit_tools.py        # log_pipeline_decision
│   └── client.py                 # MCP client used by LangGraph agents

backend/routers/
└── chat.py                       # Updated: multipart/form-data, calls graph runner

frontend/src/
├── components/
│   ├── ChatWindow.jsx
│   └── DocumentUpload.jsx        # NEW: drag-drop file upload
└── App.jsx                       # Wire DocumentUpload into chat flow
```

**Tasks:**
- Set up MCP server using the `mcp` Python SDK
- Implement all 12 tools (Section 6) — tools in `document_tools.py` are stubs that delegate to Member 3's implementations
- Implement `calculate_banking_metrics` and `get_current_rates` as pure functions
- Implement `get_conversation_history` via SQLAlchemy query
- Update `chat.py` router to accept `multipart/form-data` (message + optional file)
- Build `DocumentUpload.jsx` React component: drag-drop or click-to-upload, shows filename on success
- Wire document upload into chat submit: if file selected, include in request
- Show document context indicator in chat UI when a document is active in session
- End-to-end test: upload a PDF via frontend, verify it flows through the full pipeline

**Coordination note**: The MCP tool implementations for document parsing (`parse_pdf_document`, etc.) are thin wrappers that call Member 3's `ingestion.py` functions. Agree on function signatures before either starts implementation.

---

### Integration Week (All Members)

After each member completes their track independently:

```
Day 1: Replace mock nodes in graph with real implementations (Member 1 leads)
Day 2: End-to-end test with all 4 scenarios:
        - BLOCKED (bereavement message)
        - AMBIGUOUS (unclear context)
        - APPROVED without document (anxiety about loan)
        - APPROVED with document (bank statement + savings advice)
Day 3: Load testing, latency profiling, demo prep
```

**Expected latencies per path:**

| Path | Expected Latency |
|---|---|
| BLOCKED (keyword match) | < 0.5s |
| AMBIGUOUS → clarification | ~2s (one LLM call) |
| APPROVED, no document | ~4–5s (classifier + strategy + generator + critic) |
| APPROVED, with document | ~5–7s (parallel classifier + doc analysis, then rest) |

---

## Dependency Map

```
Member 1 (Graph)      ←── depends on ──→  All members (needs node interfaces)
Member 2 (Gate+Class) ──── independent ────────────────────────────────────────
Member 3 (Documents)  ──→ provides tools to ──→ Member 5 (MCP server wraps these)
Member 4 (Strategy+   ──── independent ────────────────────────────────────────
          Generator+
          Critic+YAML)
Member 5 (MCP+        ←── wraps Member 3's ──── provides tools to all agents
          Frontend)        document functions
```

**Start order recommendation:**
- Week 1: Members 2, 3, 4 build their components independently with stub dependencies
- Week 1: Member 5 builds MCP server structure + stubs + frontend
- Week 1: Member 1 builds graph with all-mock nodes, verifies routing logic
- Week 2: Members 3 → 5 integrate (document tools wired into MCP)
- Week 2: Member 1 replaces mock nodes with real implementations one at a time
- Week 3: Full integration, testing, demo prep

---

*Last Updated: 2026-04-09*
*This document supersedes `.claude/architecture.md` for v2 design decisions.*
*Update `.claude/current_status.md` as implementation progresses.*
