"""
Main application module for the TechTree API.
"""

# pylint: disable=wrong-import-position,logging-fstring-interpolation

import sys
import os
from contextlib import asynccontextmanager # Import asynccontextmanager

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
# Remove direct import of SQLiteDatabaseService
# Import the shared db_service instance from dependencies
from backend.dependencies import db_service
from backend.logger import logger

# Define the lifespan context manager
@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Manages application startup and shutdown events.
    """
    # Startup logic would go here (if any)
    logger.info("Application startup...")
    yield
    # Shutdown logic
    logger.info("Application shutdown...")
    # Use the imported shared db_service instance
    db_service.close()
    print("Database connection closed.") # Keep print for visibility if desired

# Instantiate FastAPI app with the lifespan manager
app = FastAPI(title="TechTree API", lifespan=lifespan)
"""
FastAPI application instance for the TechTree API.
"""

# Removed direct DB instantiation and print statement

# Removed deprecated @app.on_event("shutdown") function


# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins since we're using a proxy
    allow_credentials=False,  # Disable credentials for simplicity
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include routers for each component
from backend.routers import auth_router
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
from backend.routers import onboarding_router
app.include_router(onboarding_router.router, prefix="/onboarding", tags=["Onboarding"])
from backend.routers import syllabus_router
app.include_router(syllabus_router.router, prefix="/syllabus", tags=["Syllabus"])
from backend.routers import lesson_router
app.include_router(lesson_router.router, prefix="/lesson", tags=["Lesson"])
from backend.routers import progress_router
app.include_router(progress_router.router, prefix="/progress", tags=["User Progress"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
