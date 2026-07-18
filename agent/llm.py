from langchain_google_genai import ChatGoogleGenerativeAI

from config import load_settings


def build_llm():
    settings = load_settings()
    if settings.llm_provider != "google_genai":
        raise ValueError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is not set")
    return ChatGoogleGenerativeAI(model=settings.llm_model, google_api_key=settings.llm_api_key, temperature=0.3)
