"""SQLAlchemy ORM model for processed documents."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class Document(Base):
    """Stores processed document metadata and full JSON result."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_name = Column(String(255), index=True, nullable=False)
    document_type = Column(String(50), nullable=False)
    processing_status = Column(String(20), nullable=False, default="FAILED")
    overall_confidence = Column(Float, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Document(name={self.document_name!r}, "
            f"type={self.document_type!r}, "
            f"status={self.processing_status!r})>"
        )
