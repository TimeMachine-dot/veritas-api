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

    # Regla principal
    if sim_score >= 55 or ai_score >= 0.70:
        return "Alto"

    if sim_score >= 20 or ai_score >= 0.30:
        return "Medio"

    # Respaldo por niveles categóricos
    max_level = max(_risk_value(sim_level), _risk_value(ai_level))
    if max_level >= 3:
        return "Alto"
    if max_level >= 2:
        return "Medio"
    if max_level >= 1:
        return "Bajo"

    return "Indeterminado"


def _build_summary(title: str | None, similarity_result: dict, ai_result: dict, overall_risk: str) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    sim_level = similarity_result.get("risk_level", "Indeterminado")
    ai_score = ai_result.get("ai_risk_score", 0)
    ai_level = ai_result.get("risk_level", "Indeterminado")

    title_part = f"Documento: {title}. " if title else ""
    return (
        f"{title_part}Similitud interna detectada: {sim_score:.2f}% ({sim_level}). "
        f"Riesgo IA estimado: {ai_score:.2f} ({ai_level}). "
        f"Riesgo global del análisis: {overall_risk}."
    )


def _build_conclusion(similarity_result: dict, ai_result: dict, overall_risk: str) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    ai_score = ai_result.get("ai_risk_score", 0)

    if overall_risk == "Alto":
        return (
            "El documento presenta indicios relevantes que justifican revisión manual prioritaria. "
            "Se detectaron patrones de repetición interna y/o señales compatibles con redacción genérica "
            "o edición intensiva asistida por IA."
        )

    if overall_risk == "Medio":
        return (
            "El documento presenta señales moderadas que ameritan revisión académica adicional. "
            "No constituyen prueba definitiva de plagio ni de autoría por IA, pero sí justifican "
            "verificación complementaria."
        )

    if sim_score == 0 and ai_score == 0:
        return (
            "No se detectaron señales relevantes con el motor actual. "
            "Aun así, el análisis sigue siendo preliminar y debe complementarse con revisión humana."
        )

    return (
        "El documento no muestra señales fuertes con el motor actual, aunque conviene interpretar "
        "el resultado con cautela y dentro de su contexto académico."
    )


def _build_recommendations(similarity_result: dict, ai_result: dict, overall_risk: str) -> list[str]:
    recommendations: list[str] = []

    sim_matches = similarity_result.get("matches", [])
    ai_segments = ai_result.get("segments", [])
    likely_issue = similarity_result.get("likely_issue", "")

    if sim_matches:
        recommendations.append("Revisar manualmente los fragmentos marcados por coincidencia interna.")
    if likely_issue in {"dependencia_fuerte_de_fuentes", "revision_manual_urgente"}:
        recommendations.append("Verificar si existen secciones copiadas, autocopiadas o excesivamente reutilizadas.")
    if ai_segments:
        recommendations.append("Comparar el estilo del texto con otros escritos del mismo autor.")
        recommendations.append("Solicitar borradores previos o una sustentación oral breve.")
    if overall_risk in {"Medio", "Alto"}:
        recommendations.append("Revisar la calidad de las citas, referencias y el nivel de especificidad del contenido.")
    if not recommendations:
        recommendations.append("Mantener revisión humana básica y contraste con el contexto académico del documento.")

    # Quitar duplicados conservando orden
    unique = []
    seen = set()
    for item in recommendations:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique[:5]


async def analyze_document(text: str, language: str = "es", title: str | None = None) -> dict:
    similarity_result = await check_similarity(text=text, language=language)
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
            "Este análisis es orientativo y no constituye una prueba definitiva de plagio "
            "ni de autoría por IA. Debe complementarse con revisión humana y verificación adicional."
        ),
    }