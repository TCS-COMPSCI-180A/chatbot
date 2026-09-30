# EthicChat: Ethical Banking Chatbot

EthicChat is a full-stack, ethics-gated banking chatbot built with FastAPI,
React, PostgreSQL, pgvector, LangGraph, and Google Gemini. It can answer normal
banking questions and, when a user uploads a banking document, run an
upload-time RAG pipeline that parses the document, extracts financial figures,
stores searchable chunks, retrieves relevant evidence, and generates a
document-grounded response.

For a demonstration of the system see the [TCS Banking Assistant Demo Video](https://drive.google.com/file/d/1r49VlzncX1MJv8eF7NU8FJJ52sPNgb8V/view?usp=sharing).

This repository is a capstone/prototype codebase. Some older docs and comments
refer to earlier OpenAI/GPT or DeBERTa-based designs; the active chat endpoint
currently uses the LangGraph pipeline under `backend/graph/`.

## Table of Contents

- [Features](#features)
- [Active Runtime Architecture](#active-runtime-architecture)
- [Document RAG Pipeline](#document-rag-pipeline)
- [Safety and Ethics Flow](#safety-and-ethics-flow)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Docker Commands](#docker-commands)
- [Development](#development)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

## Features

- FastAPI backend with a React chat frontend.
- Active LangGraph pipeline for message processing, safety checks, generation,
  critique, and audit logging.
- Optional document upload through `multipart/form-data`.
- PDF parsing with `pdfplumber`.
- OCR fallback with `pytesseract` and Pillow preprocessing.
- DeBERTa zero-shot classification for uploaded banking document type.
- Regex-based extraction of balances, APRs, fees, payments, credit limits, and
  other document-specific figures.
- Gemini embeddings stored in PostgreSQL with pgvector.
- pgvector similarity retrieval with lexical fallback.
- Gemini-based message classifier, ethics gate, strategy selection, generation,
  document insight synthesis, and critic.
- YAML response strategies for neutral, soft-persuasion, blocked, and
  document-grounded responses.
- PostgreSQL audit logging for messages, gate decisions, selected strategies,
  critic scores, and document metadata.
- Docker Compose setup for Postgres, backend, and frontend.

## Active Runtime Architecture

The served chat endpoint is `POST /api/v1/chat` in `backend/routers/chat.py`.
It calls `graph.runner.run_pipeline()`, which invokes the compiled LangGraph in
`backend/graph/graph.py`.

Current active flow:

```text
entry
-> document_ingestion
-> classifier
-> ethics_gate
-> document_analysis
-> generator
-> critic
-> db_logger
```

Blocked flow:

```text
entry
-> document_ingestion
-> classifier
-> ethics_gate
-> db_logger
```

The `generator` node also calls strategy-selection logic internally. There is no
separate strategy node in the active graph.

### Node Summary

- `entry`: initializes request state and loads recent conversation history.
- `document_ingestion`: if document bytes are present, parses, classifies,
  extracts, chunks, embeds, and stores document chunks.
- `classifier`: classifies the user message into emotion, intent, and business
  situation.
- `ethics_gate`: checks whether the system should proceed normally, block, or
  treat the case as ambiguous/high-risk.
- `document_analysis`: if a document is present in the current request, retrieves
  relevant chunks and builds document insights.
- `generator`: selects a strategy, builds a Gemini prompt, and produces a draft
  response.
- `critic`: scores the draft for compliance, grounding, and prohibited language.
  A score below `7.0` can trigger one rewrite.
- `db_logger`: stores the user message, assistant response, and decision trace in
  PostgreSQL.

## Document RAG Pipeline

The document pipeline lives mainly in:

- `backend/document/ingestion.py`
- `backend/document/extractors.py`
- `backend/document/retrieval.py`
- `backend/agents/document_analysis_agent.py`
- `backend/models.py`

Upload-time document flow:

```text
uploaded bytes
-> PDF text extraction
-> OCR fallback if needed
-> DeBERTa document type classification
-> regex financial figure extraction
-> word chunking with overlap
-> Gemini embeddings
-> PostgreSQL/pgvector document_chunks table
```

Question-time document flow:

```text
user question
-> Gemini query embedding
-> pgvector similarity search over stored chunks
-> deterministic metrics from extracted figures
-> optional Gemini document-insight synthesis
-> document_insights passed to generator and critic
```

Current document types:

- `bank_statement`
- `loan_agreement`
- `mortgage_statement`
- `credit_card_statement`
- `cd_savings_statement`
- `credit_report`
- `foreclosure_notice`
- `bankruptcy_filing`
- `unknown`

Document retrieval uses the pgvector `<=>` operator over 768-dimensional Gemini
embeddings. If vector retrieval fails, the retrieval module falls back to a
simple lexical term-overlap ranking over stored chunk text.

Important current behavior: document RAG is wired for the current upload/request.
Document chunks are stored with `session_id`, and there is a helper for looking
up the most recent document for a session, but the active graph does not yet
automatically recover a previously uploaded document on later turns when the
user does not re-upload it.

## Safety and Ethics Flow

The safety architecture has several layers:

1. Document type hard block:
   - `foreclosure_notice`
   - `bankruptcy_filing`

2. Message hard-block keywords:
   - bereavement/loss terms
   - suicide
   - bankruptcy/foreclosure
   - inability to afford payments
   - job-loss terms

3. Prompt-injection pattern checks:
   - ignore instructions
   - reveal hidden/system prompt
   - jailbreak/DAN attempts
   - bypass safety/policy/rules

4. Gemini ethics gate with local policy/guideline lookup tools.

5. YAML strategy constraints for allowed/prohibited response framing.

6. Gemini critic that checks the generated draft for:
   - coercive language
   - prohibited strategy phrases
   - persuasion in blocked contexts
   - fabricated document figures
   - missing document grounding

Blocked responses are generated from safe templates in
`backend/pipeline/blocked_responses.py` and skip normal generation.

## Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic
- LangGraph
- LangChain Core
- PyYAML

### AI / ML

- Google Gemini via `google-genai`
- Gemini 2.5 Flash for classifier, ethics gate, strategy, generator, critic, and
  optional document insight synthesis
- Gemini `models/gemini-embedding-001` for 768-dimensional embeddings
- Hugging Face Transformers
- DeBERTa zero-shot classification for uploaded document type

### Document Processing

- `pdfplumber`
- `pdfminer.six`
- `pytesseract`
- Pillow

### Frontend

- React
- Axios
- React Markdown
- React Scripts

### Database / Vector Search

- PostgreSQL
- pgvector
- `document_chunks` table with `Vector(768)` embeddings

### Infrastructure

- Docker Compose
- Backend Dockerfile based on `python:3.11-slim`
- Frontend Dockerfile based on `node:20-alpine`

### Testing

- pytest
- pytest-asyncio
- React Scripts test runner

## Prerequisites

- Docker 20.10 or higher
- Docker Compose 2.0 or higher
- Git
- Google AI API key for Gemini features
- Tesseract OCR available in the runtime environment if OCR is needed

Verify Docker:

```bash
docker --version
docker-compose --version
```

## Getting Started

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd chatbot
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add:

```bash
GOOGLE_API_KEY=your-google-api-key-here
```

### 3. Start the Application

```bash
docker-compose up
```

Services:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API documentation: http://localhost:8000/docs
- PostgreSQL: localhost:5433

## Docker Commands

Start all services:

```bash
docker-compose up
```

Start in detached mode:

```bash
docker-compose up -d
```

Stop services:

```bash
docker-compose down
```

Stop and remove volumes:

```bash
docker-compose down -v
```

Build or rebuild:

```bash
docker-compose build
docker-compose up --build
```

View logs:

```bash
docker-compose logs
docker-compose logs -f
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
```

Access PostgreSQL:

```bash
docker-compose exec postgres psql -U postgres -d chatbot_db
```

## Development

Backend and frontend are mounted into their containers for hot reload.

Backend hot reload:

- Python changes restart the FastAPI/Uvicorn server.

Frontend hot reload:

- React changes refresh the browser.
- `CHOKIDAR_USEPOLLING=true` and `WATCHPACK_POLLING=true` are set in
  `docker-compose.yml` for containerized development.

Add backend dependencies:

```bash
# Add package to requirements.txt, then:
docker-compose build backend
docker-compose up -d
```

Add frontend dependencies:

```bash
docker-compose exec frontend npm install <package-name>
docker-compose build frontend
docker-compose up -d
```

## Testing

Run all backend tests inside the backend container:

```bash
docker-compose exec backend pytest
```

Run selected tests locally with the project venv:

```bash
venv/bin/python -m pytest backend/tests/test_document_pipeline.py -q
venv/bin/python -m pytest backend/tests/test_ethics_gate.py -q
```

Graph tests require `langgraph` to be installed in the active Python
environment:

```bash
venv/bin/python -m pytest backend/tests/test_graph.py -q
```

Frontend tests:

```bash
docker-compose exec frontend npm test
```

## Project Structure

```text
chatbot/
├── backend/
│   ├── agents/
│   │   ├── critic_agent.py
│   │   ├── document_analysis_agent.py
│   │   ├── generator_agent.py
│   │   └── strategy_agent.py
│   ├── document/
│   │   ├── extractors.py
│   │   ├── ingestion.py
│   │   └── retrieval.py
│   ├── graph/
│   │   ├── graph.py
│   │   ├── routing.py
│   │   ├── runner.py
│   │   └── state.py
│   ├── pipeline/
│   │   ├── blocked_responses.py
│   │   ├── classifier.py
│   │   ├── ethics_gate.py
│   │   ├── generator.py
│   │   ├── orchestrator.py
│   │   └── strategy.py
│   ├── routers/
│   │   ├── chat.py
│   │   └── conversations.py
│   ├── strategies/
│   │   ├── blocked/
│   │   ├── document_grounded/
│   │   ├── neutral/
│   │   └── soft_persuasion/
│   ├── tests/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── docker/
│   └── init-db.sql
├── docs/
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── requirements.txt
└── README.md
```

Note: `backend/graph/` is the active runtime graph. Some files under
`backend/pipeline/` are reusable components or older/alternate pipeline code.

## Environment Variables

See `.env.example` for available configuration.

### Required for AI functionality

- `GOOGLE_API_KEY`: Google AI API key used by Gemini model calls and embeddings.

### Optional / defaulted

- `GEMINI_MODEL`: Gemini generation/critic model, default `gemini-2.5-flash`.
- `POSTGRES_USER`: default `postgres`.
- `POSTGRES_PASSWORD`: default `postgres`.
- `POSTGRES_DB`: default `chatbot_db`.
- `BACKEND_PORT`: default `8000`.
- `FRONTEND_PORT`: default `3000`.
- `CORS_ORIGINS`: default `http://localhost:3000`.
- `SECRET_KEY`: default provided for development by `docker-compose.yml`; change
  for production-like deployments.

## Known Limitations

- This is a prototype/capstone codebase, not a production banking system.
- Multi-turn document follow-up is only partially wired. Uploaded chunks are
  stored with `session_id`, but the active graph does not automatically retrieve
  a previously uploaded document on later turns without a new upload.
- There is no real human escalation backend, ticketing system, or CRM
  integration.
- There is no production authentication/authorization flow.
- There is no explicit PII redaction, retention policy, or encryption layer in
  application code.
- Retrieval quality, classifier accuracy, safety accuracy, latency, load, and
  cost are not benchmarked in the repo.
- Some older docs/migrations mention OpenAI embeddings or 1536-dimensional
  vectors; current active code uses Gemini embeddings with 768 dimensions.
- Some code comments still mention DeBERTa for message-level safety; current
  active message classifier and ethics gate are Gemini-based, while DeBERTa is
  used for uploaded document type classification.

## Troubleshooting

### Port Already in Use

Change ports in `.env`:

```bash
BACKEND_PORT=8001
FRONTEND_PORT=3001
POSTGRES_PORT=5433
```

### Database Connection Issues

```bash
docker-compose ps
docker-compose logs postgres
docker-compose restart postgres
```

### Missing Python Dependencies

Rebuild the backend:

```bash
docker-compose build backend
docker-compose up -d backend
```

### Missing Node Dependencies

Rebuild the frontend:

```bash
docker-compose build frontend
docker-compose up -d frontend
```

### Hot Reload Not Working

Check that polling environment variables are set:

```bash
CHOKIDAR_USEPOLLING=true
WATCHPACK_POLLING=true
```

### Clear Everything and Start Fresh

This deletes database data:

```bash
docker-compose down -v
docker-compose rm -f
docker-compose build --no-cache
docker-compose up
```

## Additional Resources

- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- Docker: https://docs.docker.com/
- pgvector: https://github.com/pgvector/pgvector
- Google AI Studio: https://aistudio.google.com/
