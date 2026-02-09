#!/bin/bash

# Hanco AI Deployment Script for AWS EC2
# This script deploys both frontend and backend using Docker

set -e  # Exit on error

echo "🚀 Starting Hanco AI Deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Check if firebase-key.json exists
if [ ! -f backend/firebase-key.json ]; then
    echo "❌ Error: backend/firebase-key.json not found!"
    echo "Please upload your Firebase service account key"
    exit 1
fi

echo "📦 Pulling latest code..."
git pull origin main || echo "Not a git repository or already up to date"

echo "🛑 Stopping existing containers..."
docker-compose down

echo "🏗️  Building images..."
docker-compose build

echo "🚀 Starting containers..."
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 10

echo "✅ Deployment complete!"
echo ""
echo "🔗 Your application is now running:"
echo "   Frontend: http://$(curl -s ifconfig.me)"
echo "   Backend API: http://$(curl -s ifconfig.me):8000"
echo "   API Docs: http://$(curl -s ifconfig.me):8000/api/v1/docs"
echo ""
echo "📊 Container status:"
docker-compose ps

echo ""
echo "📝 View logs with:"
echo "   docker-compose logs -f"
