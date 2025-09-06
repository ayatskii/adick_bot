"""
Simplified main application for quick setup
"""
import logging
from fastapi import FastAPI
from app.config import settings
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Telegram Audio Bot",
    description="Audio transcription and grammar checking bot",
    version="1.0.0",
    debug=settings.log_level == "DEBUG"
)

@app.on_event("startup")
async def startup():
    logger.info("🚀 Bot starting up...")
    logger.info(f"📂 Upload directory: {settings.upload_dir}")

@app.on_event("shutdown") 
async def shutdown():
    logger.info("👋 Bot shutting down...")

@app.get("/")
async def root():
    return {"message": "Telegram Audio Bot", "status": "ready"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
