"""
ATLAS Backend — FastAPI Entry Point
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.upload import router as upload_router
from api.chat import router as chat_router

load_dotenv()

app = FastAPI(
    title="ATLAS — Advanced Transport & Logistics Analytics System",
    description="EDA + BI platform backend powered by LangGraph + Groq",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

allowed_origins = [
    "http://localhost:3000",
    frontend_url,
    "https://atlas-wine-iota.vercel.app",  # your Vercel deployment
]

# In development, allow all origins
if os.getenv("ENVIRONMENT") != "production":
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(chat_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "ATLAS Backend"}


@app.get("/")
def root():
    return {"message": "ATLAS API is running. Visit /docs for API documentation."}
