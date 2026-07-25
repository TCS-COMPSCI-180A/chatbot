# Ethical Persuasion Chatbot

A sophisticated chatbot application built with FastAPI, React, and PostgreSQL with pgvector for semantic search capabilities.

For a demonstration of the system see the [Home Score Demo Video](https://drive.google.com/file/d/1SAmxpryPY2NFLeOFAla22SGvy0kr1hxs/view?usp=sharing).


## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Docker Commands](#docker-commands)
- [Development](#development)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

## ✨ Features

- **FastAPI Backend**: High-performance Python backend with async support
- **React Frontend**: Modern, responsive user interface
- **PostgreSQL + pgvector**: Vector similarity search for semantic capabilities
- **Docker Support**: Fully containerized development and deployment
- **Hot-Reload**: Automatic code reloading during development
- **AI Integration**: Google Gemini (generation + embeddings) with ethics-gated pipeline

## 🛠 Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **pgvector**: Vector similarity search
- **Uvicorn**: ASGI server

### Frontend
- **React**: UI library
- **Axios**: HTTP client
- **React Router**: Navigation

### Database
- **PostgreSQL**: Relational database
- **pgvector**: Vector extension for embeddings

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

- **Docker**: Version 20.10 or higher ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose**: Version 2.0 or higher (usually included with Docker Desktop)
- **Git**: For version control

To verify your installation:

```bash
docker --version
docker-compose --version
```

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd chatbot
```

### 2. Set Up Environment Variables

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```bash
# Required: Add your Google AI API key
# Get one free at: https://aistudio.google.com/apikey
GOOGLE_API_KEY=your-google-api-key-here

# Optional: Modify ports and other settings as needed
```

### 3. Start the Application

```bash
docker-compose up
```

The services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5433

## 🐳 Docker Commands

### Basic Operations

#### Start all services
```bash
docker-compose up
```

#### Start services in detached mode (background)
```bash
docker-compose up -d
```

#### Stop all services
```bash
docker-compose down
```

#### Stop and remove volumes (⚠️ deletes database data)
```bash
docker-compose down -v
```

### Building and Rebuilding

#### Build or rebuild services
```bash
docker-compose build
```

#### Rebuild and start services
```bash
docker-compose up --build
```

#### Rebuild a specific service
```bash
docker-compose build backend
docker-compose build frontend
```

### Viewing Logs

#### View logs from all services
```bash
docker-compose logs
```

#### Follow logs in real-time
```bash
docker-compose logs -f
```

#### View logs for a specific service
```bash
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
```

### Service Management

#### Restart a specific service
```bash
docker-compose restart backend
```

#### Stop a specific service
```bash
docker-compose stop backend
```

#### Start a specific service
```bash
docker-compose start backend
```

### Database Operations

#### Access PostgreSQL shell
```bash
docker-compose exec postgres psql -U postgres -d chatbot_db
```

#### Run database migrations (when implemented)
```bash
docker-compose exec backend alembic upgrade head
```

#### Create a new migration
```bash
docker-compose exec backend alembic revision --autogenerate -m "description"
```

### Troubleshooting Commands

#### Check service status
```bash
docker-compose ps
```

#### View resource usage
```bash
docker stats
```

#### Execute command in running container
```bash
docker-compose exec backend bash
docker-compose exec frontend sh
```

#### Remove all stopped containers
```bash
docker-compose rm
```

#### Clean up Docker system (⚠️ removes unused data)
```bash
docker system prune -a
```

## 💻 Development

### Hot-Reload

Both frontend and backend support hot-reloading:

- **Backend**: Changes to Python files automatically restart the FastAPI server
- **Frontend**: Changes to React components automatically refresh the browser

### Adding Dependencies

#### Backend (Python)
1. Add the package to `backend/requirements.txt`
2. Rebuild the backend service:
   ```bash
   docker-compose build backend
   docker-compose up -d
   ```

#### Frontend (Node.js)
1. Add the package to `frontend/package.json`
2. Rebuild the frontend service:
   ```bash
   docker-compose build frontend
   docker-compose up -d
   ```

Or install directly in the running container:
```bash
docker-compose exec frontend npm install <package-name>
```

### Running Tests

```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests
docker-compose exec frontend npm test
```

## 📁 Project Structure

```
chatbot/
├── backend/                    # FastAPI backend application
│   ├── pipeline/               # Core AI pipeline (runs in order, never skip steps)
│   │   ├── ethics_gate.py      # Rules + zero-shot check (runs first — blocks/allows)
│   │   ├── classifier.py       # Zero-shot: emotion, intent, situation
│   │   ├── strategy.py         # Emotion-first YAML strategy selection
│   │   ├── generator.py        # Gemini LLM with structured prompts
│   │   ├── critic.py           # Score + optional rewrite (one pass max)
│   │   └── orchestrator.py     # Coordinates the full pipeline
│   ├── strategies/             # Human-editable YAML strategy files
│   │   ├── blocked/
│   │   ├── soft_persuasion/
│   │   └── neutral/
│   ├── routers/
│   │   ├── chat.py             # Main chat endpoint
│   │   └── conversations.py    # Conversation CRUD
│   ├── models.py               # SQLAlchemy models
│   ├── database.py             # DB session management
│   ├── main.py                 # Application entry point
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # React frontend application
│   ├── Dockerfile
│   ├── package.json
│   └── src/
├── docker/
│   └── init-db.sql             # Database initialization
├── docker-compose.yml
├── .env.example                # Environment variables template
├── .gitignore
└── README.md
```

## 🔧 Environment Variables

See [.env.example](.env.example) for all available configuration options.

### Required Variables

- `GOOGLE_API_KEY`: Your Google AI API key — used for Gemini LLM generation, embeddings, and the critic agent. Get one free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- `SECRET_KEY`: Secret key for session management (change in production)

### Optional Variables

- `POSTGRES_USER`: Database user (default: `postgres`)
- `POSTGRES_PASSWORD`: Database password (default: `postgres`)
- `POSTGRES_DB`: Database name (default: `chatbot_db`)
- `POSTGRES_PORT`: Host-side PostgreSQL port (default: `5433`)
- `DATABASE_URL`: Full connection string (default: `postgresql://postgres:postgres@localhost:5433/chatbot_db`)
- `BACKEND_PORT`: Backend port (default: `8000`)
- `FRONTEND_PORT`: Frontend port (default: `3000`)
- `CORS_ORIGINS`: Allowed CORS origins (default: `http://localhost:3000`)

## 🔍 Troubleshooting

### Port Already in Use

If you see an error about ports already being in use:

```bash
# Change ports in .env file
BACKEND_PORT=8001
FRONTEND_PORT=3001
POSTGRES_PORT=5433
```

### Database Connection Issues

```bash
# Check if PostgreSQL is healthy
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Hot-Reload Not Working

For frontend hot-reload issues on Windows:

```bash
# Ensure polling is enabled in .env
CHOKIDAR_USEPOLLING=true
WATCHPACK_POLLING=true
```

### Permission Issues (Linux/Mac)

```bash
# Fix permission issues
sudo chown -R $USER:$USER .
```

### Clear Everything and Start Fresh

```bash
# Stop all services and remove volumes
docker-compose down -v

# Remove all images
docker-compose rm -f

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Docker Documentation](https://docs.docker.com/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)

## 📝 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]

---

**Questions or Issues?** Please open an issue on GitHub.
