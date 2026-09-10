# Document Intelligence Platform

AI-powered document extraction, validation & API platform for financial documents.

## 🏗️ Solution Overview

This platform accepts financial documents (Invoices, Balance Sheets, Profit & Loss statements, Cash Flow Statements) in PDF/JPG/PNG format, extracts all visible fields using AI (Google Gemini 2.0 Flash), performs financial validation checks, stores results in a database, and presents them through a REST API and web dashboard.

### Architecture

```
┌───────────────────┐        ┌───────────────────────────────────┐
│   Frontend        │  HTTP  │   FastAPI Backend                  │
│   (Jinja2 + CSS)  │◄──────►│                                    │
│   Dashboard       │        │  POST /api/v1/documents/process    │
│   Upload Form     │        │  GET  /api/v1/documents/{name}     │
│   Result Viewer   │        │  GET  /api/v1/documents            │
└───────────────────┘        │  GET  /api/v1/health               │
                             │                                    │
                             │  Pipeline:                         │
                             │  Upload → Validate → OCR → AI     │
                             │  Extract → Financial Validate →    │
                             │  Store → Response                  │
                             │                                    │
                             │  DB: SQLite (SQLAlchemy ORM)       │
                             └───────────────────────────────────┘
```

## 🛠️ Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend | **FastAPI** | Async, auto Swagger/OpenAPI docs, Pydantic validation |
| AI/LLM | **Google Gemini 2.0 Flash** | Free tier, multimodal (images+PDF), structured JSON output |
| OCR | **Gemini Vision + PyMuPDF** | Gemini handles image-based OCR; PyMuPDF extracts native PDF text |
| PDF Processing | **PyMuPDF (fitz)** | Fast text extraction, page rendering, integrity checks |
| Database | **SQLite + SQLAlchemy** | Zero-config, file-based, suitable for deployment |
| Frontend | **Jinja2 + HTML/CSS/JS** | Server-side rendering, no separate frontend build needed |
| Deployment | **Render** | Free tier, Docker support |

## 🚀 Local Setup

### Prerequisites
- Python 3.12+
- Google Gemini API key (free from [Google AI Studio](https://aistudio.google.com/))

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd neoass

# Create virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Run Locally

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/api/v1/health

### Run Tests

```bash
cd backend
pytest tests/ -v
```

## 🌐 Deployed URLs

| Resource | URL |
|----------|-----|
| Frontend Dashboard | `https://document-intelligence-platform-1-fw40.onrender.com/` |
| Backend API | `https://document-intelligence-platform-1-fw40.onrender.com/docs` |
| Swagger/OpenAPI Docs | `https://document-intelligence-platform-1-fw40.onrender.com/docs` |
| Health Endpoint | `https://document-intelligence-platform-1-fw40.onrender.com/api/v1/health` |
| GitHub Repository | `https://github.com/Pownkumar-g/Document-intelligence-platform` |

## 📡 API Reference

### POST /api/v1/documents/process
Upload and process a document.

```bash
curl -X POST "<base-url>/api/v1/documents/process" \
  -F "file=@invoice.pdf" \
  -F "document_type=invoice"
```

**Parameters:**
- `file`: Document file (PDF/JPG/PNG)
- `document_type`: One of `invoice`, `balance_sheet`, `profit_and_loss`, `cash_flow_statement`

### GET /api/v1/documents/{document_name}
Retrieve the latest result by document name.

```bash
curl "<base-url>/api/v1/documents/sample_invoice.pdf"
```

### GET /api/v1/documents
List all processed documents.

```bash
curl "<base-url>/api/v1/documents"
```

### GET /api/v1/health
Health check.

```bash
curl "<base-url>/api/v1/health"
```

## 🔧 Environment Variables

See `.env.example`:

| Variable | Description | Required |
|----------|------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `DATABASE_URL` | SQLAlchemy database URL | No (defaults to SQLite) |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING) | No (defaults to INFO) |
| `MAX_PAGES` | Maximum pages allowed per document | No (defaults to 3) |

## 🤖 OCR/LLM Details

- **OCR**: Google Gemini 2.0 Flash's multimodal vision capabilities serve as the primary OCR engine. For native PDFs, PyMuPDF extracts text directly; for scanned/image documents, Gemini reads the images.
- **LLM**: Google Gemini 2.0 Flash with JSON mode for structured extraction. Temperature set to 0.1 for deterministic output.
- **Confidence Scoring**: Gemini provides confidence scores (0-1) based on text readability and extraction certainty.

## ✅ Financial Validation Rules

| Document | Validation | Tolerance |
|----------|-----------|-----------|
| Invoice | qty × unit_price ≈ line_total | ±1.0 |
| Invoice | sum(line_totals) ≈ subtotal | ±1.0 |
| Invoice | subtotal + tax - discount ≈ total | ±1.0 |
| Invoice | cash - total ≈ change | ±1.0 |
| Balance Sheet | Total Assets ≈ Total Capital & Liabilities | ±1.0 |
| Balance Sheet | sum(components) ≈ reported total | ±1.0 |
| P&L | sum(income_items) ≈ Total Income | ±1.0 |
| P&L | sum(expenditure_items) ≈ Total Expenditure | ±1.0 |
| P&L | Total Income - Total Expenditure ≈ Net Profit | ±1.0 |
| Cash Flow | Operating + Investing + Financing ≈ Net Change | ±1.0 |
| Cash Flow | Opening + Net Change ≈ Closing | ±1.0 |

Missing fields result in `NOT_APPLICABLE` status (not assumed/invented).

## 💾 Database/Persistence

- **Engine**: SQLite via SQLAlchemy ORM
- **Storage**: Full JSON response stored in `result_json` column alongside indexed metadata fields
- **Upsert**: Processing the same filename overwrites the previous result (latest wins)
- **Location**: `./data/documents.db` (auto-created on startup)

## ⚠️ Known Limitations

1. **Free-tier rate limits**: Gemini free tier allows 15 requests/minute; batch processing may need throttling
2. **SQLite on deployment**: Data persists across restarts but not across redeployments on free-tier platforms
3. **Scanned document quality**: Very low-resolution or heavily damaged scans may produce lower accuracy
4. **Large tables**: Documents with very dense financial tables (many columns/rows) may occasionally miss values
5. **Currency detection**: Currency is inferred from document context; multi-currency documents may need manual review

## 🚀 Production Improvements

1. **Managed database**: PostgreSQL or Cloud SQL instead of SQLite for durability
2. **Async processing**: Queue-based processing (Celery/Redis) for large batches
3. **Document versioning**: Store all processing versions, not just latest
4. **Authentication**: API key or OAuth2 for access control
5. **Caching**: Redis cache for repeated document lookups
6. **Monitoring**: Prometheus metrics, Sentry error tracking
7. **File storage**: Cloud storage (S3/GCS) for uploaded documents
8. **CI/CD**: Automated testing and deployment pipeline
9. **Multi-model ensemble**: Use multiple AI models and reconcile results
10. **Human-in-the-loop**: Low-confidence extractions flagged for manual review

## 🤖 AI Tools Used

- **Google Gemini (Antigravity)**: Used for project scaffolding, code generation, and documentation
- **Google Gemini 2.0 Flash**: Runtime AI model for document extraction

## 📄 License

This project was created as part of an AI Engineer Internship case study.
