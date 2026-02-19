# Docker Setup Verification Checklist

## ✅ Pre-flight Checklist

Before running `docker-compose up`, verify:

### 1. Environment Configuration
- [ ] Copied `.env.example` to `.env`
- [ ] Added `OPENAI_API_KEY` to `.env`
- [ ] Added `ANTHROPIC_API_KEY` to `.env`
- [ ] (Optional) Changed default `POSTGRES_PASSWORD`

### 2. Docker Installation
```bash
# Verify Docker is installed
docker --version
# Should show: Docker version 20.10+ or higher

# Verify Docker Compose is installed
docker-compose --version
# Should show: Docker Compose version 2.0+ or higher

# Verify Docker is running
docker ps
# Should list running containers (or be empty, but not error)
```

## 🚀 First Launch Test

### Step 1: Start Services
```bash
docker-compose up
```

Expected output should include:
- ✓ Building backend... (if first time)
- ✓ Building frontend... (if first time)
- ✓ Pulling pgvector image...
- ✓ Creating network
- ✓ Starting postgres...
- ✓ Starting backend...
- ✓ Starting frontend...

### Step 2: Verify Services are Running

Open new terminal and run:
```bash
docker-compose ps
```

Expected output:
```
NAME                   STATUS              PORTS
chatbot-backend        Up                  0.0.0.0:8000->8000/tcp
chatbot-frontend       Up                  0.0.0.0:3000->3000/tcp
chatbot-postgres       Up (healthy)        0.0.0.0:5432->5432/tcp
```

### Step 3: Test Each Service

#### Backend API Test
```bash
# Method 1: Using curl
curl http://localhost:8000/health

# Method 2: Using PowerShell
Invoke-WebRequest -Uri http://localhost:8000/health

# Method 3: Open in browser
# Visit: http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "development"
}
```

#### API Documentation Test
Open in browser: http://localhost:8000/docs

Should show: FastAPI Swagger UI documentation

#### Frontend Test
Open in browser: http://localhost:3000

Should show: 
- Chatbot welcome page
- System status indicators
- All status = ✓ Connected/Running

#### Database Test
```bash
docker-compose exec postgres psql -U postgres -d chatbot_db -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

Expected output:
```
 oid  | extname | extowner | extnamespace | ... 
------+---------+----------+--------------+-----
 xxxxx| vector  |       10 |           xx | ...
```

## 🔥 Hot-Reload Verification

### Backend Hot-Reload Test

1. Keep `docker-compose up` running in one terminal
2. Open `backend/main.py` in editor
3. Find the root endpoint (around line 25):
```python
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Ethical Persuasion Chatbot API is running",
        "version": "0.1.0"
    }
```

4. Change version to "0.1.1" and save
5. Watch terminal - should see:
```
INFO:     Detected file change in 'main.py'
INFO:     Reloading...
```

6. Test the change:
```bash
curl http://localhost:8000/
```

Should show version "0.1.1"

### Frontend Hot-Reload Test

1. Keep `docker-compose up` running
2. Open `frontend/src/App.js`
3. Find the h1 tag (around line 30):
```jsx
<h1>🤖 Ethical Persuasion Chatbot</h1>
```

4. Change to: `<h1>🤖 My Awesome Chatbot</h1>`
5. Save the file
6. Watch browser at http://localhost:3000
   - Should automatically refresh
   - Should show new title

## 🗄️ Database Volume Persistence Test

### Test 1: Data Persists After Restart
```bash
# Create a test table
docker-compose exec postgres psql -U postgres -d chatbot_db -c "CREATE TABLE test (id INT, name TEXT);"

# Insert test data
docker-compose exec postgres psql -U postgres -d chatbot_db -c "INSERT INTO test VALUES (1, 'Test Data');"

# Stop services
docker-compose down

# Start services again
docker-compose up -d

# Verify data still exists
docker-compose exec postgres psql -U postgres -d chatbot_db -c "SELECT * FROM test;"
```

Expected: Should see the test data

### Test 2: Data Deleted with Volume Flag
```bash
# Stop and remove volumes
docker-compose down -v

# Start again
docker-compose up -d

# Try to query test table
docker-compose exec postgres psql -U postgres -d chatbot_db -c "SELECT * FROM test;"
```

Expected: Should error (table doesn't exist) - volumes were wiped

## 📊 Performance Check

### Check Resource Usage
```bash
docker stats --no-stream
```

Typical resource usage:
- Backend: ~100-200MB RAM
- Frontend: ~200-300MB RAM  
- Postgres: ~50-100MB RAM

## 🐛 Troubleshooting Tests

### If Backend Won't Start

Check logs:
```bash
docker-compose logs backend
```

Common issues:
- Missing dependencies in requirements.txt
- Syntax error in main.py
- Port 8000 already in use

Solution:
```bash
# View detailed logs
docker-compose logs backend

# Rebuild
docker-compose build backend

# Try again
docker-compose up
```

### If Frontend Won't Start

Check logs:
```bash
docker-compose logs frontend
```

Common issues:
- node_modules issues
- Port 3000 already in use
- Invalid package.json

Solution:
```bash
# Rebuild
docker-compose build frontend --no-cache

# Try again
docker-compose up
```

### If Database Won't Connect

Check health:
```bash
docker-compose ps postgres
```

Should show: `Up (healthy)`

If not healthy:
```bash
# View logs
docker-compose logs postgres

# Restart
docker-compose restart postgres

# Wait for healthy status
docker-compose ps postgres
```

## ✅ Success Criteria

Your Docker environment is properly configured if:

- [ ] `docker-compose up` starts all 3 services without errors
- [ ] http://localhost:8000/health returns JSON with "healthy" status
- [ ] http://localhost:8000/docs shows FastAPI documentation
- [ ] http://localhost:3000 shows the frontend application
- [ ] Frontend shows "Backend API: ✓ Connected"
- [ ] PostgreSQL responds to queries
- [ ] pgvector extension is installed and active
- [ ] Backend hot-reload works (file changes restart server)
- [ ] Frontend hot-reload works (file changes refresh browser)
- [ ] Database data persists between restarts (without -v flag)

## 🎉 Next Steps After Verification

Once all checks pass:

1. Start building your chatbot features
2. Implement chat API endpoints
3. Create frontend chat UI components
4. Connect to AI models (OpenAI/Anthropic)
5. Add database models and migrations
6. Implement conversation history

## 📝 Notes

- First `docker-compose up` takes longer (building images)
- Subsequent starts are much faster (using cached images)
- Hot-reload may take 2-3 seconds to trigger
- Windows users: Ensure WSL2 backend is enabled for best performance
- Mac users: Consider increasing Docker Desktop memory allocation to 4GB+

---

**Need Help?** Check [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for detailed troubleshooting.
