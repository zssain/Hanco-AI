"""
Hanco-AI Backend - Main Application Entry Point
FastAPI application with Firebase, ONNX, and AI integration
Includes: Rate limiting, security headers, CORS, request size limits
"""
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
from typing import Callable

from app.core.config import settings
from app.core.firebase import firebase_client
from app.core.security import safe_log_error, redact_sensitive_data
from app.api.v1.router import api_router

# Configure logging with redaction
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== Rate Limiter Setup ====================
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    enabled=settings.RATE_LIMIT_ENABLED,
    storage_uri="memory://"  # For production, use Redis: "redis://localhost:6379"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Manages startup and shutdown events.
    """
    # ==================== Startup ====================
    logger.info("🚀 Starting Hanco AI Backend...")
    logger.info(f"📝 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"🔥 Firebase Project: {settings.FIREBASE_PROJECT_ID}")
    logger.info(f"🤖 Gemini API: {'✅ Configured' if settings.GEMINI_API_KEY else '❌ Not configured'}")
    logger.info(f"💳 Payment Simulator: {'✅ ENABLED (DEV)' if settings.ENABLE_PAYMENT_SIMULATOR else '❌ DISABLED'}")
    logger.info(f"🛡️  Rate Limiting: {'✅ Enabled' if settings.RATE_LIMIT_ENABLED else '❌ Disabled'}")
    logger.info(f"📊 Max Request Size: {settings.MAX_REQUEST_SIZE_MB}MB")
    logger.info(f"📚 API Docs: http://localhost:8000{settings.API_V1_PREFIX}/docs")
    
    # Initialize Firebase (already initialized in firebase.py)
    try:
        _ = firebase_client.db
        logger.info("✅ Firebase connection verified")
    except Exception as e:
        logger.error(f"❌ Firebase initialization error: {e}")
    
    # Start background scheduler for competitor scraping and price updates
    try:
        from app.core.scheduler import start_scheduler, get_scheduler_status
        start_scheduler()
        status = get_scheduler_status()
        logger.info(f"📅 Background Scheduler: {status['status']}")
        for job in status.get('jobs', []):
            logger.info(f"   └─ {job['name']}: next run at {job.get('next_run', 'N/A')}")
    except Exception as e:
        logger.warning(f"⚠️ Background scheduler failed to start: {e}")
    
    logger.info("✅ Application startup complete")
    
    yield
    
    # ==================== Shutdown ====================
    logger.info("👋 Shutting down Hanco AI Backend...")
    
    # Stop background scheduler
    try:
        from app.core.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler shutdown error: {e}")
    
    logger.info("✅ Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="AI-powered car rental platform for Saudi Arabia - Secured",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==================== Request Size Limit Middleware ====================
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size to prevent DoS"""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length:
            max_size = settings.MAX_REQUEST_SIZE_MB * 1024 * 1024  # Convert MB to bytes
            if int(content_length) > max_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": f"Request body too large. Maximum {settings.MAX_REQUEST_SIZE_MB}MB allowed."}
                )
    
    response = await call_next(request)
    return response


# ==================== Security Headers Middleware ====================
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # XSS Protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS (only in production with HTTPS)
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Conservative CSP (can be expanded as needed)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://firestore.googleapis.com https://identitytoolkit.googleapis.com; "
        "font-src 'self' data:;"
    )
    
    # Permissions Policy (Feature-Policy replacement)
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response


# ==================== CORS Middleware ====================
# Use FastAPI's built-in CORS middleware for better compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Guest-Id"],
    max_age=600,
)


# ==================== Logging Middleware ====================
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    """Log all HTTP requests with redaction"""
    start_time = time.time()
    
    # Redact sensitive info from path
    safe_path = redact_sensitive_data(str(request.url.path))
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log request details (with redaction)
    logger.info(
        f"{request.method} {safe_path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    # Add custom header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# ==================== Error Handlers ====================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with safe error messages"""
    # Log full error server-side with redaction
    safe_log_error("Unhandled exception", exc)
    
    # Return generic error to client (don't leak internal details)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred" if settings.ENVIRONMENT == "production" else str(exc)
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with safe error messages"""
    # For production, sanitize 500 errors
    if settings.ENVIRONMENT == "production" and exc.status_code >= 500:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "An internal error occurred"}
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# ==================== Root Endpoints ====================
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "operational",
        "docs": f"{settings.API_V1_PREFIX}/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check Firebase connection
        _ = firebase_client.db.collection("users").limit(1).get()
        firebase_status = "healthy"
    except Exception as e:
        logger.error(f"Firebase health check failed: {e}")
        firebase_status = "unhealthy"
    
    return {
        "status": "healthy" if firebase_status == "healthy" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "firebase": firebase_status,
            "api": "healthy"
        }
    }


# ==================== Include API Router ====================
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ==================== Vercel Handler ====================
# Export app for Vercel serverless deployment
handler = app


# ==================== Run Application ====================
if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting uvicorn server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
