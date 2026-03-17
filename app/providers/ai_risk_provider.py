import re
from collections import Counter


GENERIC_PHRASES = [
    "en conclusión",
    "por otro lado",
    "asimismo",
    "en ese sentido",
    "cabe destacar",
    "por consiguiente",
    "de esta manera",
    "en definitiva",
    "es importante destacar",
    "resulta fundamental",
    "a lo largo del tiempo",
    "en la actualidad",
    "diversos autores coinciden",
    "es necesario considerar",
    "desde esta perspectiva",
    "en términos generales",
]

SPECIFICITY_HINTS = [
    "según",
    "tabla",
    "figura",
    "gráfico",
    "coeficiente",
    "variable",
    "hipótesis",
    "modelo",
    "muestra",
    "estimación",
    "perú",
    "cajamarca",
    "bcrp",
    "inei",
]


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", _normalize_spaces(text))
    return [p.strip() for p in parts if len(p.strip()) > 25]


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    return [p for p in parts if len(p) > 30]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]+", text.lower())


def _risk_from_score(score: float) -> str:
    if score >= 0.70:
        return "Alto"
    if score >= 0.25:
        return "Medio"
    if score >= 0:
        return "Bajo"
    return "Indeterminado"


def run_ai_risk_check(text: str, language: str = "es") -> dict:
    clean_text = _normalize_spaces(text)
    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)
    tokens = _tokenize(text)

    if not tokens:
        return {
            "ai_risk_score": 0.0,
            "risk_level": "Indeterminado",
            "segments": [],
            "notes": "No hubo suficiente contenido para analizar.",
            "disclaimer": (
                "Este resultado no demuestra autoría por IA. "
                "Solo estima señales compatibles con generación o edición intensiva mediante IA."
            ),
        }

    token_count = len(tokens)
    unique_tokens = len(set(tokens))
    lexical_diversity = unique_tokens / token_count if token_count else 0

    sentence_lengths = [len(_tokenize(s)) for s in sentences if len(_tokenize(s)) > 0]
    paragraph_lengths = [len(_tokenize(p)) for p in paragraphs if len(_tokenize(p)) > 0]

    avg_sentence_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    avg_paragraph_len = sum(paragraph_lengths) / len(paragraph_lengths) if paragraph_lengths else 0

    similar_paragraph_sizes = 0
    if len(paragraph_lengths) >= 4:
        avg_len = avg_paragraph_len
        similar_paragraph_sizes = sum(1 for x in paragraph_lengths if abs(x - avg_len) <= 8)

    lower_text = clean_text.lower()
    generic_hits = sum(lower_text.count(p) for p in GENERIC_PHRASES)
    specificity_hits = sum(lower_text.count(p) for p in SPECIFICITY_HINTS)

    sentence_starts = []
    for s in sentences:
        toks = _tokenize(s)
        if len(toks) >= 4:
            sentence_starts.append(" ".join(toks[:4]))
    repeated_starts = sum(c - 1 for c in Counter(sentence_starts).values() if c > 1)

    bigrams = list(zip(tokens, tokens[1:]))
    bigram_counts = Counter(bigrams)
    repeated_bigrams = sum(c - 2 for c in bigram_counts.values() if c >= 3)

    score = 0.0

    # Baja diversidad léxica
    if lexical_diversity < 0.42:
        score += 0.18
    elif lexical_diversity < 0.50:
        score += 0.10

    # Longitud de oraciones muy “limpia” y estable
    if 16 <= avg_sentence_len <= 24:
        score += 0.08

    # Uniformidad estructural de párrafos
    if similar_paragraph_sizes >= max(4, len(paragraph_lengths) // 2):
        score += 0.12

    # Más sensibilidad a frases genéricas
    score += min(generic_hits * 0.07, 0.30)

    # Repetición de arranques de oración
    score += min(repeated_starts * 0.05, 0.15)

    # Repetición de combinaciones léxicas
    score += min(repeated_bigrams * 0.01, 0.10)

    # La especificidad reduce sospecha
    score -= min(specificity_hits * 0.03, 0.18)

    # Castigo adicional si el texto es muy general y no tiene anclajes concretos
    if generic_hits >= 6 and specificity_hits == 0:
        score += 0.08

    score = max(0.0, min(round(score, 2), 0.95))

    segments = []

    for s in sentences:
        lower_s = s.lower()
        matched = [p for p in GENERIC_PHRASES if p in lower_s]
        if matched:
            segments.append(
                {
                    "text_span": s[:280],
                    "reason": f"Frase académica genérica detectada: {matched[0]}.",
                    "signal_strength": "moderada" if len(matched) == 1 else "fuerte",
                }
            )
        if len(segments) >= 3:
            break

    if len(segments) < 3 and similar_paragraph_sizes >= max(4, len(paragraph_lengths) // 2):
        segments.append(
            {
                "text_span": "Varios párrafos presentan una longitud muy parecida.",
                "reason": "Uniformidad estructural superior a la esperada en redacción humana variada.",
                "signal_strength": "moderada",
            }
        )

    if len(segments) < 3 and lexical_diversity < 0.45:
        segments.append(
            {
                "text_span": "Se observa reutilización significativa de vocabulario y patrones.",
                "reason": "Diversidad léxica baja para la extensión del texto.",
                "signal_strength": "moderada",
            }
        )

    notes = (
        f"Análisis heurístico interno del texto. Diversidad léxica: {lexical_diversity:.2f}. "
        f"Frases genéricas detectadas: {generic_hits}. Señales de especificidad: {specificity_hits}. "
        "Este resultado es orientativo y debe complementarse con revisión humana."
    )

    return {
        "ai_risk_score": score,
        "risk_level": _risk_from_score(score),
        "segments": segments[:5],
        "notes": notes,
        "disclaimer": (
            "Este resultado no demuestra autoría por IA. "
            "Solo estima señales compatibles con generación o edición intensiva mediante IA."
        ),
    }