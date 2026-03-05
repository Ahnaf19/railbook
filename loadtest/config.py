import os

BASE_URL = os.getenv("TARGET_URL", "http://localhost:8000")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://railbook:railbook@localhost:5432/railbook",
)

# Thresholds for pass/fail
MAX_P95_MS = 2000
MAX_ERROR_RATE = 0.05
