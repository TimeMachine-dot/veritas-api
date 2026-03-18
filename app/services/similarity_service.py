from sqlalchemy.orm import Session
from ..config import settings
from ..providers.similarity_provider import run_similarity_check
from .reference_similarity_service import compare_against_reference_corpus


def _risk_from_similarity(score: float) -> str:
    if score >= 45:
        return "Alto"
    if score >= 15:
        return "Medio"
    if score >= 0:
        return "Bajo"
    return "Indeterminado"


async def check_similarity(text: str, language: str = "es", db: Session | None = None) -> dict:
    internal_result = run_similarity_check(text=text, language=language)

    if db is None:
        return internal_result

    external_result = compare_against_reference_corpus(db, text=text, language=language)

    combined_score = max(
        internal_result.get("overall_similarity", 0.0),
        external_result.get("overall_similarity", 0.0),
    )

    combined_matches = (
        external_result.get("matches", []) + internal_result.get("matches", [])
    )
    combined_matches = sorted(combined_matches, key=lambda x: x["match_percent"], reverse=True)[:10]

    likely_issue = internal_result.get("likely_issue", "sin_hallazgos_relevantes")
    if external_result.get("matches"):
        likely_issue = external_result.get("likely_issue", likely_issue)

    notes = (
        f"{internal_result.get('notes', '')} "
        f"{external_result.get('note', '')}".strip()
    )

    disclaimer = (
        "Este resultado no prueba plagio. "
        "Combina similitud interna y comparacion contra el corpus de referencia cargado, "
        "pero debe complementarse con revision humana."
    )

    return {
        "overall_similarity": round(combined_score, 2),
        "risk_level": _risk_from_similarity(round(combined_score, 2)),
        "likely_issue": likely_issue,
        "matches": combined_matches,
        "notes": notes,
        "disclaimer": disclaimer,
    }