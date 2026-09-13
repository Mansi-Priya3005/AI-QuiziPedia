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

    # Rate limiting for auth endpoints, to slow down credential-stuffing /
    # brute-force attempts and signup spam.
    auth_rate_limit: str = "5/minute"

    # JWT signing. No default for the secret -- an app with a guessable or
    # shared-across-deployments default secret can have its tokens forged.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
