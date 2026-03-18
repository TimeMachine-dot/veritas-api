from sqlalchemy.orm import Session
from ..db_models import ReferenceDocument


def save_reference_document(
    db: Session,
    *,
    title: str,
    text: str,
    language: str = "es",
    source: str | None = None,
) -> int:
    record = ReferenceDocument(
        title=title,
        text=text,
        language=language,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def list_reference_documents(db: Session, limit: int = 50) -> list[dict]:
    records = (
        db.query(ReferenceDocument)
        .order_by(ReferenceDocument.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "title": r.title,
            "language": r.language,
            "source": r.source,
            "created_at": r.created_at,
        }
        for r in records
    ]


def get_reference_document_by_id(db: Session, document_id: int) -> dict | None:
    r = db.query(ReferenceDocument).filter(ReferenceDocument.id == document_id).first()
    if r is None:
        return None

    return {
        "id": r.id,
        "title": r.title,
        "text": r.text,
        "language": r.language,
        "source": r.source,
        "created_at": r.created_at,
    }