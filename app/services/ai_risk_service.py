from ..config import settings
from ..providers.ai_risk_provider import run_ai_risk_check


async def check_ai_risk(text: str, language: str = "es") -> dict:
    if settings.ai_risk_provider == "dummy":
        return run_ai_risk_check(text=text, language=language)

    raise NotImplementedError("AI risk provider real no configurado todavía.")