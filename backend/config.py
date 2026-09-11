from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    gemini_api_key: str
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    environment: str = "development"

    # Rate limiting for the expensive /generate-quiz endpoint (calls the
    # LLM). Previously this endpoint was fully unauthenticated and
    # unthrottled — anyone could trigger unlimited Gemini calls.
    generate_quiz_rate_limit: str = "10/minute"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
