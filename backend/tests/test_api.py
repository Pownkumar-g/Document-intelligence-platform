"""Tests for the REST API endpoints."""

import os
import sys
import json
import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import init_db

# Ensure tables exist for test database
init_db()

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestDocumentListEndpoint:
    def test_list_documents_returns_list(self):
        response = client.get("/api/v1/documents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestDocumentProcessEndpoint:
    def test_unsupported_file_type(self):
        """Uploading a .txt file should be rejected."""
        response = client.post(
            "/api/v1/documents/process",
            data={"document_type": "invoice"},
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_invalid_document_type(self):
        """An invalid document_type should be rejected."""
        response = client.post(
            "/api/v1/documents/process",
            data={"document_type": "invalid_type"},
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "INVALID_DOCUMENT_TYPE"

    def test_empty_file(self):
        """An empty file should be rejected."""
        response = client.post(
            "/api/v1/documents/process",
            data={"document_type": "invoice"},
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400

    def test_corrupted_pdf(self):
        """A corrupted PDF should fail validation gracefully."""
        response = client.post(
            "/api/v1/documents/process",
            data={"document_type": "invoice"},
            files={"file": ("corrupt.pdf", b"not a real pdf", "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processing_status"] == "FAILED"
        assert data["file_validation"]["is_readable"] == False


class TestDocumentRetrieveEndpoint:
    def test_get_nonexistent_document(self):
        """Requesting a non-existent document should return 404."""
        response = client.get("/api/v1/documents/nonexistent_file.pdf")
        assert response.status_code == 404


class TestFrontendPages:
    def test_dashboard_loads(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "Document Intelligence Platform" in response.text

    def test_document_result_page_not_found(self):
        response = client.get("/document/nonexistent.pdf")
        assert response.status_code == 200  # page renders, shows "not found"
