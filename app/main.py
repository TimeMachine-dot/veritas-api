from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .auth import verify_action_api_key
from .config import settings
from .db import init_db, get_db
from . import db_models

from .models import (
    TextRequest,
    ExternalSearchRequest,
    SimilarityResponse,
    AIRiskResponse,
    StoredDocumentAnalysisResponse,
    AnalysisListItem,
    AnalysisDetailResponse,
    ReferenceDocumentCreate,
    ReferenceDocumentListItem,
    ReferenceDocumentDetail,
    ExternalSearchResponse,
)
from .services.similarity_service import check_similarity
from .services.ai_risk_service import check_ai_risk
from .services.document_analysis_service import analyze_document
from .services.analysis_store_service import save_analysis, list_analyses, get_analysis_by_id
from .services.reference_store_service import (
    save_reference_document,
    list_reference_documents,
    get_reference_document_by_id,
)
from .services.external_search_service import external_search

app = FastAPI(
    title=settings.app_name,
    version="1.6.0",
    description="API para Veritas Academico: similitud, riesgo IA, analisis combinado, almacenamiento, historial, corpus de referencia y busqueda externa."
)


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.app_env}


@app.post(
    "/external_search",
    response_model=ExternalSearchResponse,
    tags=["external"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_external_search(payload: ExternalSearchRequest) -> dict:
    return await external_search(query=payload.query, limit=payload.limit)


@app.post(
    "/reference_documents",
    response_model=dict,
    tags=["references"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_create_reference_document(
    payload: ReferenceDocumentCreate,
    db: Session = Depends(get_db),
) -> dict:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    document_id = save_reference_document(
        db,
        title=payload.title,
        text=payload.text,
        language=payload.language,
        source=payload.source,
    )
    return {"document_id": document_id, "status": "stored"}


@app.get(
    "/reference_documents",
    response_model=list[ReferenceDocumentListItem],
    tags=["references"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_list_reference_documents(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    limit = max(1, min(limit, 100))
    return list_reference_documents(db, limit=limit)


@app.get(
    "/reference_documents/{document_id}",
    response_model=ReferenceDocumentDetail,
    tags=["references"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_get_reference_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    result = get_reference_document_by_id(db, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Reference document not found.")

    return result


@app.post(
    "/check_similarity",
    response_model=SimilarityResponse,
    tags=["analysis"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_check_similarity(
    payload: TextRequest,
    db: Session = Depends(get_db),
) -> dict:
    return await check_similarity(text=payload.text, language=payload.language, db=db)


@app.post(
    "/check_ai_risk",
    response_model=AIRiskResponse,
    tags=["analysis"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_check_ai_risk(payload: TextRequest) -> dict:
    return await check_ai_risk(text=payload.text, language=payload.language)


@app.post(
    "/analyze_document",
    response_model=StoredDocumentAnalysisResponse,
    tags=["analysis"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_analyze_document(
    payload: TextRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = await analyze_document(
        text=payload.text,
        language=payload.language,
        title=payload.title,
        db=db,
    )

    analysis_id = None
    if db is not None:
        analysis_id = save_analysis(
            db,
            title=payload.title,
            language=payload.language,
            text=payload.text,
            result=result,
        )

    result["analysis_id"] = analysis_id
    return result


@app.get(
    "/analyses",
    response_model=list[AnalysisListItem],
    tags=["history"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_list_analyses(
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict]:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    limit = max(1, min(limit, 100))
    return list_analyses(db, limit=limit)


@app.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisDetailResponse,
    tags=["history"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
) -> dict:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    result = get_analysis_by_id(db, analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return result