@echo off
title TALLY AI BILL SCANNER - STARTER
echo ===================================================
echo Starting Tally AI Bill Scanner Full Stack App...
echo ===================================================
start "Tally AI Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
start "Tally AI Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 0.0.0.0 --port 5173"
echo.
echo Both servers launched!
echo - Web UI:  http://localhost:5173/
echo - Backend: http://localhost:8000/
echo ===================================================
timeout /t 5
