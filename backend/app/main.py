from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from app.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate DB connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")
    yield
    # Shutdown: dispose engine
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(title="RailBook", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
