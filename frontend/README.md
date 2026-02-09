# Hanco-AI Frontend

Modern React frontend built with Vite for AI-powered car rental platform.

## Tech Stack

- **Framework**: React 18
- **Build Tool**: Vite
- **Language**: TypeScript
- **Routing**: React Router
- **State Management**: React Query
- **Authentication**: Firebase
- **HTTP Client**: Axios

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
cp .env.example .env.local
# Edit .env.local with your Firebase config
```

3. Run development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
```

## Deployment

Deploy to AWS S3 (see infra/s3/ for scripts)
