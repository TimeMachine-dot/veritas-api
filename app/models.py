from typing import Literal
from pydantic import BaseModel, Field


RiskLevel = Literal["Bajo", "Medio", "Alto", "Indeterminado"]


class TextRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Texto a analizar")
    language: str = Field(default="es", description="Idioma principal del texto")
    title: str | None = Field(default=None, description="Título opcional del documento")


class SimilarityMatch(BaseModel):
    text_span: str
    source_title: str
    source_url: str | None = None
    match_percent: float
    source_type: Literal["web", "paper", "student_paper", "internal", "unknown"] = "unknown"
    note: str | None = None


class SimilarityResponse(BaseModel):
    overall_similarity: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    likely_issue: Literal[
        "sin_hallazgos_relevantes",
        "coincidencias_convencionales",
        "mala_citacion_potencial",
        "parafraseo_cercano_potencial",
        "dependencia_fuerte_de_fuentes",
        "revision_manual_urgente",
    ]
    matches: list[SimilarityMatch]
    notes: str
    disclaimer: str


class SuspiciousSegment(BaseModel):
    text_span: str
    reason: str
    signal_strength: Literal["débil", "moderada", "fuerte"]


class AIRiskResponse(BaseModel):
    ai_risk_score: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    segments: list[SuspiciousSegment]
    notes: str
    disclaimer: str
    from typing import Literal
from pydantic import BaseModel, Field


RiskLevel = Literal["Bajo", "Medio", "Alto", "Indeterminado"]


class TextRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Texto a analizar")
    language: str = Field(default="es", description="Idioma principal del texto")
    title: str | None = Field(default=None, description="Título opcional del documento")


class SimilarityMatch(BaseModel):
    text_span: str
    source_title: str
    source_url: str | None = None
    match_percent: float
    source_type: Literal["web", "paper", "student_paper", "internal", "unknown"] = "unknown"
    note: str | None = None


class SimilarityResponse(BaseModel):
    overall_similarity: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    likely_issue: Literal[
        "sin_hallazgos_relevantes",
        "coincidencias_convencionales",
        "mala_citacion_potencial",
        "parafraseo_cercano_potencial",
        "dependencia_fuerte_de_fuentes",
        "revision_manual_urgente",
    ]
    matches: list[SimilarityMatch]
    notes: str
    disclaimer: str


class SuspiciousSegment(BaseModel):
    text_span: str
    reason: str
    signal_strength: Literal["débil", "moderada", "fuerte"]


class AIRiskResponse(BaseModel):
    ai_risk_score: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    segments: list[SuspiciousSegment]
    notes: str
    disclaimer: str


class DocumentAnalysisResponse(BaseModel):
    title: str | None = None
    similarity: SimilarityResponse
    ai_risk: AIRiskResponse
    overall_risk: RiskLevel
    summary: str
    conclusion: str
    recommendations: list[str]
    disclaimer: str
