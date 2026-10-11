"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://resolveflow:localdev@localhost:5432/resolveflow"
    test_database_url: str | None = None

    # Auth
    jwt_secret: str = "dev-only-insecure-secret-do-not-use-in-prod"  # noqa: S105 - dev default, refused at startup outside dev
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    environment: str = "dev"  # dev | test | prod

    # CORS
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,"
        "https://frontend-three-bice-94.vercel.app,https://frontend-oos8pnhe9-rishidas887s-projects.vercel.app"
    )

    # LLM
    llm_provider: str = "auto"  # auto | deterministic | openai
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 1

    # Embeddings
    embedding_provider: str = "auto"  # auto | deterministic | openai
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 256

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.05
    retrieval_max_chunks: int = 8

    # Uploads
    max_upload_bytes: int = 1_048_576  # 1 MiB

    # Worker
    worker_poll_seconds: float = 2.0
    run_max_attempts: int = 3
    run_retry_backoff_seconds: float = 5.0
    run_stale_seconds: float = 600.0  # a "running" run older than this is recovered

    @field_validator("cors_origins")
    @classmethod
    def _cors_not_blank(cls, v: str) -> str:
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            return "openai" if self.openai_api_key else "deterministic"
        return self.llm_provider

    @property
    def effective_embedding_provider(self) -> str:
        if self.embedding_provider == "auto":
            return "openai" if self.openai_api_key else "deterministic"
        return self.embedding_provider

    def validate_runtime(self) -> None:
        """Fail fast on unsafe/missing config in non-dev environments."""
        if self.environment not in ("dev", "test"):
            if self.jwt_secret.startswith("dev-only"):
                raise RuntimeError(
                    "JWT_SECRET must be set to a strong secret when ENVIRONMENT is not dev/test"
                )
            if not self.database_url.startswith("postgresql"):
                raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")
        if self.effective_llm_provider == "openai" and not self.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
