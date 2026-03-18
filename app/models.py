from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


RiskLevel = Literal["Bajo", "Medio", "Alto", "Indeterminado"]
SimilarityScope = Literal["none", "internal_only", "corpus_only", "internal_and_corpus"]


class TextRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Texto a analizar")
    language: str = Field(default="es", description="Idioma principal del texto")
    title: str | None = Field(default=None, description="Titulo opcional del documento")


class ExternalSearchRequest(BaseModel):
    query: str = Field(..., min_length=10, description="Consulta para buscar fuentes externas")
    limit: int = Field(default=5, ge=1, le=10, description="Cantidad maxima de resultados por fuente")


class SimilarityMatch(BaseModel):
    text_span: str
    source_title: str
    source_url: str | None = None
    match_percent: float
    source_type: Literal["web", "paper", "student_paper", "internal", "reference_corpus", "unknown"] = "unknown"
    note: str | None = None


class SimilarityResponse(BaseModel):
    overall_similarity: float = Field(..., ge=0, le=100)
    internal_similarity_score: float = Field(default=0, ge=0, le=100)
    corpus_similarity_score: float = Field(default=0, ge=0, le=100)
    corpus_documents_checked: int = Field(default=0, ge=0)
    similarity_scope: SimilarityScope = "none"
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
    signal_strength: str


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


class StoredDocumentAnalysisResponse(DocumentAnalysisResponse):
    analysis_id: int | None = None


class AnalysisListItem(BaseModel):
    id: int
    title: str | None = None
    language: str | None = None
    overall_risk: RiskLevel | None = None
    similarity_score: float | None = None
    ai_risk_score: float | None = None
    created_at: datetime


class AnalysisDetailResponse(BaseModel):
    id: int
    title: str | None = None
    language: str | None = None
    text: str
    similarity_score: float | None = None
    similarity_risk: str | None = None
    ai_risk_score: float | None = None
    ai_risk_level: str | None = None
    overall_risk: RiskLevel | None = None
    summary: str | None = None
    conclusion: str | None = None
    recommendations: list[str]
    created_at: datetime


class ReferenceDocumentCreate(BaseModel):
    title: str = Field(..., min_length=3, description="Titulo del documento de referencia")
    text: str = Field(..., min_length=100, description="Texto del documento de referencia")
    language: str = Field(default="es", description="Idioma principal del documento")
    source: str | None = Field(default=None, description="Fuente opcional del documento")


class ReferenceDocumentListItem(BaseModel):
    id: int
    title: str
    language: str | None = None
    source: str | None = None
    created_at: datetime


class ReferenceDocumentDetail(BaseModel):
    id: int
    title: str
    text: str
    language: str | None = None
    source: str | None = None
    created_at: datetime


class ExternalSearchItem(BaseModel):
    source: Literal["crossref", "europe_pmc"]
    title: str
    url: str | None = None
    doi: str | None = None
    year: str | None = None
    authors: str | None = None
    journal: str | None = None
    match_score: float
    snippet: str | None = None


class ExternalSearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[ExternalSearchItem]
    notes: str
    disclaimer: str