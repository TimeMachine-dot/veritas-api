from fastapi import Depends, FastAPI
from .auth import verify_action_api_key
from .config import settings
from .models import TextRequest, SimilarityResponse, AIRiskResponse
from .services.similarity_service import check_similarity
from .services.ai_risk_service import check_ai_risk

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="API para Veritas Académico: similitud y riesgo IA."
)


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