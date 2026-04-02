from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google OAuth
    google_client_id: str = ""

    # JWT
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # Database
    database_url: str = "sqlite+aiosqlite:///./hush.db"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
