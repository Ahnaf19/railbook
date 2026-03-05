from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.database import async_session, engine
from app.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate DB connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")

    # Seed data
    async with async_session() as session:
        await seed_database(session)
    logger.info("Seed data loaded")

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


app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
