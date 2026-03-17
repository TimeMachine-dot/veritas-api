import json
from sqlalchemy.orm import Session
from ..db_models import AnalysisRecord


def _parse_recommendations(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except Exception:
        return []


def save_analysis(
    db: Session,
    *,
    title: str | None,
    language: str,
    text: str,
    result: dict,
) -> int:
    record = AnalysisRecord(
        title=title,
        language=language,
        text=text,
        similarity_score=result["similarity"]["overall_similarity"],
        similarity_risk=result["similarity"]["risk_level"],
        ai_risk_score=result["ai_risk"]["ai_risk_score"],
        ai_risk_level=result["ai_risk"]["risk_level"],
        overall_risk=result["overall_risk"],
        summary=result["summary"],
        conclusion=result["conclusion"],
        recommendations=json.dumps(result["recommendations"], ensure_ascii=False),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def list_analyses(db: Session, limit: int = 20) -> list[dict]:
    records = (
        db.query(AnalysisRecord)
        .order_by(AnalysisRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "title": r.title,
            "language": r.language,
            "overall_risk": r.overall_risk,
            "similarity_score": r.similarity_score,
            "ai_risk_score": r.ai_risk_score,
            "created_at": r.created_at,
        }
        for r in records
    ]


def get_analysis_by_id(db: Session, analysis_id: int) -> dict | None:
    r = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if r is None:
        return None

    return {
        "id": r.id,
        "title": r.title,
        "language": r.language,
        "text": r.text,
        "similarity_score": r.similarity_score,
        "similarity_risk": r.similarity_risk,
        "ai_risk_score": r.ai_risk_score,
        "ai_risk_level": r.ai_risk_level,
        "overall_risk": r.overall_risk,
        "summary": r.summary,
        "conclusion": r.conclusion,
        "recommendations": _parse_recommendations(r.recommendations),
        "created_at": r.created_at,
    }