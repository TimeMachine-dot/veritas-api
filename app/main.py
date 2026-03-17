from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .auth import verify_action_api_key
from .config import settings
from .db import init_db, get_db
from . import db_models

from .models import (
    TextRequest,
    SimilarityResponse,
    AIRiskResponse,
    StoredDocumentAnalysisResponse,
    AnalysisListItem,
    AnalysisDetailResponse,
)
from .services.similarity_service import check_similarity
from .services.ai_risk_service import check_ai_risk
from .services.document_analysis_service import analyze_document
from .services.analysis_store_service import save_analysis, list_analyses, get_analysis_by_id

app = FastAPI(
    title=settings.app_name,
    version="1.3.0",
    description="API para Veritas Academico: similitud, riesgo IA, analisis combinado, almacenamiento e historial."
)


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.app_env}


@app.post(
    "/check_similarity",
    response_model=SimilarityResponse,
    tags=["analysis"],
    dependencies=[Depends(verify_action_api_key)],
)
async def api_check_similarity(payload: TextRequest) -> dict:
    return await check_similarity(text=payload.text, language=payload.language)


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