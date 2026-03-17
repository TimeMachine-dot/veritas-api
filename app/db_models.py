from sqlalchemy import Column, Integer, Float, String, Text, DateTime
from sqlalchemy.sql import func
from .db import Base


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    language = Column(String(20), nullable=True)

    text = Column(Text, nullable=False)

    similarity_score = Column(Float, nullable=True)
    similarity_risk = Column(String(50), nullable=True)

    ai_risk_score = Column(Float, nullable=True)
    ai_risk_level = Column(String(50), nullable=True)

    overall_risk = Column(String(50), nullable=True)

    summary = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())