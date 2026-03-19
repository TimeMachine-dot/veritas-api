import re
from difflib import SequenceMatcher
import httpx

from ..config import settings


SPANISH_STOPWORDS = {
    "de", "la", "el", "los", "las", "y", "o", "u", "un", "una", "unos", "unas",
    "del", "al", "por", "para", "con", "sin", "sobre", "entre", "hacia", "desde",
    "en", "se", "que", "como", "su", "sus", "es", "son", "fue", "han", "ha",
    "paper", "articulo", "artículo", "estudio", "estudios", "documento", "texto",
    "tema", "general", "generales", "investigacion", "investigación", "analisis",
    "análisis", "economia", "economía", "economics"
}

ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "without",
    "from", "by", "at", "as", "is", "are", "was", "were", "be", "been", "that",
    "this", "these", "those", "about", "into", "between", "paper", "study",
    "studies", "article", "text", "general", "economics"
}

STOPWORDS = SPANISH_STOPWORDS | ENGLISH_STOPWORDS

DOMAIN_TERMS = {
    "copper", "mining", "fiscal", "revenue", "cointegration",
    "commodity", "commodities", "tax", "taxation", "royalty",
    "minerals", "ore", "precio", "cobre", "mineria", "minería",
    "ingresos", "fiscales", "recaudacion", "recaudación", "tributario",
    "tributaria", "cointegracion", "cointegración", "commodity"
}


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_text(text: str) -> str:
    text = _normalize_spaces(text.lower())
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\wáéíóúñü\s-]", " ", text)
    return _normalize_spaces(text)


def _truncate(text: str | None, limit: int = 280) -> str | None:
    if not text:
        return None
    text = _normalize_spaces(re.sub(r"<[^>]+>", " ", text))
    return text[:limit]


def _extract_keywords(query: str) -> list[str]:
    q = _normalize_text(query)
    raw_tokens = re.findall(r"[a-záéíóúñü0-9-]+", q)

    keywords = []
    seen = set()

    for tok in raw_tokens:
        if len(tok) < 3:
            continue
        if tok in STOPWORDS:
            continue
        if tok not in seen:
            seen.add(tok)
            keywords.append(tok)

    # Prioriza términos de dominio primero
    domain_first = [k for k in keywords if k in DOMAIN_TERMS]
    others = [k for k in keywords if k not in DOMAIN_TERMS]

    ordered = domain_first + others
    return ordered[:10]


def _prepare_query(query: str) -> str:
    keywords = _extract_keywords(query)
    if not keywords:
        return query
    return " ".join(keywords[:8])


def _keyword_hits(keywords: list[str], text: str) -> list[str]:
    norm = _normalize_text(text)
    tokens = set(norm.split())
    hits = [k for k in keywords if k in tokens]
    return hits


def _phrase_bonus(query_keywords: list[str], text: str) -> float:
    norm_text = _normalize_text(text)
    if len(query_keywords) < 2:
        return 0.0

    bonus = 0.0
    for i in range(len(query_keywords) - 1):
        phrase = f"{query_keywords[i]} {query_keywords[i + 1]}"
        if phrase in norm_text:
            bonus += 6.0

    return min(bonus, 18.0)


def _score_candidate(query: str, title: str | None, snippet: str | None = None) -> float:
    q_keywords = _extract_keywords(query)
    if not q_keywords:
        return 0.0

    title = title or ""
    snippet = snippet or ""

    norm_query = _normalize_text(query)
    norm_title = _normalize_text(title)
    norm_snippet = _normalize_text(snippet)

    title_ratio = SequenceMatcher(None, norm_query, norm_title).ratio() if norm_title else 0.0
    snippet_ratio = SequenceMatcher(None, norm_query, norm_snippet).ratio() if norm_snippet else 0.0

    title_hits = _keyword_hits(q_keywords, title)
    snippet_hits = _keyword_hits(q_keywords, snippet)

    title_overlap = (len(title_hits) / len(q_keywords)) * 100
    snippet_overlap = (len(snippet_hits) / len(q_keywords)) * 100

    domain_hits_title = [k for k in title_hits if k in DOMAIN_TERMS]
    domain_hits_snippet = [k for k in snippet_hits if k in DOMAIN_TERMS]

    score = 0.0
    score += title_overlap * 0.45
    score += snippet_overlap * 0.20
    score += title_ratio * 100 * 0.20
    score += snippet_ratio * 100 * 0.10

    # Bonos por términos importantes en el título
    score += min(len(domain_hits_title) * 7.0, 21.0)
    score += min(len(domain_hits_snippet) * 3.0, 9.0)

    # Bonos por frases cercanas
    score += _phrase_bonus(q_keywords, title) * 1.0
    score += _phrase_bonus(q_keywords, snippet) * 0.5

    # Bonus fuerte si el título contiene varios términos clave
    if len(title_hits) >= 3:
        score += 10.0
    if len(domain_hits_title) >= 2:
        score += 12.0

    # Penalizaciones por coincidencia demasiado genérica
    if len(title_hits) <= 1 and len(snippet_hits) <= 1:
        score -= 15.0

    if len(domain_hits_title) == 0 and len(domain_hits_snippet) == 0:
        score -= 12.0

    # Penaliza series repetitivas muy generales si no hay términos fuertes
    generic_series_patterns = [
        "revenue statistics",
        "country note",
        "edition",
        "statistical report",
    ]
    norm_title_compact = norm_title
    if any(p in norm_title_compact for p in generic_series_patterns) and len(domain_hits_title) < 2:
        score -= 10.0

    return round(max(0.0, min(score, 100.0)), 2)


