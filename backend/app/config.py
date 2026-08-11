import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://admin:YOUR_DB_PASSWORD@db:5432/stockbs")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
    SUBTITLE_DIR: str = os.getenv("SUBTITLE_DIR", "/app/storage/subtitles")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "YOUR_JWT_SECRET_KEY")
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours

settings = Settings()
