from sqlalchemy.orm import Session
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


def _build_similarity_scope(internal_score: float, corpus_score: float) -> str:
    has_internal = internal_score > 0
    has_corpus = corpus_score > 0

    if has_internal and has_corpus:
        return "internal_and_corpus"
    if has_internal:
        return "internal_only"
    if has_corpus:
        return "corpus_only"
    return "none"


def _build_similarity_notes(internal_result: dict, external_result: dict, scope: str) -> str:
    internal_note = internal_result.get("notes", "")
    external_note = external_result.get("note", "")

    if scope == "internal_and_corpus":
        scope_note = (
            "Se detectaron coincidencias tanto dentro del propio texto como contra el corpus de referencia."
        )
    elif scope == "internal_only":
        scope_note = (
            "Solo se detectaron coincidencias internas dentro del texto analizado."
        )
    elif scope == "corpus_only":
        scope_note = (
            "No se detectaron coincidencias internas relevantes, pero si coincidencias contra el corpus de referencia."
        )
    else:
        scope_note = (
            "No se detectaron coincidencias relevantes ni dentro del texto ni contra el corpus de referencia."
        )

    return f"{scope_note} {internal_note} {external_note}".strip()


async def check_similarity(text: str, language: str = "es", db: Session | None = None) -> dict:
    internal_result = run_similarity_check(text=text, language=language)

    external_result = {
        "docs_count": 0,
        "overall_similarity": 0.0,
        "matches": [],
        "likely_issue": "sin_hallazgos_relevantes",
        "note": "No se comparo contra corpus externo.",
    }

    if db is not None:
        external_result = compare_against_reference_corpus(db, text=text, language=language)

    internal_score = round(internal_result.get("overall_similarity", 0.0), 2)
    corpus_score = round(external_result.get("overall_similarity", 0.0), 2)
    combined_score = max(internal_score, corpus_score)

    combined_matches = (
        external_result.get("matches", []) + internal_result.get("matches", [])
    )
    combined_matches = sorted(combined_matches, key=lambda x: x["match_percent"], reverse=True)[:10]

    likely_issue = internal_result.get("likely_issue", "sin_hallazgos_relevantes")
    if external_result.get("matches"):
        likely_issue = external_result.get("likely_issue", likely_issue)

    scope = _build_similarity_scope(internal_score, corpus_score)
    notes = _build_similarity_notes(internal_result, external_result, scope)

    disclaimer = (
        "Este resultado no prueba plagio. "
        "Distingue entre similitud interna y comparacion contra el corpus de referencia, "
        "pero debe complementarse con revision humana."
    )

    return {
        "overall_similarity": combined_score,
        "internal_similarity_score": internal_score,
        "corpus_similarity_score": corpus_score,
        "corpus_documents_checked": external_result.get("docs_count", 0),
        "similarity_scope": scope,
        "risk_level": _risk_from_similarity(combined_score),
        "likely_issue": likely_issue,
        "matches": combined_matches,
        "notes": notes,
        "disclaimer": disclaimer,
    }