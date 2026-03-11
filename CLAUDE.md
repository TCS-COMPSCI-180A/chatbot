# TCS Ethical Persuasion Chatbot - AI Context

## 🎯 Project Identity
**What**: Ethically-grounded AI persuasion chatbot for financial services
**Sponsor**: Tata Consultancy Services (COMPSCI 180A/B)
**Ethics-First**: Determines WHETHER to persuade before HOW to respond
**Timeline**: MVP demo in 1-2 days

## 📋 Context Architecture (Progressive Disclosure)

**Before making ANY changes, read:**
1. `.claude/project_overview.md` - Full PRD summary, goals, constraints
2. `.claude/architecture.md` - System design, pipeline flow, research basis
3. `.claude/current_status.md` - What's built, what's next, active tasks

**When implementing features, consult:**
- `.claude/implementation_plan.md` - Step-by-step build order, priorities
- `.claude/research_foundations.md` - Label taxonomies, strategy frameworks

**After making changes:**
- Update `.claude/current_status.md` with progress
- Document architectural decisions in `.claude/architecture.md`

## 🚫 What NOT to Do

- **Never use AI for linting** - Use formatters (black, prettier)
- **Never bloat context** - Keep responses concise, code modular
- **Never implement features not in the plan** - Stick to MVP scope
- **Never skip the ethics gate** - Always gate → classify → strategy → generate
- **Never auto-generate this file** - Manual updates only for quality

## 🔑 Core Development Principles

**Context First**: Read `.claude/current_status.md` before every coding session
**Sequential Pipeline**: Ethics Gate → Classifier → Strategy → LLM → Critic (no shortcuts)
**Research-Backed**: All labels/strategies must trace to Plutchik/Cialdini/FCA
**Auditability**: Log EVERYTHING to database (gate, classification, strategy, critic score)
**Fail Safe**: When uncertain, default to BLOCKED/informational response

## 🛠 Tech Stack
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + pgvector
- **AI**: Hugging Face Transformers (DeBERTa v3) + OpenAI GPT-4o-mini
- **Format**: Strategy files are YAML (not Python)
- **Environment**: Docker Compose

## 📁 Key Files to Know
```
backend/
├── pipeline/           # Core AI pipeline (NEVER modify order)
│   ├── ethics_gate.py  # Rules + zero-shot (MUST run first)
│   ├── classifier.py   # 3 zero-shot calls (emotion, intent, situation)
│   ├── strategy.py     # Emotion-first selection + compliance overrides
│   ├── generator.py    # LLM with structured prompts
│   ├── critic.py       # Score + optional rewrite (ONE time max)
│   └── orchestrator.py # Coordinates all steps
├── strategies/         # YAML files (human-editable)
│   ├── blocked/
│   ├── soft_persuasion/
│   └── neutral/
├── models.py           # Conversation, Message, Classification tables
├── database.py         # DB session management
└── routers/
    ├── chat.py         # Main chat endpoint (calls orchestrator)
    └── conversations.py # CRUD endpoints
```

## 🎬 Common Tasks

**Start coding session:**
```bash
cat .claude/current_status.md  # Read what's done/next
```

**After implementing a feature:**
```bash
# Update current status with what you built
# Add architectural decisions to architecture.md if needed
```

**Testing the pipeline:**
```python
from backend.pipeline.orchestrator import run_pipeline
result = run_pipeline("test message")
print(result["debug"])  # See full decision trace
```

## 📊 Success Metrics for TCS Demo

1. **Ethics Gate blocks vulnerable cases** (bereavement, hardship)
2. **Classifier correctly identifies emotion** (anxiety → social proof)
3. **Strategy selection is transparent** (YAML files reviewable by compliance)
4. **Critic catches violations** (persuasion in blocked contexts)
5. **Full auditability** (every decision logged to DB)

## 🔄 Continuous Updates

This file is **manually curated**. The `.claude/` directory is **actively maintained** and updated after every significant change. Trust the context files - they're the source of truth.

---
Last Updated: 2026-03-10
Current Phase: Pre-implementation (planning complete, ready to code)
