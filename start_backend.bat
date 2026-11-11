@echo off
echo ===================================================
echo Starting AI Bill Scanner Backend API (FastAPI)...
echo Target Tally Endpoint: http://localhost:9000
echo Backend Server: http://localhost:8000
echo ===================================================
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause

