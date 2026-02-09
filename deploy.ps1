# Hanco AI Deployment Script for AWS EC2 (PowerShell)
# This script deploys both frontend and backend using Docker

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Hanco AI Deployment..." -ForegroundColor Green

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "❌ Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env file from .env.example" -ForegroundColor Yellow
    exit 1
}

# Check if firebase-key.json exists
if (-not (Test-Path backend\firebase-key.json)) {
    Write-Host "❌ Error: backend\firebase-key.json not found!" -ForegroundColor Red
    Write-Host "Please upload your Firebase service account key" -ForegroundColor Yellow
    exit 1
}

Write-Host "📦 Pulling latest code..." -ForegroundColor Cyan
git pull origin main

Write-Host "🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

Write-Host "🏗️  Building images..." -ForegroundColor Cyan
docker-compose build

Write-Host "🚀 Starting containers..." -ForegroundColor Green
docker-compose up -d

Write-Host "⏳ Waiting for services to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Container status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "📝 View logs with:" -ForegroundColor Cyan
Write-Host "   docker-compose logs -f" -ForegroundColor White
