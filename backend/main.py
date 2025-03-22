import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import auth_router, onboarding_router, syllabus_router, lesson_router, progress_router

app = FastAPI(title="TechTree API")

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
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(onboarding_router.router, prefix="/onboarding", tags=["Onboarding"])
app.include_router(syllabus_router.router, prefix="/syllabus", tags=["Syllabus"])
app.include_router(lesson_router.router, prefix="/lesson", tags=["Lesson"])
app.include_router(progress_router.router, prefix="/progress", tags=["User Progress"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)