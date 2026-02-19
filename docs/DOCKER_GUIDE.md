# Docker Development Guide

## Quick Start Commands

### First Time Setup
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env and add your API keys
# Required: OPENAI_API_KEY and ANTHROPIC_API_KEY

# 3. Start all services
docker-compose up
```

### Daily Development

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Service URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

## Hot-Reload Testing

### Backend Hot-Reload
1. Edit `backend/main.py`
2. Save the file
3. Watch the terminal - server should restart automatically
4. Test at http://localhost:8000

### Frontend Hot-Reload
1. Edit `frontend/src/App.js`
2. Save the file
3. Browser should refresh automatically
4. If not, check browser console and ensure CHOKIDAR_USEPOLLING=true in .env

## Database Access

### Connect to PostgreSQL
```bash
docker-compose exec postgres psql -U postgres -d chatbot_db
```

### Useful SQL Commands
```sql
-- List all extensions
SELECT * FROM pg_extension;

-- Verify pgvector is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- List all tables
\dt

-- Exit psql
\q
```

## Troubleshooting

### Services won't start
```bash
# Check what's running
docker-compose ps

# View service logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres

# Restart a specific service
docker-compose restart backend
```

### Port conflicts
Edit `.env` file:
```
BACKEND_PORT=8001
FRONTEND_PORT=3001
POSTGRES_PORT=5433
```

### Clean restart
```bash
# Stop and remove everything
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache

# Start again
docker-compose up
```

### Frontend not connecting to backend
1. Check backend is running: http://localhost:8000/health
2. Verify REACT_APP_API_URL in .env matches backend URL
3. Check CORS_ORIGINS in .env includes frontend URL

## Development Workflow

### Adding Python Dependencies
1. Add package to `backend/requirements.txt`
2. Rebuild backend:
   ```bash
   docker-compose build backend
   docker-compose up -d
   ```

### Adding Node Dependencies
1. Add to `frontend/package.json` or:
   ```bash
   docker-compose exec frontend npm install <package-name>
   ```
2. Rebuild if needed:
   ```bash
   docker-compose build frontend
   docker-compose up -d
   ```

### Running Tests
```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests
docker-compose exec frontend npm test
```

### Database Migrations (when implemented)
```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback migration
docker-compose exec backend alembic downgrade -1
```

## Performance Tips

1. **Use volume caching**: Already configured in docker-compose.yml
2. **Keep containers running**: Use `docker-compose up -d` for background
3. **Limit rebuilds**: Only rebuild when dependencies change
4. **Clean up**: Periodically run `docker system prune` to free space

## Environment Variables Checklist

Required for full functionality:
- [ ] OPENAI_API_KEY
- [ ] ANTHROPIC_API_KEY
- [ ] SECRET_KEY (for production)

Optional but recommended:
- [ ] POSTGRES_PASSWORD (change from default)
- [ ] JWT_SECRET_KEY
- [ ] LOG_LEVEL

## Health Checks

### Backend Health
```bash
curl http://localhost:8000/health
```

### Database Health
```bash
docker-compose exec postgres pg_isready -U postgres
```

### Frontend Health
Visit http://localhost:3000 - should show the app

## Common Issues and Solutions

### "Address already in use"
- Change ports in `.env` file
- Or stop conflicting services

### "Cannot connect to database"
- Wait for PostgreSQL health check to pass
- Check `docker-compose logs postgres`
- Verify DATABASE_URL in .env

### "Module not found" errors
- Rebuild the affected service
- Check requirements.txt or package.json

### Hot-reload not working
- Ensure volume mounts are correct
- On Windows: Enable CHOKIDAR_USEPOLLING in .env
- Restart the service

## Monitoring

### View all service status
```bash
docker-compose ps
```

### View resource usage
```bash
docker stats
```

### Follow all logs
```bash
docker-compose logs -f
```

### Follow specific service logs
```bash
docker-compose logs -f backend
```
