# Ethics Gate — Compliance Documentation

## 1. Hard-Block Keyword List

These keywords trigger an **immediate BLOCKED decision** (Layer 1).  
No model inference is performed. Confidence is always `1.0`.  
Keywords are matched **case-insensitively** and as **substrings** (so "died" matches "my father died yesterday").

| # | Keyword | FCA Vulnerability Driver | Category |
|---|---------|--------------------------|----------|
| 1 | `passed away` | Life Events | Bereavement |
| 2 | `death` | Life Events | Bereavement |
| 3 | `died` | Life Events | Bereavement |
| 4 | `funeral` | Life Events | Bereavement |
| 5 | `bereavement` | Life Events | Bereavement |
| 6 | `grieving` | Life Events | Bereavement |
| 7 | `suicide` | Health | Mental Health Crisis |
| 8 | `bankruptcy` | Resilience | Financial Distress |
| 9 | `foreclosure` | Resilience | Financial Distress |
| 10 | `can't afford` | Resilience | Financial Distress |
| 11 | `lost my job` | Life Events / Resilience | Employment Shock |
| 12 | `laid off` | Life Events / Resilience | Employment Shock |

---

## 2. FCA Vulnerability Mapping

The UK Financial Conduct Authority (FCA) **Consumer Duty (2023)** defines vulnerability  
via four drivers. Our Ethics Gate covers all four:

### Driver 1 — Life Events
Sudden, significant life changes that impair decision-making capacity.

**Covered by keywords:** `passed away`, `death`, `died`, `funeral`, `bereavement`, `grieving`, `lost my job`, `laid off`

**FCA Requirement:** Firms must not exploit emotional states during bereavement or major life disruption. The gate responds with empathy-only messaging and zero persuasion.

---

### Driver 2 — Health
Physical or mental health conditions affecting ability to engage with financial products.

**Covered by keywords:** `suicide`  
**Covered by model (Layer 2):** Distress signals not in keyword list (e.g. *"I can't cope"*, *"I feel hopeless"*)

**FCA Requirement:** Customers in mental health crisis must be routed to appropriate support, not engaged commercially. The gate provides crisis line numbers (988, 741741) and does not proceed with any financial discussion.

---

### Driver 3 — Resilience
Low financial or emotional resilience leaving customers unable to withstand financial shocks.

**Covered by keywords:** `bankruptcy`, `foreclosure`, `can't afford`  
**Covered by model (Layer 2):** Phrasing like *"struggling financially"*, *"can barely make payments"*

**FCA Requirement:** Customers in financial distress must not be upsold or cross-sold. The gate routes to hardship specialists only.

---

### Driver 4 — Capability
Low knowledge, confidence, or skills in managing finances.

**Covered by:** Layer 2 zero-shot model (DeBERTa v3)  
No hard keywords are effective here; the model detects confusion signals like *"I don't understand"*, *"I have no idea what to do"*

**FCA Requirement:** Customers with low financial capability must receive clear information, not persuasive framing. Gate returns `AMBIGUOUS` which triggers an informational-only response path.

---

## 3. Decision Logic Summary

```
Incoming message
      │
      ▼
┌─────────────────────────────────┐
│  Layer 1: Keyword Scan          │  ← Microseconds, deterministic
│  Match found?                   │
└────────┬────────────────────────┘
         │ YES → BLOCKED (confidence=1.0)
         │ NO  ↓
┌─────────────────────────────────┐
│  Layer 2: DeBERTa v3 Zero-Shot  │  ← ~200ms, nuanced
│  Top label?                     │
└────────┬────────────────────────┘
         ├─ "vulnerable" + score ≥ 0.60  → BLOCKED
         ├─ "vulnerable" + score < 0.60  → AMBIGUOUS
         ├─ "unclear"                    → AMBIGUOUS
         └─ "routine financial inquiry"  → APPROVED
```

---

## 4. Blocked Response Principles

All BLOCKED/AMBIGUOUS responses follow these rules (FCA Consumer Duty, Outcome 4):

1. **Acknowledge** — Express empathy appropriate to the situation
2. **Inform only** — Provide exactly what was requested, nothing more
3. **Escalate** — Provide a human contact path (specialist phone line)
4. **Zero persuasion** — No product recommendations, no retention tactics, no upsell

**Prohibited phrases in any blocked response:**
- "consider upgrading / switching"
- "great opportunity"
- "don't miss out"
- "we recommend you"
- "special offer"

---

## 5. Model Details (Layer 2)

| Property | Value |
|----------|-------|
| Model | `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` |
| Parameters | 184M |
| Task | Zero-shot classification |
| Confidence threshold | 0.60 |
| Inference device | CPU (configurable to GPU) |
| Fail-safe behaviour | Error → `AMBIGUOUS` (never `APPROVED`) |

---

## 6. Audit Trail

Every gate decision is logged to the `classifications` table:

| Field | Description |
|-------|-------------|
| `gate_decision` | BLOCKED / APPROVED / AMBIGUOUS |
| `gate_reason` | e.g. `keyword:passed away` or `model:routine_financial_inquiry` |
| `gate_confidence` | 0.0 – 1.0 |
| `gate_layer` | `keyword` or `model` |

This enables compliance teams to query 100% of vulnerable interactions:

```sql
SELECT m.content, cl.gate_decision, cl.gate_reason, cl.gate_confidence
FROM   messages m
JOIN   classifications cl ON cl.message_id = m.id
WHERE  cl.gate_decision = 'BLOCKED'
ORDER  BY m.created_at DESC;
```

---

*Last updated: 2026-03-11 | Owner: Person 2 — Ethics Gate & Compliance*
