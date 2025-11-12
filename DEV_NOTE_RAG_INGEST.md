# RAG Ingest Dev Note

## Overview

**Endpoint:** `POST /ingest` (main.py:818-887)  
**Service:** `VertexIngestionService` (vertex_ingestion_service.py)  
**Status:** ✅ Working (with GCS import method)

## Data Storage Locations

Ingest writes to **4 different storage systems**:

1. **AWS S3** (raw upload) - Source of truth
2. **GCP GCS Bucket** (file copy) - Intermediate for Vertex AI
3. **Vertex AI RAG Corpus** (vector embeddings) - Search/retrieval
4. **Supabase `documents` table** (metadata) - Tracking & references

## Detailed Flow

### 1. AWS S3 (Already exists before ingest)
```
Bucket: AGANSWERS_S3_BUCKET_NAME
Path: courses/{course_name}/{uuid}-{filename}
Purpose: Source of truth for raw files
Action: READ ONLY (files uploaded separately before /ingest is called)
```

### 2. GCP GCS Bucket (Written during ingest)
```
Bucket: VERTEX_GCS_BUCKET (env var)
Path: gs://{bucket}/vertex-rag/{course_name}/{readable_filename}
Purpose: Intermediate storage for Vertex AI import
Action: WRITE (copy from S3)
Why: Enables rag.import_files() which avoids OAuth scope issues
```

### 3. Vertex AI RAG Corpus (Written during ingest)
```
Location: us-east4
Corpus: aganswers-documents-{course_name}
Purpose: Vector embeddings for semantic search
Action: WRITE via rag.import_files() or rag.upload_file()
Contains:
  - Chunked document text (512 char chunks, 100 char overlap)
  - Vector embeddings (gemini-embedding-001)
  - Metadata for retrieval
```

### 4. Supabase `documents` Table (Written during ingest)
```
Table: documents
Purpose: Metadata tracking and search indexing
Fields stored:
  - course_name
  - s3_path (reference to S3)
  - readable_filename
  - file_type (pdf, csv, html, txt, etc.)
  - summary (AI-generated, 2-3 sentences)
  - keywords (AI-extracted, 5-10 keywords)
  - vertex_corpus_id (reference to Vertex corpus)
  - vertex_document_id (reference to Vertex document)
  - column_headers (CSV only)
  - row_count (CSV only)
  - url (empty for file uploads)
  - base_url (empty for file uploads)
  - contexts (array of chunks with embeddings for fallback)
```

## Ingestion Methods

### Method 1: GCS Import (Preferred - No OAuth issues)
```python
# If VERTEX_GCS_BUCKET is set:
1. Download from S3 → temp file
2. Extract metadata sample
3. Upload temp file → GCS
4. rag.import_files(corpus, ["gs://bucket/path"])
5. List files to get vertex_document_id
6. Generate metadata with Vertex AI text model
7. Store in Supabase
```

### Method 2: Direct Upload (Fallback - Has OAuth scope issues)
```python
# If VERTEX_GCS_BUCKET not set:
1. Download from S3 → temp file
2. rag.upload_file(corpus, temp_file_path)  # ⚠️ OAuth scope error
3. Extract metadata
4. Store in Supabase
```

### Method 3: Local Fallback (No Vertex AI)
```python
# If Vertex AI disabled or fails:
1. Download from S3
2. Extract text (BeautifulSoup for HTML)
3. Chunk text (RecursiveCharacterTextSplitter)
4. Generate embeddings (OpenAI)
5. Store contexts in Supabase directly
```

## File Type Handling

### Unstructured Data (→ Vertex AI RAG)
- **PDF, TXT, MD, DOCX, HTML, images**
- Processed by Vertex AI:
  - Automatic OCR for images/PDFs
  - Text extraction
  - Chunking (512 chars, 100 overlap)
  - Embedding generation
  - Metadata extraction via Gemini

### Structured Data (→ Metadata only)
- **CSV, XLSX, XLS, JSON, XML**
- Metadata extraction:
  - Column headers
  - Row count
  - Keywords from column names
- NOT sent to Vertex AI RAG (no vector embeddings)

## Metadata Generation

**Using Vertex AI Text Model** (gemini-2.5-flash-lite):
```python
Prompt: "Analyze this document and provide:
1. A concise 2-3 sentence summary
2. A list of 5-10 relevant keywords"

Response parsed for:
- summary: str
- keywords: List[str]
```

## API Request/Response

### Request
```json
POST /ingest
{
  "course_name": "test",
  "s3_path": "courses/test/uuid-filename.pdf",
  "readable_filename": "My Document.pdf"
}
```

### Success Response
```json
{
  "success": true,
  "message": "Successfully ingested My Document.pdf",
  "file_type": "pdf",
  "is_structured": false,
  "metadata": {
    "vertex_corpus_id": "projects/.../ragCorpora/...",
    "vertex_document_id": "projects/.../ragFiles/...",
    "summary": "This document discusses...",
    "keywords": ["rag", "vector", "search", ...]
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "message": "Failed to ingest My Document.pdf"
}
```

## Key Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT_ID=search-477419
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
VERTEX_AI_LOCATION=us-east4
VERTEX_RAG_CORPUS_NAME=aganswers-documents
VERTEX_TEXT_MODEL=gemini-2.5-flash-lite

# For GCS import method (recommended)
VERTEX_GCS_BUCKET=aganswers-vertex-rag

