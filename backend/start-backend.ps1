# Backend Startup Script for Hanco-AI
# Run this from anywhere: .\start-backend.ps1

# Get the script directory (backend folder)
$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BackendDir

Write-Host "Starting Hanco-AI Backend..." -ForegroundColor Green
Write-Host "Backend Directory: $BackendDir" -ForegroundColor Cyan
Write-Host "Starting server on http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start uvicorn from the backend directory
& "$BackendDir\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
