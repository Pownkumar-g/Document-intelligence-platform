"""Document repository – persistence layer using SQLAlchemy."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.document import Document

logger = logging.getLogger("docextract")


class DocumentRepository:
    """CRUD operations for the documents table."""

    # ------------------------------------------------------------------
    # Save / upsert
    # ------------------------------------------------------------------
    @staticmethod
    def save_result(db: Session, result: dict[str, Any]) -> Document:
        """Insert or update a processed document result.

        If a record with the same document_name exists, it is updated
        (latest-wins semantics).
        """
        doc_name = result.get("document_name", "")
        existing = (
            db.query(Document)
            .filter(Document.document_name == doc_name)
            .first()
        )

        result_json = json.dumps(result, default=str)

        if existing:
            existing.document_type = result.get("document_type", "")
            existing.processing_status = result.get("processing_status", "FAILED")
            existing.overall_confidence = result.get("overall_confidence")
            existing.result_json = result_json
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            logger.info("Updated existing record for '%s'", doc_name)
            return existing

        doc = Document(
            document_name=doc_name,
            document_type=result.get("document_type", ""),
            processing_status=result.get("processing_status", "FAILED"),
            overall_confidence=result.get("overall_confidence"),
            result_json=result_json,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        logger.info("Saved new record for '%s' (id=%d)", doc_name, doc.id)
        return doc

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------
    @staticmethod
    def get_by_name(db: Session, document_name: str) -> Optional[dict[str, Any]]:
        """Retrieve the latest result for a given document name."""
        doc = (
            db.query(Document)
            .filter(Document.document_name == document_name)
            .order_by(Document.updated_at.desc())
            .first()
        )
        if doc is None:
            return None
        return json.loads(doc.result_json)

    @staticmethod
    def list_all(db: Session) -> list[dict[str, Any]]:
        """Return summary records for the dashboard."""
        docs = (
            db.query(Document)
            .order_by(Document.updated_at.desc())
            .all()
        )
        items = []
        for doc in docs:
            items.append({
                "document_name": doc.document_name,
                "document_type": doc.document_type,
                "processing_status": doc.processing_status,
                "overall_confidence": doc.overall_confidence,
                "processed_at": doc.updated_at.isoformat() if doc.updated_at else "",
            })
        return items
