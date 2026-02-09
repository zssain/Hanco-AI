# Hanco-AI - AI-Powered Car Rental Platform

Modern, scalable car rental platform for Saudi Arabia with AI-driven features.

## 🏗️ Architecture

**Monorepo Structure:**
- `backend/` - FastAPI backend with Firebase, ONNX ML, and AI chatbot
- `frontend/` - React + Vite frontend
- `infra/` - AWS deployment scripts (EC2, S3)

## 🚀 Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11)
- **Auth**: Firebase Authentication
- **Database**: Firestore (NoSQL)
- **AI Chatbot**: Gemini API (primary), OpenAI (fallback)
- **ML Pricing**: ONNX Runtime
- **Weather**: Open-Meteo API (free)
- **Scraping**: Crawl4AI (Yelo, Lumi, Budget, Hertz)
- **Payments**: Simulator

### Frontend
- **Framework**: React 18
- **Build**: Vite
- **Language**: TypeScript
- **Routing**: React Router
- **State**: React Query
- **Auth**: Firebase

### Deployment
- **Backend**: AWS EC2
- **Frontend**: AWS S3 + CloudFront

## 📁 Project Structure

```
hanco-ai/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Config, Firebase, Security
│   │   ├── models/          # Firestore models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── services/        # Business logic
│   └── ml/
│       ├── training/        # Model training
│       └── models/          # ONNX models
├── frontend/
│   └── src/
│       ├── components/      # React components
│       ├── pages/           # Page components
│       ├── hooks/           # Custom hooks
│       └── utils/           # Utilities
└── infra/
    ├── ec2/                 # Backend deployment
    └── s3/                  # Frontend deployment
```

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11.x (backend)
- Node.js 18+ (frontend)
- Firebase project configured
- Gemini API key

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   - Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-key.json
#   - Set GEMINI_API_KEY=your-key-here
#   - Set other Firebase config values

# Run development server
uvicorn app.main:app --reload --port 8000
```

Backend will run at `http://localhost:8000`
API docs at `http://localhost:8000/api/v1/docs`

### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with:
#   - VITE_API_BASE_URL=http://localhost:8000
#   - Firebase web config values

# Run development server
npm run dev
```

Frontend will run at `http://localhost:5173`

## 🚀 Production Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for complete AWS deployment instructions.

**Architecture:**
- Backend: AWS EC2 (FastAPI + Nginx)
- Frontend: AWS S3 + CloudFront
- Database: Firebase Firestore
- Secrets: AWS Secrets Manager (recommended) or environment variables

## 🔑 Required API Keys

1. **Firebase** - Authentication & Firestore
2. **Gemini API** - AI Chatbot (primary)
3. **OpenAI API** - AI Chatbot (fallback)
4. **Open-Meteo** - Weather (no key needed - free!)

## 📦 Features

- ✅ User authentication (Firebase)
- ✅ Vehicle inventory management
- ✅ AI-powered chatbot (Gemini/OpenAI)
- ✅ Dynamic ML pricing (ONNX)
- ✅ Weather-based pricing adjustments
- ✅ Competitor price monitoring (Crawl4AI)
- ✅ Booking management
- ✅ Payment simulation
- ✅ Admin dashboard
- ✅ Real-time analytics

## 🚀 Deployment

See `infra/` directory for deployment scripts.

## 📝 License

Proprietary - Hanco-AI
