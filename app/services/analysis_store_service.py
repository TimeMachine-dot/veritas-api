import json
from sqlalchemy.orm import Session
from ..db_models import AnalysisRecord


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