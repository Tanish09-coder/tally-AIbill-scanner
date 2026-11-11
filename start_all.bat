@echo off
echo ============================================================
echo AI Bill Scanner + Hinglish Voice Assistant + TallyPrime
echo Starting Backend and Frontend Servers...
echo ============================================================
start "Tally AI Backend" cmd /k "cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "Tally AI Frontend" cmd /k "cd frontend && npm run dev"
echo Both services launched!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
pause

