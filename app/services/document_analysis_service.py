import re
from sqlalchemy.orm import Session
from ..services.similarity_service import check_similarity
from ..services.ai_risk_service import check_ai_risk
from ..services.external_search_service import external_search


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


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_keywords(text: str) -> list[str]:
    text = _normalize_spaces(text.lower())
    text = re.sub(r"[^\wáéíóúñü\s-]", " ", text)
    tokens = re.findall(r"[a-záéíóúñü0-9-]+", text)

    stopwords = {
        "de", "la", "el", "los", "las", "y", "o", "u", "un", "una", "unos", "unas",
        "del", "al", "por", "para", "con", "sin", "sobre", "entre", "hacia", "desde",
        "en", "se", "que", "como", "su", "sus", "es", "son", "fue", "han", "ha",
        "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "without",
        "from", "by", "at", "as", "is", "are", "was", "were", "be", "been", "this", "that",
    }

    preferred = {
        "copper", "cobre", "fiscal", "revenue", "ingresos", "cointegration",
        "cointegracion", "cointegración", "mining", "mineria", "minería",
        "commodity", "commodities", "tributario", "tributaria", "tax", "royalty",
        "education", "educacion", "educación", "employment", "empleo",
        "development", "desarrollo", "inequality", "desigualdad"
    }

    seen = set()
    out = []

    for tok in tokens:
        if len(tok) < 4:
            continue
        if tok in stopwords:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)

    preferred_hits = [x for x in out if x in preferred]
    others = [x for x in out if x not in preferred]
    return (preferred_hits + others)[:10]


def _build_external_query(title: str | None, text: str) -> str:
    title_part = _normalize_spaces(title or "")
    keywords = _extract_keywords(text)
    if title_part:
        return _normalize_spaces(f"{title_part} {' '.join(keywords[:8])}")
    return _normalize_spaces(" ".join(keywords[:8]))


def _should_trigger_external_search(text: str, similarity_result: dict, ai_result: dict) -> bool:
    sim_score = similarity_result.get("overall_similarity", 0)
    ai_score = ai_result.get("ai_risk_score", 0)
    likely_issue = similarity_result.get("likely_issue", "")
    scope = similarity_result.get("similarity_scope", "none")

    lower_text = text.lower()
    vague_citation_markers = [
        "diversos autores",
        "segun estudios",
        "según estudios",
        "segun investigaciones",
        "según investigaciones",
        "varios estudios coinciden",
        "according to studies",
        "several studies",
        "many authors",
    ]
    has_vague_markers = any(marker in lower_text for marker in vague_citation_markers)

    if sim_score >= 15:
        return True
    if ai_score >= 0.30:
        return True
    if likely_issue in {
        "mala_citacion_potencial",
        "parafraseo_cercano_potencial",
        "dependencia_fuerte_de_fuentes",
        "revision_manual_urgente",
    }:
        return True
    if scope in {"corpus_only", "internal_and_corpus"}:
        return True
    if has_vague_markers:
        return True

    return False


def _build_summary(
    title: str | None,
    similarity_result: dict,
    ai_result: dict,
    overall_risk: str,
    external_triggered: bool,
    external_candidates: list[dict],
) -> str:
    sim_score = similarity_result.get("overall_similarity", 0)
    sim_level = similarity_result.get("risk_level", "Indeterminado")
    ai_score = ai_result.get("ai_risk_score", 0)
    ai_level = ai_result.get("risk_level", "Indeterminado")
    internal_score = similarity_result.get("internal_similarity_score", 0)
    corpus_score = similarity_result.get("corpus_similarity_score", 0)
    scope = similarity_result.get("similarity_scope", "none")

    title_part = f"Documento: {title}. " if title else ""
    external_part = ""
    if external_triggered:
        external_part = f" Busqueda externa activada: {len(external_candidates)} fuentes candidatas."

    return (
        f"{title_part}Similitud total detectada: {sim_score:.2f}% ({sim_level}). "
        f"Interna: {internal_score:.2f}%. Contra corpus: {corpus_score:.2f}%. "
        f"Alcance de similitud: {_scope_label(scope)}. "
        f"Riesgo IA estimado: {ai_score:.2f} ({ai_level}). "
        f"Riesgo global del analisis: {overall_risk}.{external_part}"
    )


def _build_conclusion(
    similarity_result: dict,
    ai_result: dict,
    overall_risk: str,
    external_triggered: bool,
    external_candidates: list[dict],
) -> str:
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
        if external_triggered and external_candidates:
            return (
                "El documento presenta senales moderadas y ademas se encontraron fuentes externas potencialmente relacionadas. "
                "Esto no prueba plagio, pero si justifica una revision academica adicional."
            )
        return (
            "El documento presenta senales moderadas que ameritan revision academica adicional. "
            "No constituyen prueba definitiva de plagio ni de autoria por IA, pero si justifican verificacion complementaria."
        )

    if sim_score == 0 and ai_score == 0 and not external_candidates:
        return (
            "No se detectaron senales relevantes con el motor actual. "
            "Aun asi, el analisis sigue siendo preliminar y debe complementarse con revision humana."
        )

    return (
        "El documento no muestra senales fuertes con el motor actual, aunque conviene interpretar "
        "el resultado con cautela y dentro de su contexto academico."
    )


def _build_recommendations(
    similarity_result: dict,
    ai_result: dict,
    overall_risk: str,
    external_triggered: bool,
    external_candidates: list[dict],
) -> list[str]:
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

    if external_triggered and external_candidates:
        recommendations.append("Revisar las fuentes externas candidatas para confirmar si el contenido proviene de literatura academica conocida.")
        recommendations.append("Si una fuente externa coincide claramente, incorporar cita o referencia explicita si corresponde.")

    if overall_risk in {"Medio", "Alto"}:
        recommendations.append("Revisar la calidad de las citas, referencias y el nivel de especificidad del contenido.")

    if not sim_matches and not ai_segments and not external_candidates:
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

    external_triggered = _should_trigger_external_search(text, similarity_result, ai_result)
    external_query = None
    external_candidates = []

    if external_triggered:
        external_query = _build_external_query(title, text)
        try:
            external_result = await external_search(query=external_query, limit=5)
            external_candidates = external_result.get("results", [])[:5]
        except Exception:
            external_candidates = []

    overall_risk = _combine_overall_risk(similarity_result, ai_result)
    summary = _build_summary(
        title,
        similarity_result,
        ai_result,
        overall_risk,
        external_triggered,
        external_candidates,
    )
    conclusion = _build_conclusion(
        similarity_result,
        ai_result,
        overall_risk,
        external_triggered,
        external_candidates,
    )
    recommendations = _build_recommendations(
        similarity_result,
        ai_result,
        overall_risk,
        external_triggered,
        external_candidates,
    )

    return {
        "title": title,
        "similarity": similarity_result,
        "ai_risk": ai_result,
        "overall_risk": overall_risk,
        "external_search_triggered": external_triggered,
        "external_query": external_query,
        "external_candidates": external_candidates,
        "summary": summary,
        "conclusion": conclusion,
        "recommendations": recommendations,
        "disclaimer": (
            "Este analisis es orientativo y no constituye una prueba definitiva de plagio "
            "ni de autoria por IA. Debe complementarse con revision humana y verificacion adicional."
        ),
    }