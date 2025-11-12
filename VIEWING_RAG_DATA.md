# How to View Vertex AI RAG Data in GCP

## Quick Answer

Your RAG corpora are stored in **Vertex AI Agent Builder** (formerly called Vertex AI Search).

## 🌐 Web Console (Easiest)

### Option 1: Direct Link
Go to: **https://console.cloud.google.com/gen-app-builder/engines?project=search-477419**

### Option 2: Navigate Manually
1. Go to: https://console.cloud.google.com/
2. Select project: `search-477419`
3. In the search bar, type: **"Agent Builder"** or **"Vertex AI Search"**
4. Click on **"Agent Builder"**
5. Look for **"Data Stores"** or **"Apps"** in the left sidebar

### Option 3: Through Vertex AI
1. Go to: https://console.cloud.google.com/vertex-ai?project=search-477419
2. In the left sidebar, find **"Vertex AI Search and Conversation"**
3. Click on **"Data Stores"**

## 🖥️ Command Line (gcloud)

```bash
# List Vertex AI resources
gcloud ai indexes list --region=us-east4 --project=search-477419

# View project resources
gcloud projects describe search-477419
```

## 🐍 Python Script (Most Detailed)

Use the provided script:

```bash
cd /home/ubuntu/dev/backend

# View all corpora and files
python view_rag_data.py

# Show statistics only
python view_rag_data.py stats

# Search across all corpora
python view_rag_data.py search "What is RAG?"
```

## 📊 What You'll See

Based on your diagnostic output, you have **3 corpora**:

1. **aganswers-documents-test**
   - ID: `projects/search-477419/locations/us-east4/ragCorpora/2305843009213693952`
   
2. **aganswers-documents** (corpus 1)
   - ID: `projects/search-477419/locations/us-east4/ragCorpora/4611686018427387904`
   
3. **aganswers-documents** (corpus 2)
   - ID: `projects/search-477419/locations/us-east4/ragCorpora/1152921504606846976`

## 🔍 Viewing GCS Files

If using the GCS import method, you can also view the source files:

```bash
# List files in your GCS bucket
gsutil ls gs://aganswers-search-dev/

# View specific directory
gsutil ls gs://aganswers-search-dev/vertex-rag/

# Get details about a file
gsutil ls -l gs://aganswers-search-dev/vertex-rag/test/
```

## 📱 GCP Console Navigation Path

```
Google Cloud Console
  └─ Select Project: search-477419
      └─ Navigation Menu (☰)
          └─ Artificial Intelligence
              └─ Vertex AI
                  └─ Agent Builder (or "Vertex AI Search and Conversation")
                      └─ Data Stores
                          └─ [Your Corpora Listed Here]
```

## 🔗 Quick Links

| Resource | URL |
|----------|-----|
| **Vertex AI Dashboard** | https://console.cloud.google.com/vertex-ai?project=search-477419 |
| **Agent Builder** | https://console.cloud.google.com/gen-app-builder/engines?project=search-477419 |
| **Cloud Storage (GCS)** | https://console.cloud.google.com/storage/browser?project=search-477419 |
| **IAM & Admin** | https://console.cloud.google.com/iam-admin/iam?project=search-477419 |
| **API Dashboard** | https://console.cloud.google.com/apis/dashboard?project=search-477419 |

## 💡 Pro Tips

1. **Can't find Agent Builder?**
   - Make sure you're in the correct project (`search-477419`)
   - Try searching for "Vertex AI Search" in the console search bar
   - The UI changes frequently; it might be under different names

2. **Empty corpus?**
   - The upload_file() method is failing due to OAuth scopes
   - Use the GCS import method instead (see VERTEX_OAUTH_ISSUE_SOLUTION.md)
   - Or check if files are still processing (can take a few minutes)

3. **Want to see file contents?**
   - Files are chunked and embedded by Vertex AI
   - You can't see the raw file, but you can:
     - Query the corpus to see retrieved chunks
     - View the original files in GCS
     - Use the view_rag_data.py script to search

## 🧪 Testing Your Data

```python
# Quick test in Python
from vertexai import rag
import vertexai

vertexai.init(project='search-477419', location='us-east4')

# List corpora
for corpus in rag.list_corpora():
    print(f"Corpus: {corpus.display_name}")
    
    # List files in corpus
    for file in rag.list_files(corpus_name=corpus.name):
        print(f"  - {file.display_name}")
    
    # Test search
    response = rag.retrieval_query(
        rag_resources=[rag.RagResource(rag_corpus=corpus.name)],
        text="test query",
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
    )
    print(f"  Search results: {response}")
```

## 🆘 Troubleshooting

**"I don't see any data"**
- Run: `python view_rag_data.py` to check if files are actually uploaded
- Check if the upload succeeded (look for OAuth errors in logs)
- Files might still be processing (wait a few minutes)

**"Access Denied"**
- Make sure you're logged in with the correct Google account
- Verify your service account has proper IAM roles
- Check: https://console.cloud.google.com/iam-admin/iam?project=search-477419

**"Can't find Agent Builder"**
- It might be called "Vertex AI Search" or "Vertex AI Search and Conversation"
- Try the direct link: https://console.cloud.google.com/gen-app-builder
- Make sure the Vertex AI API is enabled



