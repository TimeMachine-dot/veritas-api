import re
from difflib import SequenceMatcher
import httpx

from ..config import settings


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    text = _normalize_spaces(text.lower())
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\wáéíóúñü\s]", "", text)
    return _normalize_spaces(text)


def _truncate(text: str | None, limit: int = 280) -> str | None:
    if not text:
        return None
    text = _normalize_spaces(re.sub(r"<[^>]+>", " ", text))
    return text[:limit]


def _score_candidate(query: str, title: str | None, snippet: str | None = None) -> float:
    q = _normalize_text(query)
    t = _normalize_text(title or "")
    s = _normalize_text(snippet or "")

    title_ratio = SequenceMatcher(None, q, t).ratio() if t else 0.0
    snippet_ratio = SequenceMatcher(None, q, s).ratio() if s else 0.0

    q_tokens = set(q.split())
    t_tokens = set(t.split())
    s_tokens = set(s.split())

    overlap_title = (len(q_tokens & t_tokens) / len(q_tokens)) if q_tokens and t_tokens else 0.0
    overlap_snippet = (len(q_tokens & s_tokens) / len(q_tokens)) if q_tokens and s_tokens else 0.0

    score = max(
        title_ratio * 100 * 0.65 + overlap_title * 100 * 0.35,
        snippet_ratio * 100 * 0.55 + overlap_snippet * 100 * 0.45,
    )
    return round(min(score, 100), 2)


async def _search_crossref(query: str, limit: int) -> list[dict]:
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": query,
        "rows": limit,
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

    return items


async def _search_europe_pmc(query: str, limit: int) -> list[dict]:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
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
        url = None

        pmid = item.get("pmid")
        pmcid = item.get("pmcid")
        if pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
        elif pmid:
            url = f"https://europepmc.org/article/MED/{pmid}"

        snippet = _truncate(item.get("abstractText"))
        score = _score_candidate(query, title, snippet)

        items.append(
            {
                "source": "europe_pmc",
                "title": title,
                "url": url,
                "doi": doi,
                "year": year,
                "authors": authors,
                "journal": journal,
                "match_score": score,
                "snippet": snippet,
            }
        )

    return items


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
    )[: limit * 2]

    return {
        "query": query,
        "total_results": len(results),
        "results": results,
        "notes": (
            "Busqueda externa realizada en Crossref y Europe PMC. "
            "Estos resultados muestran fuentes candidatas relacionadas por metadatos, titulos y, cuando estan disponibles, resúmenes."
        ),
        "disclaimer": (
            "Este resultado no prueba plagio ni coincidencia textual exacta con el documento completo. "
            "Sirve para identificar posibles fuentes externas que merecen revision adicional."
        ),
    }