def _dedupe_results(results: list[dict]) -> list[dict]:
    seen = set()
    deduped = []

    for item in results:
        title_key = _normalize_text(item.get("title", ""))
        doi_key = (item.get("doi") or "").lower().strip()
        key = doi_key if doi_key else f"{item.get('source')}::{title_key}"

        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


async def _search_crossref(query: str, limit: int) -> list[dict]:
    prepared_query = _prepare_query(query)

    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": prepared_query,
        "rows": limit * 3,
    }
    if settings.crossref_mailto:
        params["mailto"] = settings.crossref_mailto

    headers = {
        "User-Agent": f"VeritasAcademicAPI/1.0 ({settings.crossref_mailto or 'no-reply@example.com'})"
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

    items = []
    for item in data.get("message", {}).get("items", []):
        title_list = item.get("title", []) or []
        title = title_list[0] if title_list else "Untitled"

        doi = item.get("DOI")
        year = None
        issued = item.get("issued", {})
        date_parts = issued.get("date-parts", [])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])

        authors_list = item.get("author", []) or []
        authors = []
        for a in authors_list[:4]:
            given = a.get("given", "")
            family = a.get("family", "")
            full = f"{given} {family}".strip()
            if full:
                authors.append(full)

        journal_list = item.get("container-title", []) or []
        journal = journal_list[0] if journal_list else None

        snippet = _truncate(item.get("abstract"))
        score = _score_candidate(query, title, snippet)

        items.append(
            {
                "source": "crossref",
                "title": title,
                "url": item.get("URL"),
                "doi": doi,
                "year": year,
                "authors": ", ".join(authors) if authors else None,
                "journal": journal,
                "match_score": score,
                "snippet": snippet,
            }
        )

    items = _dedupe_results(items)
    items = sorted(items, key=lambda x: x["match_score"], reverse=True)
    return items[:limit]


async def _search_europe_pmc(query: str, limit: int) -> list[dict]:
    prepared_query = _prepare_query(query)

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": prepared_query,
        "format": "json",
        "pageSize": limit * 3,
        "resultType": "core",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    items = []
    for item in data.get("resultList", {}).get("result", []):
        title = item.get("title") or "Untitled"
        doi = item.get("doi")
        year = item.get("pubYear")
        authors = item.get("authorString")
        journal = item.get("journalTitle")

        url_value = None
        pmid = item.get("pmid")
        pmcid = item.get("pmcid")
        if pmcid:
            url_value = f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
        elif pmid:
            url_value = f"https://europepmc.org/article/MED/{pmid}"

        snippet = _truncate(item.get("abstractText"))
        score = _score_candidate(query, title, snippet)

        items.append(
            {
                "source": "europe_pmc",
                "title": title,
                "url": url_value,
                "doi": doi,
                "year": year,
                "authors": authors,
                "journal": journal,
                "match_score": score,
                "snippet": snippet,
            }
        )

    items = _dedupe_results(items)
    items = sorted(items, key=lambda x: x["match_score"], reverse=True)
    return items[:limit]


async def external_search(query: str, limit: int | None = None) -> dict:
    limit = limit or settings.external_search_limit or 5
    limit = max(1, min(limit, 10))

    crossref_items = []
    europe_pmc_items = []

    try:
        crossref_items = await _search_crossref(query, limit)
    except Exception:
        crossref_items = []

    try:
        europe_pmc_items = await _search_europe_pmc(query, limit)
    except Exception:
        europe_pmc_items = []

    results = sorted(
        crossref_items + europe_pmc_items,
        key=lambda x: x["match_score"],
        reverse=True,
    )

    results = _dedupe_results(results)
    results = results[: limit * 2]

    return {
        "query": query,
        "total_results": len(results),
        "results": results,
        "notes": (
            "Busqueda externa realizada en Crossref y Europe PMC. "
            "El ranking prioriza coincidencia de terminos clave, relevancia del titulo y proximidad del resumen cuando esta disponible."
        ),
        "disclaimer": (
            "Este resultado no prueba plagio ni coincidencia textual exacta con el documento completo. "
            "Sirve para identificar posibles fuentes externas que merecen revision adicional."
        ),
    }