# S3 (source files)
AGANSWERS_S3_BUCKET_NAME=your-s3-bucket

# Supabase (metadata)
SUPABASE_URL=https://...
SUPABASE_API_KEY=...

# Fallback embeddings
AGANSWERS_OPENAI_KEY=sk-...
```

## OAuth Scope Issue (SOLVED)

### Problem
`rag.upload_file()` fails with:
```
RefreshError('invalid_scope: Invalid OAuth scope or ID token audience provided.')
```

### Root Cause
- Service account credentials lack OAuth scope for file upload endpoint
- `rag.upload_file()` requires special OAuth token audience
- IAM roles alone are insufficient

### Solution
Use `rag.import_files()` with GCS paths instead:
- ✅ No OAuth scope issues
- ✅ Faster for large files
- ✅ Follows Google's recommended pattern
- ✅ Server-to-server (no token audience issues)

See: `VERTEX_OAUTH_ISSUE_SOLUTION.md`

## Comparison: Old vs New Ingest

### Old Ingest (beam/ingest.py)
- Stores: Qdrant (vectors) + Supabase (contexts + metadata)
- Embeddings: OpenAI or local models
- Chunking: LangChain RecursiveCharacterTextSplitter
- Search: Qdrant vector similarity
- Still used for: Legacy courses, specific use cases

### New Ingest (vertex_ingestion_service.py)
- Stores: Vertex AI RAG (vectors) + Supabase (metadata only)
- Embeddings: Vertex AI (gemini-embedding-001)
- Chunking: Vertex AI automatic (512/100)
- Search: Vertex AI RAG retrieval
- Used for: Spotlight search, new courses
- Benefits:
  - Automatic OCR
  - Better multilingual support
  - Managed infrastructure
  - No vector DB maintenance

## Data Flow Diagram

```
User Upload
    ↓
AWS S3 (raw file stored)
    ↓
POST /ingest {course_name, s3_path, readable_filename}
    ↓
vertex_service.ingest_document()
    ↓
┌─────────────────────────────────────────┐
│ 1. Download from S3 → temp file         │
│ 2. Copy to GCS (gs://bucket/path)       │
│ 3. rag.import_files(corpus, [gcs_path]) │
│ 4. Extract metadata with Gemini         │
│ 5. Store in Supabase documents table    │
└─────────────────────────────────────────┘
    ↓
Data stored in 4 locations:
    ├─ S3: Raw file (source of truth)
    ├─ GCS: Copy for Vertex AI
    ├─ Vertex RAG: Vector embeddings
    └─ Supabase: Metadata + references
```

## Viewing Ingested Data

### Supabase
```sql
SELECT * FROM documents 
WHERE course_name = 'test' 
ORDER BY created_at DESC;
```

### Vertex AI RAG
```bash
python view_rag_data.py
```

### GCS Bucket
```bash
gsutil ls gs://aganswers-vertex-rag/vertex-rag/
```

### S3 (original files)
```bash
aws s3 ls s3://your-bucket/courses/test/
```

## Testing

```bash
# Run diagnostics
python diagnose_vertex.py

# Test GCS import method
python test_gcs_import.py

# Test full endpoint
python test_ingest_endpoint.py

# View current data
python view_rag_data.py
```

## Common Issues

### 1. OAuth Scope Error
**Symptom:** `invalid_scope: Invalid OAuth scope or ID token audience provided`  
**Fix:** Set `VERTEX_GCS_BUCKET` env var to use GCS import method

### 2. Corpus Not Found
**Symptom:** `Corpus not found for course`  
**Fix:** Corpus is auto-created on first ingest. Check logs for creation errors.

### 3. File Not Appearing in Vertex
**Symptom:** `vertex_document_id` is None  
**Fix:** 
- Check GCS bucket permissions
- Verify file was copied to GCS
- Wait a few minutes (import is async)

### 4. Metadata Missing
**Symptom:** Summary/keywords are empty  
**Fix:** 
- Check `VERTEX_TEXT_MODEL` is set
- Verify Gemini API access
- Falls back to basic metadata if Gemini fails

## Performance Notes

- **Chunking:** 512 chars with 100 char overlap (Vertex AI default)
- **Embedding Model:** gemini-embedding-001 (768 dimensions)
- **Retrieval:** Top-K configurable (default: 3-10)
- **File Size Limit:** Vertex AI handles up to 100MB per file
- **Batch Import:** Can import multiple files at once via `rag.import_files()`

## Future Improvements

- [ ] Batch ingestion endpoint (multiple files at once)
- [ ] Webhook for async ingestion status
- [ ] Duplicate detection (check before ingesting)
- [ ] Update existing documents (versioning)
- [ ] Delete documents from Vertex RAG
- [ ] Custom chunking strategies per file type
- [ ] Support for more structured data formats

## Related Files

- `ai_ta_backend/main.py` - /ingest endpoint (818-887)
- `ai_ta_backend/service/vertex_ingestion_service.py` - Main service
- `ai_ta_backend/beam/ingest.py` - Legacy ingest (Qdrant)
- `VERTEX_OAUTH_ISSUE_SOLUTION.md` - OAuth scope fix
- `VIEWING_RAG_DATA.md` - How to view data in GCP

---

**Last Updated:** 2025-01-11  
**Status:** ✅ Production Ready (with GCS import method)


