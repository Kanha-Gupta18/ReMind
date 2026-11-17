from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file.

    Pydantic reads these automatically:
      - settings.database_url  <- DATABASE_URL   env var
      - settings.jwt_secret    <- JWT_SECRET     env var
      - etc.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True,
    )

    app_name: str = "ReMind"
    version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://remind:remind_dev@localhost:5432/remind"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 10080  # 7 days
    session_idle_minutes: int = 30

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
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_storage_bucket: str = "remind-sources"
    max_upload_bytes: int = Field(default=6 * 1024 * 1024, gt=0, le=6 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_deployment(self):
        if self.storage_backend == "supabase":
            origin = urlsplit(self.supabase_url)
            if (origin.scheme != "https" or not origin.hostname or origin.username
                    or origin.password or origin.path not in ("", "/")
                    or origin.query or origin.fragment):
                raise ValueError("SUPABASE_URL must be an HTTPS origin")
            if not self.supabase_service_role_key.get_secret_value():
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required for Supabase storage")
            if not self.supabase_storage_bucket or any(
                char not in "abcdefghijklmnopqrstuvwxyz0123456789-_"
                for char in self.supabase_storage_bucket
            ):
                raise ValueError("Use a lowercase bucket name with letters, numbers, hyphens or underscores")
        if self.environment == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith(("dev-", "ci-")):
                raise ValueError("Production requires a random JWT_SECRET of at least 32 characters")
            if self.jwt_algorithm != "HS256":
                raise ValueError("This deployment supports JWT_ALGORITHM=HS256")
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true")
            if self.storage_backend != "supabase":
                raise ValueError("Production requires persistent Supabase storage")
            if not self.cors_origins or any(
                urlsplit(origin).scheme != "https" or not urlsplit(origin).hostname
                or urlsplit(origin).path or urlsplit(origin).query or urlsplit(origin).fragment
                or urlsplit(origin).username or "*" in origin
                for origin in self.cors_origins
            ):
                raise ValueError("Production CORS_ORIGINS must contain explicit HTTPS origins without paths")
            database = urlsplit(self.database_url)
            if database.scheme != "postgresql+psycopg" or not database.hostname:
                raise ValueError("Production requires a postgresql+psycopg DATABASE_URL")
            from urllib.parse import parse_qs
            if parse_qs(database.query).get("sslmode") not in (["require"], ["verify-full"]):
                raise ValueError("Production DATABASE_URL requires sslmode=require or verify-full")
        return self


settings = Settings()
