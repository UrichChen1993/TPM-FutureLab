import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_backend: str
    aws_region: str
    dynamodb_table: str
    llm_provider: str
    llm_model: str
    llm_api_key: str | None


def load_settings() -> Settings:
    return Settings(
        data_backend=os.getenv("DATA_BACKEND", "memory"),
        aws_region=os.getenv("AWS_REGION", "ap-northeast-1"),
        dynamodb_table=os.getenv("DYNAMODB_TABLE", "homewellness-mvp"),
        llm_provider=os.getenv("LLM_PROVIDER", "google_genai"),
        llm_model=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
    )
