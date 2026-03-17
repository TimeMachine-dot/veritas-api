from __future__ import annotations


def _risk_from_score(score: float) -> str:
    if score >= 0.75:
        return "Alto"
    if score >= 0.45:
        return "Medio"
    if score >= 0:
        return "Bajo"
    return "Indeterminado"


def run_ai_risk_check(text: str, language: str = "es") -> dict:
    lowered = text.lower()

    connectors = [
        "en conclusión",
        "por otro lado",
        "asimismo",
        "en ese sentido",
        "cabe destacar",
        "por consiguiente",
        "de esta manera",
        "en definitiva",
    ]
    connector_hits = sum(lowered.count(c) for c in connectors)

    generic_phrases = [
        "es importante destacar",
        "resulta fundamental",
        "a lo largo del tiempo",
        "en la actualidad",
        "diversos autores coinciden",
    ]
    generic_hits = sum(lowered.count(g) for g in generic_phrases)

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    similar_lengths = 0
    if len(paragraphs) >= 3:
        lens = [len(p) for p in paragraphs[:10]]
        avg = sum(lens) / len(lens)
        similar_lengths = sum(1 for l in lens if abs(l - avg) < 35)

    score = min(
        0.12 * connector_hits +
        0.10 * generic_hits +
        0.05 * similar_lengths,
        0.95
    )
    score = round(float(score), 2)

    segments = []
    if connector_hits >= 3:
        segments.append(
            {
                "text_span": "Uso intensivo de conectores académicos repetitivos en varias secciones.",
                "reason": "Uniformidad discursiva y transición excesivamente estandarizada.",
                "signal_strength": "moderada",
            }
        )
    if generic_hits >= 2:
        segments.append(
            {
                "text_span": "Presencia repetida de fórmulas académicas genéricas.",
                "reason": "Generalidad elevada con baja especificidad analítica.",
                "signal_strength": "moderada",
            }
        )
    if similar_lengths >= 5:
        segments.append(
            {
                "text_span": "Varios párrafos con longitudes muy parecidas.",
                "reason": "Patrón estructural demasiado uniforme.",
                "signal_strength": "débil",
            }
        )

    return {
        "ai_risk_score": score,
        "risk_level": _risk_from_score(score),
        "segments": segments,
        "notes": (
            "Resultado provisional basado en señales de estilo. "
            "Debe complementarse con revisión humana, historial de borradores y contexto académico."
        ),
        "disclaimer": (
            "Este resultado no demuestra autoría por IA. Solo estima señales compatibles "
            "con generación o edición intensiva mediante IA."
        ),
    }