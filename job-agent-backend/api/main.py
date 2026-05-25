"""
FastAPI main application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import upload, jobs, download
from utils.db import init_db
from utils.file_helpers import init_directories


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for app startup and shutdown events.
    """
    # Startup
    logger.info("Initializing database and directories...")
    init_db()
    init_directories()
    logger.info("Application started")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title="Job Agent API",
    description="Multi-agent job application automation system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(download.router)


@app.get("/")
async def root():
    """
    Root endpoint - health check.
    """
    return {
        "message": "Job Agent API is running",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /api/upload",
            "jobs": "GET /api/jobs?session_id=<uuid>",
            "download": "GET /api/download?file=<filename>",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
