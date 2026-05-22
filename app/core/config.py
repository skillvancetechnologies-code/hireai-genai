"""Centralized config. All env vars loaded here, nowhere else."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str = "sk-missing"
    gemini_api_key: str = ""

    # Model selection
    parser_model: str = "gpt-4o-mini"
    copilot_model: str = "gpt-4o-mini"
    explain_model: str = "gpt-4o"

    # Infra
    redis_url: str = "redis://localhost:6379/0"
    web_backend_url: str = "http://localhost:8000/api"

    # Service
    service_host: str = "0.0.0.0"
    service_port: int = 8001
    log_level: str = "INFO"

    # Cost
    daily_spend_cap_usd: float = 10.0
    project_spend_cap_usd: float = 200.0
    cost_log_path: str = "data/cost_log.jsonl"

    # Cache
    default_cache_ttl_seconds: int = 3600

    # Slack
    slack_webhook_url: str = ""

    # Module ownership (used by regression alerts to tag the owner)
    module_owners: dict[str, str] = {
        "parser": "G1",
        "copilot": "G2",
        "explain": "G3",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
