# Vertex AI Setup Guide

## Overview
This guide explains how to set up Google Cloud Vertex AI for the spotlight search feature.

## Prerequisites
- Google Cloud Project with billing enabled
- Owner or Editor permissions on the project

## Step 1: Enable Required APIs

Run these commands using `gcloud` CLI or enable via Google Cloud Console:

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable generativelanguage.googleapis.com
```

Or via Cloud Console:
1. Go to https://console.cloud.google.com/apis/library
2. Search for and enable:
   - Vertex AI API
   - Cloud Storage API
   - Generative Language API

## Step 2: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create aganswers-vertex-ai \
    --display-name="AgAnswers Vertex AI Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:aganswers-vertex-ai@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:aganswers-vertex-ai@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Create and download key
gcloud iam service-accounts keys create ~/aganswers-vertex-key.json \
    --iam-account=aganswers-vertex-ai@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## Step 3: Set Environment Variables

Add these to your `.env` file or environment:

```bash
# Google Cloud Project Configuration
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/backend/aganswers-vertex-key.json
VERTEX_AI_LOCATION=us-central1

# Vertex AI RAG Configuration
VERTEX_RAG_CORPUS_NAME=aganswers-documents
VERTEX_EMBEDDING_MODEL=text-embedding-005
VERTEX_TEXT_MODEL=gemini-2.0-flash-exp
```

## Step 4: Upload Service Account Key to EC2

```bash
# From your local machine, upload the key to EC2
scp ~/aganswers-vertex-key.json ubuntu@your-ec2-instance:/home/ubuntu/backend/

# SSH into EC2 and secure the key
ssh ubuntu@your-ec2-instance
chmod 600 /home/ubuntu/backend/aganswers-vertex-key.json
```

## Step 5: Verify Setup

Test that authentication works:

```python
from google.cloud import aiplatform

aiplatform.init(
    project="your-project-id",
    location="us-central1"
)

print("Vertex AI initialized successfully!")
```

## Recommended Configuration

### Embedding Model
- **Model**: `gemini-embedding-001`
- **Dimensions**: 3072 (4x richer than standard models!)
- **Best for**: High-quality multilingual semantic search, document retrieval
- **Cost**: $0.00001 per 1K characters

### Text Generation Model  
- **Model**: `gemini-2.5-flash-lite`
- **Best for**: Fast, cost-effective metadata extraction (summaries, keywords)
- **Cost**: Very low cost for short generations

### Corpus Settings
- **Corpus Name**: `aganswers-documents`
- **Chunk Size**: 1024 tokens (Vertex auto-chunks)
- **Chunk Overlap**: 200 tokens
- **Distance Strategy**: COSINE

## Security Notes

1. **Never commit** `aganswers-vertex-key.json` to git
2. Add to `.gitignore`:
   ```
   aganswers-vertex-key.json
   *-vertex-key.json
   ```
3. Rotate service account keys every 90 days
4. Use least-privilege IAM permissions in production

## Troubleshooting

### Authentication Errors
```bash
# Verify credentials are valid
gcloud auth application-default print-access-token

# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:aganswers-vertex-ai@*"
```

### API Not Enabled
If you see "API not enabled" errors, double-check Step 1.

### Quota Issues
Check quotas at: https://console.cloud.google.com/iam-admin/quotas

For higher limits, request quota increases via the Cloud Console.

## Cost Estimation

Based on 1000 documents/month:
- Embedding: ~$0.10/month (10 pages per doc avg)
- Text generation: ~$0.05/month (metadata extraction)
- Storage in Vertex: ~$0.02/month

**Total estimated cost: ~$0.20/month per 1000 documents**

