# Deprecated Deployment Configurations

This folder contains deployment configurations that are **NO LONGER SUPPORTED** and have been deprecated in favor of AWS-first deployment.

## ⚠️ DO NOT USE THESE FILES

These files have been moved here because they:
1. Contained hardcoded secrets and API keys
2. Are not part of the official deployment strategy
3. May reference outdated infrastructure

## Deprecated Files

- `render.yaml.deprecated` - Render.com deployment config (replaced by AWS EC2)
- `vercel.json.deprecated` - Vercel deployment config (replaced by AWS S3+CloudFront)
- `backend-vercel.json.deprecated` - Backend Vercel config
- `frontend-vercel.json.deprecated` - Frontend Vercel config
- `railway.json.deprecated` - Railway deployment config
- `vercel-env-setup.txt.deprecated` - Vercel environment setup

## Current Deployment Strategy

**Backend:** AWS EC2 with FastAPI
- See `infra/ec2/` for deployment scripts
- Use `backend/.env.example` for configuration

**Frontend:** AWS S3 + CloudFront
- See `infra/s3/` for deployment scripts
- Use `frontend/.env.example` for configuration

## Security Notice

⚠️ **All API keys and secrets in these files have been EXPOSED and should be considered COMPROMISED.**

If you deployed using these files:
1. Rotate all API keys immediately (Gemini, Firebase, etc.)
2. Check Firebase audit logs for unauthorized access
3. Update to AWS deployment with proper secrets management

## Documentation

For current deployment instructions, see:
- `README.md` - Local development setup
- `DEPLOYMENT.md` - AWS production deployment guide
