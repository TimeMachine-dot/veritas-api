import re
from collections import Counter


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    text = _normalize_spaces(text.lower())
    text = re.sub(r"[^\wáéíóúñü\s]", "", text)
    return text


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", _normalize_spaces(text))
    return [p.strip() for p in parts if len(p.strip()) > 35]


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    return [p for p in parts if len(p) > 60]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]+", text.lower())


def _risk_from_similarity(score: float) -> str:
    if score >= 45:
        return "Alto"
    if score >= 15:
        return "Medio"
    if score >= 0:
        return "Bajo"
    return "Indeterminado"


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def run_similarity_check(text: str, language: str = "es") -> dict:
    clean_text = _normalize_spaces(text)
    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)
    tokens = _tokenize(text)

    norm_sentences = [_normalize_text(s) for s in sentences]
    norm_paragraphs = [_normalize_text(p) for p in paragraphs]

    sentence_counts = Counter(s for s in norm_sentences if len(s) > 60)
    paragraph_counts = Counter(p for p in norm_paragraphs if len(p) > 120)

    repeated_sentences = {k: v for k, v in sentence_counts.items() if v > 1}
    repeated_paragraphs = {k: v for k, v in paragraph_counts.items() if v > 1}

    ngram_counts = Counter(_ngrams(tokens, 8))
    repeated_ngrams = {k: v for k, v in ngram_counts.items() if v > 2}

    matches = []

    for original in sentences:
        norm = _normalize_text(original)
        if norm in repeated_sentences and len(original) > 60:
            matches.append(
                {
                    "text_span": original[:300],
                    "source_title": "Repetición interna de oración",
                    "source_url": None,
                    "match_percent": 88.0,
                    "source_type": "internal",
                    "note": f"Oración repetida {repeated_sentences[norm]} veces dentro del mismo documento.",
                }
            )

    for original in paragraphs:
        norm = _normalize_text(original)
        if norm in repeated_paragraphs and len(original) > 120:
            matches.append(
                {
                    "text_span": original[:300],
                    "source_title": "Repetición interna de párrafo",
                    "source_url": None,
                    "match_percent": 94.0,
                    "source_type": "internal",
                    "note": f"Párrafo repetido {repeated_paragraphs[norm]} veces dentro del mismo documento.",
                }
            )

    for gram, count in list(repeated_ngrams.items())[:5]:
        matches.append(
            {
                "text_span": " ".join(gram),
                "source_title": "Secuencia léxica repetida",
                "source_url": None,
                "match_percent": 70.0,
                "source_type": "internal",
                "note": f"Secuencia de 8 palabras repetida {count} veces.",
            }
        )

    repeated_sentence_penalty = min(sum(v - 1 for v in repeated_sentences.values()) * 10, 35)
    repeated_paragraph_penalty = min(sum(v - 1 for v in repeated_paragraphs.values()) * 20, 40)
    repeated_ngram_penalty = min(len(repeated_ngrams) * 3, 20)

    score = round(min(repeated_sentence_penalty + repeated_paragraph_penalty + repeated_ngram_penalty, 100), 2)

    if repeated_paragraphs:
        likely_issue = "revision_manual_urgente"
    elif repeated_sentences and len(repeated_sentences) >= 2:
        likely_issue = "dependencia_fuerte_de_fuentes"
    elif repeated_sentences or repeated_ngrams:
        likely_issue = "coincidencias_convencionales"
    else:
        likely_issue = "sin_hallazgos_relevantes"

    notes = (
        "Análisis interno de repetición y similitud dentro del mismo texto. "
        "Este resultado no compara contra internet, artículos ni repositorios externos. "
        "Sirve para detectar reutilización, duplicación o redacción excesivamente repetitiva."
    )

    return {
        "overall_similarity": score,
        "risk_level": _risk_from_similarity(score),
        "likely_issue": likely_issue,
        "matches": matches[:8],
        "notes": notes,
        "disclaimer": (
            "Este resultado no prueba plagio externo. "
            "Solo identifica coincidencias internas y patrones que requieren revisión humana."
        ),
    }