# Fix Vertex AI Authentication Error

## Error
```
google.auth.exceptions.RefreshError: invalid_scope: Invalid OAuth scope or ID token audience provided
```

## Root Cause
The service account doesn't have the correct API scopes enabled, or the Vertex AI API isn't fully enabled.

## Solution Steps

### 1. Enable Required APIs

```bash
# Set your project ID
export PROJECT_ID="search-477419"

# Enable all required APIs
gcloud services enable aiplatform.googleapis.com --project=$PROJECT_ID
gcloud services enable storage.googleapis.com --project=$PROJECT_ID
gcloud services enable storage-api.googleapis.com --project=$PROJECT_ID
gcloud services enable storage-component.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT_ID
```

### 2. Update Service Account Permissions

Your service account already has these roles (good!):
- ✅ Vertex AI Administrator
- ✅ Storage Object Admin

But you also need:

```bash
# Get your service account email from the JSON file
export SA_EMAIL=$(grep -oP '"client_email":\s*"\K[^"]+' /home/ubuntu/search-477419-2a6ecc3442d6.json)

echo "Service Account: $SA_EMAIL"

# Add additional required role for Vertex AI RAG
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.user"

# Ensure Cloud Storage permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.admin"
```

### 3. Verify API Enablement

```bash
# Check which APIs are enabled
gcloud services list --enabled --project=$PROJECT_ID | grep -E "(aiplatform|storage)"
```

You should see:
- aiplatform.googleapis.com
- storage.googleapis.com
- storage-api.googleapis.com

### 4. Test Authentication

```python
# Test in Python
from google.cloud import aiplatform
import vertexai

project_id = "search-477419"
location = "us-east4"

try:
    vertexai.init(project=project_id, location=location)
    print("✅ Vertex AI initialized successfully!")
    
    # Test listing corpora
    from vertexai import rag
    corpora = rag.list_corpora()
    print(f"✅ Can access RAG API. Found {len(list(corpora))} corpora.")
    
except Exception as e:
    print(f"❌ Error: {e}")
```

### 5. Update Environment Variables

Make sure your `.env` has:

```bash
GOOGLE_CLOUD_PROJECT_ID=search-477419
GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/search-477419-2a6ecc3442d6.json
VERTEX_AI_LOCATION=us-east4
```

### 6. Restart Backend

After making changes:

```bash
# In tmux session
Ctrl+C  # Stop backend
bpr     # Restart backend
```

## Alternative: Create New Service Account

If the above doesn't work, create a fresh service account with correct permissions:

```bash
export PROJECT_ID="search-477419"
export SA_NAME="vertex-rag-service"

# Create service account
gcloud iam service-accounts create $SA_NAME \
    --display-name="Vertex AI RAG Service Account" \
    --project=$PROJECT_ID

# Get the email
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant all required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.user"

# Create new key
gcloud iam service-accounts keys create ~/vertex-rag-new-key.json \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

# Upload to EC2 and update GOOGLE_APPLICATION_CREDENTIALS
```

## Common Issues

### Issue 1: APIs Not Enabled
**Symptoms:** `invalid_scope` error  
**Fix:** Run step 1 above

### Issue 2: Service Account Lacks Permissions
**Symptoms:** `Permission denied` or `invalid_scope`  
**Fix:** Run step 2 above

### Issue 3: Wrong Project ID
**Symptoms:** Project not found errors  
**Fix:** Verify `GOOGLE_CLOUD_PROJECT_ID=search-477419` in your .env

### Issue 4: Key File Not Found
**Symptoms:** `FileNotFoundError`  
**Fix:** Verify path in `GOOGLE_APPLICATION_CREDENTIALS`

## Verify Everything Works

```bash
# In backend Python environment
cd /home/ubuntu/backend
source backend/bin/activate

python3 << 'EOF'
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/ubuntu/search-477419-2a6ecc3442d6.json'
os.environ['GOOGLE_CLOUD_PROJECT_ID'] = 'search-477419'

from google.cloud import aiplatform
import vertexai
from vertexai import rag

vertexai.init(project='search-477419', location='us-east4')

# Try to list corpora
try:
    corpora = list(rag.list_corpora())
    print(f"✅ SUCCESS! Found {len(corpora)} corpora")
    for corpus in corpora:
        print(f"  - {corpus.display_name}")
except Exception as e:
    print(f"❌ Error: {e}")
EOF
```

If this works, your authentication is fixed and ingestion should work!

