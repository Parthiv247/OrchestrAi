from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM — Groq
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", env="GROQ_MODEL")

    # LangSmith
    langsmith_api_key: str = Field(default="", env="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="orchestrai", env="LANGSMITH_PROJECT")
    langchain_tracing_v2: str = Field(default="true", env="LANGCHAIN_TRACING_V2")

    # Database — set DATABASE_URL for production (Railway/Supabase), or individual vars for local Docker
    database_url_override: str = Field(default="", env="DATABASE_URL")
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="orchestrai", env="POSTGRES_DB")
    postgres_user: str = Field(default="admin", env="POSTGRES_USER")
    postgres_password: str = Field(default="orchestrai_secret", env="POSTGRES_PASSWORD")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            # Supabase pooler requires SSL. asyncpg doesn't read sslmode from the
            # query string so we strip it and rely on connect_args ssl="require"
            # (set in db/session.py) — but also strip any conflicting sslmode param
            # so the URL stays clean for asyncpg's URL parser.
            if "?" in url:
                # remove sslmode param if present; asyncpg handles SSL via connect_args
                parts = url.split("?", 1)
                params = "&".join(p for p in parts[1].split("&") if not p.startswith("sslmode"))
                url = parts[0] + (f"?{params}" if params else "")
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Auth
    jwt_secret_key: str = Field(default="change_me_in_production", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Airflow
    airflow_executor: str = Field(default="LocalExecutor", env="AIRFLOW__CORE__EXECUTOR")

    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")

    # ChromaDB
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8001, env="CHROMA_PORT")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
