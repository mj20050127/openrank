from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://openrank:openrank@127.0.0.1:5432/openrank"
    OPENDIGGER_BASE_URL: str = "https://oss.open-digger.cn"
    OPENDIGGER_PLATFORM: str = "github"
    BOOTSTRAP_SEED_ENABLED: bool = True
    BOOTSTRAP_SEED_PATH: str | None = None

    GITHUB_TOKEN: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
