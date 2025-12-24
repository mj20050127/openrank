from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"
    OPENDIGGER_BASE_URL: str = "https://oss.open-digger.cn"
    OPENDIGGER_PLATFORM: str = "github"

    DATAEASE_BASE_URL: str | None = None
    DATAEASE_USERNAME: str | None = None
    DATAEASE_PASSWORD: str | None = None
    DATAEASE_EMBED_APP_ID: str | None = None
    DATAEASE_EMBED_APP_SECRET: str | None = None
    DATAEASE_EMBED_ORIGIN: str | None = None

    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    MAXKB_BASE_URL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
