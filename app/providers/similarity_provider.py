from __future__ import annotations
from collections import Counter
from typing import Any


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in text.replace("\n", " ").split(".")]
    return [p for p in parts if len(p) > 40]


def _risk_from_similarity(score: float) -> str:
    if score >= 40:
        return "Alto"
    if score >= 20:
        return "Medio"
    if score >= 0:
        return "Bajo"
    return "Indeterminado"


def run_similarity_check(text: str, language: str = "es") -> dict[str, Any]:
    sentences = _split_sentences(text)
    lowered = [s.lower() for s in sentences]

    counts = Counter(lowered)
    repeated = [s for s, c in counts.items() if c > 1 and len(s) > 80]

    matches = []
    for s in repeated[:8]:
        matches.append(
            {
                "text_span": s[:300],
                "source_title": "Coincidencia interna del mismo documento",
                "source_url": None,
                "match_percent": 75.0,
                "source_type": "internal",
                "note": "Frase repetida dentro del texto analizado.",
            }
        )

    long_sentences = [s for s in sentences if len(s) > 180]
    repeated_ratio = min(len(repeated) * 8, 50)
    density_ratio = min(len(long_sentences) * 1.2, 20)
    score = round(min(repeated_ratio + density_ratio, 100), 2)

    if score >= 40:
        likely_issue = "revision_manual_urgente"
    elif score >= 20:
        likely_issue = "dependencia_fuerte_de_fuentes"
    elif repeated:
        likely_issue = "coincidencias_convencionales"
    else:
        likely_issue = "sin_hallazgos_relevantes"

    return {
        "overall_similarity": score,
        "risk_level": _risk_from_similarity(score),
        "likely_issue": likely_issue,
        "matches": matches,
        "notes": (
            "Resultado provisional basado en patrones internos del texto. "
            "Conecta aquí un motor real de similitud para comparar contra web, papers o repositorios."
        ),
        "disclaimer": (
            "Este resultado no prueba plagio. Solo señala coincidencias o patrones "
            "que requieren verificación humana y comparación con fuentes externas."
        ),
    }