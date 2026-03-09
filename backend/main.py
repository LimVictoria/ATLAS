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
# Allow all origins for now — tighten after confirmed working
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ATLAS Backend"}


@app.get("/")
def root():
    return {"message": "ATLAS API is running. Visit /docs for API documentation."}
