from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file.

    Pydantic reads these automatically:
      - settings.database_url  <- DATABASE_URL   env var
      - settings.jwt_secret    <- JWT_SECRET     env var
      - etc.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "ReMind"
    version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://remind:remind_dev@localhost:5432/remind"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 10080  # 7 days

    # httpOnly cookie support (optional; the primary path is Authorization: Bearer)
    cookie_name: str = "remind_token"
    cookie_secure: bool = False

    # The four frontend apps (patient/family/caregiver/clinician)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
    ]

    storage_dir: str = "storage"


settings = Settings()
