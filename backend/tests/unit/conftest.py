import os

# The app's dependencies read settings on first use; give unit tests harmless
# values (never used to connect: tests override every DB/LLM dependency).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:1/test")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-at-least-32-bytes-long")
