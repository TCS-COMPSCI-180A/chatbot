# Project Overview: TCS Ethical Persuasion Chatbot

## Project Identity

**Course**: COMPSCI 180A/B (UCI)
**Team**: Avengers (Team #101)
**Sponsor**: Tata Consultancy Services (TCS)
**Project Title**: Art of Persuasion: Building Intelligent Machines for Context-aware Engagement

### Team Members
- Shriivanth Gunanidhi (Team Lead) - sgunanid@uci.edu
- Arnav Pandey - arnavp4@uci.edu
- Jacob Horne - jhorne1@uci.edu
- Jason Wong - jasonhw3@uci.edu
- **Rounak Rao** - raora@uci.edu (primary developer)

## Problem Statement

Most existing financial services chatbots are either generic or insufficiently fine-tuned for high-stakes situations. They generate shallow, one-size-fits-all responses during crucial decision-making moments, leading to:

- Missed business opportunities
- Poor customer experiences
- Potential loss of business value
- **Ethical concerns**: Inappropriate influence in vulnerable situations (bereavement, financial hardship)
- **Regulatory risk**: Violation of FCA/FINRA guidelines

### Real-World Example

**Current chatbots:**
```
User: "My spouse just passed away. I need to cancel our life insurance."
Bot: "Before you cancel, have you considered the benefits of maintaining coverage?
      Many customers find..."
```
❌ **Problem**: Persuasion during bereavement is unethical and potentially illegal.

**Our solution:**
```
User: "My spouse just passed away. I need to cancel our life insurance."
Bot: [Ethics Gate: BLOCKED]
     "I'm very sorry for your loss. Here's the cancellation process: ..."
```
✅ **Result**: Empathy only, zero persuasion.

## Solution: Ethics-First AI Architecture

### Core Innovation: "SHOULD we persuade?" before "HOW to persuade?"

Traditional chatbots ask: *"How can we influence this user?"*
**Our system asks**: *"Is it even ethical to persuade right now?"*

### Pipeline Flow

```
User Message
    ↓
1. ETHICS GATE (Rules + Zero-Shot SLM)
   ├→ BLOCKED → Empathetic response, no persuasion
   ├→ AMBIGUOUS → Request clarification
   └→ APPROVED → Continue to classification ↓

2. CLASSIFIER (3 Zero-Shot Calls)
   - Emotion (Plutchik's 8 + financial context)
   - Intent (financial taxonomy)
   - Situation (positive/neutral/negative for business)
    ↓

3. STRATEGY SELECTOR (Emotion-First + Compliance Overrides)
   - Selects from Cialdini's 7 principles
   - Loads YAML strategy file
    ↓

4. LLM GENERATOR (GPT-4o-mini with Structured Prompts)
   - System prompt built from strategy YAML
   - Ethical constraints enforced
    ↓

5. CRITIC (Zero-Shot Validation)
   - Score response (0-10)
   - Check for violations
   - Optional bounded rewrite (ONE time max)
    ↓

6. DATABASE LOGGING (Full Audit Trail)
   - Gate decision + confidence
   - Classification results
   - Strategy selected
   - Critic score + violations
   - Final response
    ↓

Return to User
```

## Target Use Cases (TCS Financial Domain)

### Primary Use Cases
1. **Investment Management**
   - "I'm thinking about increasing my 401k contribution"
   - "Should I pull out of the market right now?"

2. **Wealth Planning**
   - "I want to save for my child's college fund"
   - "What do experts recommend for retirement?"

3. **Policy Management (Insurance)**
   - "I need to cancel my life insurance policy"
   - "Can I adjust my coverage?"

4. **Retirement Services**
   - "When should I start taking distributions?"
   - "How much should I contribute monthly?"

## MVP Scope (1-2 Day Implementation)

### ✅ IN SCOPE (What We're Building)

**Core Pipeline:**
- Ethics gate with hard-coded rules + DeBERTa v3 zero-shot classifier
- 3-layer classifier (emotion, intent, situation)
- Strategy selection (emotion-first, YAML-based, tunable)
- LLM generation with structured prompts from strategy files
- Critic validation with bounded rewrite (max 1 rewrite)
- Full auditability (PostgreSQL database logging)

**Frontend:**
- Chatscope React UI Kit (professional chat interface)
- Real-time message display
- Shows typing indicator during processing

**Infrastructure:**
- FastAPI backend
- PostgreSQL with pgvector
- Docker Compose setup

### ❌ OUT OF SCOPE (Future Work)

**Not Building for MVP:**
- RAG/knowledge retrieval (no proprietary data available yet)
- User history/personalization (no real users yet)
- Authentication/authorization system
- Multi-language support (English only)
- Fine-tuned models (zero-shot only for speed)
- Mobile app
- Advanced analytics dashboard

**Why These Are Out:**
- **RAG**: No TCS proprietary documents available for demo
- **User History**: Need real users first, focus on single-turn quality
- **Auth**: Demo doesn't need security, just functionality
- **Fine-tuning**: Zero-shot models sufficient for MVP, faster to implement

## Success Criteria

### For TCS Demo (Must-Haves)

1. ✅ **Ethics Gate Works**: System blocks persuasion in vulnerable contexts
   - Bereavement → BLOCKED
   - Financial hardship → BLOCKED
   - Routine inquiry → APPROVED

2. ✅ **Strategy Selection Works**: Emotion drives strategy choice
   - Anxiety → Social Proof strategy
   - Calm + advice-seeking → Authority strategy

3. ✅ **Transparency**: All decisions are auditable
   - Check PostgreSQL Classification table
   - See full decision trace (gate, emotion, intent, strategy, critic score)

4. ✅ **Tunability**: Strategy behavior editable via YAML
   - Compliance team can edit strategies without code changes
   - Demo editing a YAML file and seeing behavior change

5. ✅ **Compliance-Friendly**: References FCA, FINRA guidelines
   - Strategy files cite regulatory frameworks
   - Critic checks for violations

### Technical Performance Goals

- Response time: <3 seconds per message (zero-shot models + LLM call)
- Accuracy: Gate should block 100% of high-risk keywords
- Audit trail: 100% of interactions logged to database
- Modularity: Each pipeline step testable independently

## Ethical Framework

### Non-Negotiable Principles

1. **Transparency First**
   - User knows they're interacting with AI
   - System decisions are explainable
   - Strategy reasoning is documented

2. **Autonomy Preserved**
   - Always present options, never coerce
   - User makes final decision
   - No dark patterns or manipulation

3. **Vulnerability Protection**
   - Automatic block for distressed users (bereavement, hardship)
   - FCA's 4 vulnerability drivers (health, life events, resilience, capability)
   - Compliance overrides (always block certain intents)

4. **Regulatory Compliance**
   - FCA FG21/1: Fair treatment of vulnerable customers
   - FINRA Rule 2210: Communications with the public
   - No misleading statements, no guarantees

5. **Auditability**
   - Every decision logged
   - Traceable to specific rules/models
   - Reviewable by compliance teams

### Disallowed Behaviors (Hard Constraints)

**NEVER allowed, regardless of gate decision:**

- ❌ Fear tactics ("You'll regret this if you don't...")
- ❌ Urgency pressure ("Limited time offer", "Act now or miss out")
- ❌ Guilt manipulation ("Think of your family's future")
- ❌ Hidden fees/information
- ❌ Persuasion during bereavement/crisis
- ❌ Exploiting cognitive biases maliciously (FOMO, scarcity manipulation)
- ❌ Guaranteeing investment returns
- ❌ Retention attempts during policy cancellation

## Research Foundations

All labels and strategies are **research-backed**, not arbitrary:

### Emotion Labels
- **Source**: Plutchik's Wheel of Emotions (1980)
- **Validation**: Cross-cultural psychological research
- **Why**: 8 basic emotions recognized universally

### Vulnerability Detection
- **Source**: UK Financial Conduct Authority (FCA) FG21/1
- **Framework**: 4 drivers (health, life events, resilience, capability)
- **Why**: Regulatory standard for financial services

### Persuasion Strategies
- **Source**: Robert Cialdini's 7 Principles of Influence
- **Validation**: 40+ years of peer-reviewed research
- **Why**: Scientific basis for ethical persuasion

### Intent Taxonomy
- **Source**: Financial services customer journey research
- **Domains**: Banking, insurance, investment management
- **Why**: Industry-standard categorization

## Key Assumptions

From PRD + Planning:

1. **Data Availability**: Synthetic test data is sufficient for demo (no real customer data needed)
2. **Model Performance**: Zero-shot SLMs (DeBERTa v3) achieve acceptable accuracy without fine-tuning
3. **Ethical Codification**: Ethical constraints can be expressed as rules + strategy constraints
4. **Advisory Role**: System is advisory, not autonomous (final decisions with user)
5. **Language**: English only (no multilingual support)
6. **User Type**: TCS financial services customers (investment, insurance, retirement)

## Timeline

**Total Time**: 1-2 days
**Current Date**: 2026-03-10
**Target**: Demo-ready ASAP for TCS sponsors

### Day 1 Plan
- Morning: Strategy YAMLs + Ethics Gate (3-4h)
- Afternoon: Classifier + Strategy Selector (3-4h)
- Evening: Frontend Integration with Chatscope (30min)

### Day 2 Plan
- Morning: LLM Generator + Critic (4h)
- Afternoon: Orchestrator + Integration + Testing (3h)
- Evening: Demo prep + documentation

## Repository & Contacts

**GitHub**: https://github.com/TCS-COMPSCI-180A
**Local Path**: `/Users/Rounak/chatbot`
**Team Lead**: Shriivanth Gunanidhi (sgunanid@uci.edu)
**Primary Developer**: Rounak Rao (raora@uci.edu)

---
**Last Updated**: 2026-03-10
**Status**: Pre-implementation (planning complete, ready to code)
**Next**: See `.claude/current_status.md` for what to build next
