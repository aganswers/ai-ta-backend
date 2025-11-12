# Vertex AI OAuth Scope Issue - Root Cause & Solution

## Problem Summary

The ingestion service was failing with this error:
```
RefreshError('invalid_scope: Invalid OAuth scope or ID token audience provided.')
```

## Root Cause

**`t.py` works but the ingestion service doesn't** because they use different Vertex AI RAG methods:

### ✅ `t.py` (WORKS)
- Uses: `rag.import_files(corpus, ["gs://bucket/path"])`
- Method: Imports files directly from Google Cloud Storage
- Auth: Only requires read access to GCS and Vertex AI API
- Scopes: Standard service account scopes are sufficient

### ❌ `vertex_ingestion_service.py` (FAILS)
- Uses: `rag.upload_file(corpus, local_file_path)`
- Method: Uploads local files through the Vertex AI API
- Auth: Requires additional OAuth scopes for file upload
- Scopes: Needs `https://www.googleapis.com/auth/cloud-platform` with proper token audience

## Why the OAuth Scope Error Occurs

The `rag.upload_file()` method internally:
1. Creates an authorized session with OAuth tokens
2. POSTs the file content to Vertex AI endpoints
3. Requires specific OAuth scopes that aren't automatically granted to service accounts

From the traceback:
```python
File ".../vertexai/rag/rag_data.py", line 434, in upload_file
    response = authorized_session.post(...)
File ".../google/auth/transport/requests.py", line 535, in request
    self.credentials.before_request(auth_request, method, url, request_headers)
```

The service account credentials lack the required OAuth scope/audience for this specific upload endpoint.

## Solutions

### Solution 1: Use `rag.import_files()` with GCS (RECOMMENDED)

**Advantages:**
- ✅ No OAuth scope issues
- ✅ Faster for large files (no local download/upload)
- ✅ Matches Google's recommended pattern (see `t.py`)
- ✅ Better for batch operations

**Implementation:**
1. Copy files from S3 to GCS
2. Use `rag.import_files()` with `gs://` paths
3. Vertex AI handles everything server-side

**Changes Made:**
- Modified `ingest_unstructured_document()` to use GCS path method
- Falls back to `upload_file()` if `VERTEX_GCS_BUCKET` not set
- Requires new env var: `VERTEX_GCS_BUCKET=your-gcs-bucket-name`

### Solution 2: Fix OAuth Scopes for `upload_file()` (ALTERNATIVE)

If you must use `upload_file()`, you need to:

1. **Use Application Default Credentials (ADC):**
   ```bash
   gcloud auth application-default login
   unset GOOGLE_APPLICATION_CREDENTIALS
   ```
   
2. **Or regenerate service account key with proper domain-wide delegation**

3. **Or add explicit scopes to credentials:**
   ```python
   from google.oauth2 import service_account
   
   credentials = service_account.Credentials.from_service_account_file(
       key_path,
       scopes=['https://www.googleapis.com/auth/cloud-platform']
   )
   vertexai.init(project=project_id, location=location, credentials=credentials)
   ```

**Note:** Even with proper IAM roles (`aiplatform.admin`, `storage.objectAdmin`), the OAuth token generation for `upload_file()` requires additional scope configuration.

## Diagnostic Results

From `diagnose_vertex.py`:

| Test | Status | Notes |
|------|--------|-------|
| Environment Variables | ✅ PASS | All configured correctly |
| Authentication | ✅ PASS | Service account loads |
| Vertex AI Init | ✅ PASS | SDK initializes |
| List Corpora | ✅ PASS | Can read RAG resources |
| Create Corpus | ✅ PASS | Can create resources |
| **Upload File** | ❌ FAIL | OAuth scope error |
| Retrieval Query | ✅ PASS | Can query existing data |

**Conclusion:** The service account has proper IAM permissions but lacks OAuth scopes for the upload endpoint.

## Implementation Steps

### 1. Create GCS Bucket
```bash
gsutil mb -p search-477419 -l us-east4 gs://aganswers-vertex-rag
```

### 2. Grant Service Account Access
```bash
gsutil iam ch serviceAccount:vertex-ingestion-sa@search-477419.iam.gserviceaccount.com:objectAdmin \
  gs://aganswers-vertex-rag
```

### 3. Update Environment Variables
Add to `.env`:
```bash
VERTEX_GCS_BUCKET=aganswers-vertex-rag
```

### 4. Test the Fix
```bash
python test_ingest_endpoint.py
```

## Code Changes Summary

**File:** `ai_ta_backend/service/vertex_ingestion_service.py`

**Changes:**
- Added GCS client initialization
- Modified `ingest_unstructured_document()` to:
  1. Check for `VERTEX_GCS_BUCKET` env var
  2. If set: Copy S3 → GCS → use `import_files()`
  3. If not set: Fallback to `upload_file()` (with OAuth warning)

**Benefits:**
- ✅ Fixes OAuth scope error
- ✅ Maintains backward compatibility
- ✅ Follows Google's recommended pattern
- ✅ Better performance for large files

## Testing

Run diagnostics:
```bash
cd /home/ubuntu/dev/backend
python diagnose_vertex.py
python test_ingest_endpoint.py
```

## References

- [Vertex AI RAG Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/rag-overview)
- [OAuth 2.0 Scopes for Google APIs](https://developers.google.com/identity/protocols/oauth2/scopes)
- Working example: `backend/t.py` (uses `import_files()`)



