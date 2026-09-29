"""ContentMind backend entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import create_all
from backend.routers.api import router as api_router
from backend.routers.content import router as content_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_all()
    yield


app = FastAPI(
    title="ContentMind API",
    description="Memory-powered AI content strategy & planning (Hindsight by Vectorize)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "app": "ContentMind"}


app.include_router(content_router)
app.include_router(api_router)
