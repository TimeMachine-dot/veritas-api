import re
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from ..db_models import ReferenceDocument


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    text = _normalize_spaces(text.lower())
    text = re.sub(r"[^\wáéíóúñü\s]", "", text)
    return text


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", _normalize_spaces(text))
    return [p.strip() for p in parts if len(p.strip()) > 40]


def compare_against_reference_corpus(
    db: Session,
    *,
    text: str,
    language: str = "es",
) -> dict:
    documents = db.query(ReferenceDocument).all()
    if not documents:
        return {
            "docs_count": 0,
            "overall_similarity": 0.0,
            "matches": [],
            "likely_issue": "sin_hallazgos_relevantes",
            "note": "No hay documentos de referencia cargados en el corpus.",
        }

    input_sentences = _split_sentences(text)
    matches = []

    for sentence in input_sentences:
        norm_sentence = _normalize_text(sentence)
        if len(norm_sentence) < 35:
            continue

        best_match = None
        best_score = 0.0

        for doc in documents:
            if doc.language and language and doc.language != language:
                continue

            ref_sentences = _split_sentences(doc.text)
            for ref_sentence in ref_sentences:
                norm_ref = _normalize_text(ref_sentence)
                if len(norm_ref) < 35:
                    continue

                score = SequenceMatcher(None, norm_sentence, norm_ref).ratio()
                if score > best_score:
                    best_score = score
                    best_match = {
                        "text_span": sentence[:300],
                        "source_title": doc.title,
                        "source_url": None,
                        "match_percent": round(score * 100, 2),
                        "source_type": "reference_corpus",
                        "note": f"Coincidencia contra documento del corpus: {doc.title}",
                    }

        if best_match and best_score >= 0.72:
            matches.append(best_match)

    matches = sorted(matches, key=lambda x: x["match_percent"], reverse=True)[:8]

    if not matches:
        return {
            "docs_count": len(documents),
            "overall_similarity": 0.0,
            "matches": [],
            "likely_issue": "sin_hallazgos_relevantes",
            "note": f"Se comparo contra {len(documents)} documentos del corpus sin hallar coincidencias relevantes.",
        }

    max_match = max(m["match_percent"] for m in matches)
    count_bonus = min(len(matches) * 6, 24)
    overall_similarity = round(min(max_match * 0.60 + count_bonus, 100), 2)

    if max_match >= 90:
        likely_issue = "revision_manual_urgente"
    elif max_match >= 82:
        likely_issue = "dependencia_fuerte_de_fuentes"
    elif max_match >= 75:
        likely_issue = "parafraseo_cercano_potencial"
    else:
        likely_issue = "mala_citacion_potencial"

    return {
        "docs_count": len(documents),
        "overall_similarity": overall_similarity,
        "matches": matches,
        "likely_issue": likely_issue,
        "note": f"Se comparo contra {len(documents)} documentos del corpus y se encontraron {len(matches)} coincidencias relevantes.",
    }