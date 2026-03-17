from ..config import settings
from ..providers.similarity_provider import run_similarity_check


async def check_similarity(text: str, language: str = "es") -> dict:
    if settings.similarity_provider == "dummy":
        return run_similarity_check(text=text, language=language)

    raise NotImplementedError("Similarity provider real no configurado todavía.")