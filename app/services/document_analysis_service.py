from sqlalchemy.orm import Session
from ..services.similarity_service import check_similarity
from ..services.ai_risk_service import check_ai_risk


def _risk_value(level: str) -> int:
    mapping = {
        "Indeterminado": 0,
        "Bajo": 1,
        "Medio": 2,
        "Alto": 3,
    }
    return mapping.get(level, 0)


def _combine_overall_risk(similarity_result: dict, ai_result: dict) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    ai_score = ai_result.get("ai_risk_score", 0)
    sim_level = similarity_result.get("risk_level", "Indeterminado")
    ai_level = ai_result.get("risk_level", "Indeterminado")

    if sim_score >= 45 or ai_score >= 0.70:
        return "Alto"

    if sim_score >= 15 or ai_score >= 0.30:
        return "Medio"

    max_level = max(_risk_value(sim_level), _risk_value(ai_level))
    if max_level >= 3:
        return "Alto"
    if max_level >= 2:
        return "Medio"
    if max_level >= 1:
        return "Bajo"

    return "Indeterminado"


def _scope_label(scope: str) -> str:
    mapping = {
        "none": "sin coincidencias relevantes",
        "internal_only": "solo similitud interna",
        "corpus_only": "solo similitud contra corpus",
        "internal_and_corpus": "similitud interna y contra corpus",
    }
    return mapping.get(scope, "sin clasificacion")


def _build_summary(title: str | None, similarity_result: dict, ai_result: dict, overall_risk: str) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    sim_level = similarity_result.get("risk_level", "Indeterminado")
    ai_score = ai_result.get("ai_risk_score", 0)
    ai_level = ai_result.get("risk_level", "Indeterminado")
    internal_score = similarity_result.get("internal_similarity_score", 0)
    corpus_score = similarity_result.get("corpus_similarity_score", 0)
    scope = similarity_result.get("similarity_scope", "none")

    title_part = f"Documento: {title}. " if title else ""
    return (
        f"{title_part}Similitud total detectada: {sim_score:.2f}% ({sim_level}). "
        f"Interna: {internal_score:.2f}%. Contra corpus: {corpus_score:.2f}%. "
        f"Alcance de similitud: {_scope_label(scope)}. "
        f"Riesgo IA estimado: {ai_score:.2f} ({ai_level}). "
        f"Riesgo global del analisis: {overall_risk}."
    )


def _build_conclusion(similarity_result: dict, ai_result: dict, overall_risk: str) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    ai_score = ai_result.get("ai_risk_score", 0)
    scope = similarity_result.get("similarity_scope", "none")
    corpus_score = similarity_result.get("corpus_similarity_score", 0)

    if overall_risk == "Alto":
        if scope in {"corpus_only", "internal_and_corpus"} and corpus_score > 0:
            return (
                "El documento presenta indicios relevantes que justifican revision manual prioritaria. "
                "Se detectaron coincidencias significativas contra el corpus de referencia y/o senales compatibles con parafraseo cercano."
            )
        return (
            "El documento presenta indicios relevantes que justifican revision manual prioritaria. "
            "Se detectaron coincidencias significativas y/o senales compatibles con redaccion generica o edicion intensiva asistida por IA."
        )

    if overall_risk == "Medio":
        if scope == "corpus_only":
            return (
                "El documento presenta coincidencias moderadas contra el corpus de referencia. "
                "No constituyen prueba definitiva de plagio, pero si justifican verificacion complementaria."
            )
        if scope == "internal_only":
            return (
                "El documento presenta repeticion o redundancia interna moderada. "
                "Esto no prueba plagio externo, pero si amerita revision de estilo o posible reutilizacion excesiva."
            )
        return (
            "El documento presenta senales moderadas que ameritan revision academica adicional. "
            "No constituyen prueba definitiva de plagio ni de autoria por IA, pero si justifican verificacion complementaria."
        )

    if sim_score == 0 and ai_score == 0:
        return (
            "No se detectaron senales relevantes con el motor actual. "
            "Aun asi, el analisis sigue siendo preliminar y debe complementarse con revision humana."
        )

    return (
        "El documento no muestra senales fuertes con el motor actual, aunque conviene interpretar "
        "el resultado con cautela y dentro de su contexto academico."
    )


def _build_recommendations(similarity_result: dict, ai_result: dict, overall_risk: str) -> list[str]:
    recommendations: list[str] = []

    sim_matches = similarity_result.get("matches", [])
    ai_segments = ai_result.get("segments", [])
    likely_issue = similarity_result.get("likely_issue", "")
    scope = similarity_result.get("similarity_scope", "none")

    if scope == "internal_only":
        recommendations.append("Revisar manualmente los fragmentos marcados por repeticion interna.")
    elif scope == "corpus_only":
        recommendations.append("Revisar manualmente los fragmentos marcados por coincidencia contra el corpus.")
    elif scope == "internal_and_corpus":
        recommendations.append("Distinguir entre coincidencias internas y coincidencias contra el corpus en la revision manual.")
        recommendations.append("Revisar manualmente los fragmentos marcados por repeticion interna y por corpus.")

    if likely_issue in {"dependencia_fuerte_de_fuentes", "revision_manual_urgente", "parafraseo_cercano_potencial"}:
        recommendations.append("Verificar si existen secciones copiadas, autocopiadas o excesivamente cercanas a documentos del corpus.")
    if ai_segments:
        recommendations.append("Comparar el estilo del texto con otros escritos del mismo autor.")
        recommendations.append("Solicitar borradores previos o una sustentacion oral breve.")
    if overall_risk in {"Medio", "Alto"}:
        recommendations.append("Revisar la calidad de las citas, referencias y el nivel de especificidad del contenido.")
    if not sim_matches and not ai_segments:
        recommendations.append("Mantener revision humana basica y contraste con el contexto academico del documento.")

    unique = []
    seen = set()
    for item in recommendations:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique[:6]


async def analyze_document(
    text: str,
    language: str = "es",
    title: str | None = None,
    db: Session | None = None,
) -> dict:
    similarity_result = await check_similarity(text=text, language=language, db=db)
    ai_result = await check_ai_risk(text=text, language=language)

    overall_risk = _combine_overall_risk(similarity_result, ai_result)
    summary = _build_summary(title, similarity_result, ai_result, overall_risk)
    conclusion = _build_conclusion(similarity_result, ai_result, overall_risk)
    recommendations = _build_recommendations(similarity_result, ai_result, overall_risk)

    return {
        "title": title,
        "similarity": similarity_result,
        "ai_risk": ai_result,
        "overall_risk": overall_risk,
        "summary": summary,
        "conclusion": conclusion,
        "recommendations": recommendations,
        "disclaimer": (
            "Este analisis es orientativo y no constituye una prueba definitiva de plagio "
            "ni de autoria por IA. Debe complementarse con revision humana y verificacion adicional."
        ),
    }