# Setup Instructions

## Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Google API Key (free): https://aistudio.google.com/apikey

## Setup Steps

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your GOOGLE_API_KEY
nano .env
```

### 2. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 3. Start PostgreSQL
```bash
# Start database
docker-compose up -d postgres

# Wait for health check
sleep 10
```

### 4. Initialize Database
```bash
python3 backend/init_db.py
```

Expected output: `✅ DATABASE INITIALIZATION COMPLETE`

## Running the Test

### Prepare Test PDF
1. Open `backend/test_e2e_with_document.py`
2. Update line 83 with path to any bank statement PDF
3. Or create a PDF using the mock text in lines 28-72

### Run Test
```bash
python3 backend/test_e2e_with_document.py
```

Expected: `🎉 ALL CHECKS PASSED (6/6)`

## Troubleshooting

**"API key expired"**
- Get new key from https://aistudio.google.com/apikey
- Update `.env` file

**"ModuleNotFoundError"**
- Run from project root, not inside `backend/`

**"Connection refused"**
- Check Docker: `docker ps | grep postgres`
- Restart: `docker-compose restart postgres`

## Stopping Services
```bash
docker-compose down
```
