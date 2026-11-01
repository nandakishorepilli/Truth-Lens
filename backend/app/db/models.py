"""SQLAlchemy 2.x models for persisting evaluation reports."""
from __future__ import annotations

from typing import Any
from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EvaluationRecord(Base):
    __tablename__ = "evaluations"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    sources_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    skipped_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    metrics_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    config_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    stages_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    limitations_data: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    claims: Mapped[list[ClaimRecord]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ClaimRecord.position",
    )
    verifications: Mapped[list[VerificationRecord]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="VerificationRecord.id",
    )


class ClaimRecord(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("evaluations.run_id", ondelete="CASCADE"), index=True, nullable=False
    )
    claim_id: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    evaluation: Mapped[EvaluationRecord] = relationship(back_populates="claims")


class VerificationRecord(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("evaluations.run_id", ondelete="CASCADE"), index=True, nullable=False
    )
    claim_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    supporting_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    contradicting_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    evaluation: Mapped[EvaluationRecord] = relationship(back_populates="verifications")
