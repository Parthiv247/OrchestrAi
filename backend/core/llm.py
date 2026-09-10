from langchain_groq import ChatGroq

from .config import get_settings


def get_groq_llm(temperature: float = 0.0, streaming: bool = False) -> ChatGroq:
    """Returns Groq llama-3.1-70b-versatile — fast inference, strong at SQL and reasoning."""
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model,
        groq_api_key=settings.groq_api_key,
        temperature=temperature,
        streaming=streaming,
    )
