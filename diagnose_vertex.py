#!/usr/bin/env python3
"""
Vertex AI RAG Diagnostics Script
Tests authentication, permissions, and RAG operations step-by-step
"""

import os
import sys
import traceback
import dotenv
from pathlib import Path

dotenv.load_dotenv()

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def check_env_vars():
    """Check required environment variables"""
    print_section("1. Environment Variables Check")
    
    required_vars = {
        'GOOGLE_CLOUD_PROJECT_ID': os.getenv('GOOGLE_CLOUD_PROJECT_ID'),
        'GOOGLE_APPLICATION_CREDENTIALS': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
        'VERTEX_AI_LOCATION': os.getenv('VERTEX_AI_LOCATION', 'us-east4'),
        'VERTEX_RAG_CORPUS_NAME': os.getenv('VERTEX_RAG_CORPUS_NAME'),
        'VERTEX_TEXT_MODEL': os.getenv('VERTEX_TEXT_MODEL'),
    }
    
    all_present = True
    for var, value in required_vars.items():
        status = "✅" if value else "❌"
        print(f"{status} {var}: {value or 'NOT SET'}")
        if not value and var in ['GOOGLE_CLOUD_PROJECT_ID', 'GOOGLE_APPLICATION_CREDENTIALS']:
            all_present = False
    
    # Check if credentials file exists
    creds_path = required_vars['GOOGLE_APPLICATION_CREDENTIALS']
    if creds_path:
        if Path(creds_path).exists():
            print(f"✅ Credentials file exists: {creds_path}")
        else:
            print(f"❌ Credentials file NOT FOUND: {creds_path}")
            all_present = False
    
    return all_present

def check_gcloud_auth():
    """Check gcloud authentication"""
    print_section("2. Google Cloud Authentication Check")
    
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        
        credentials, project = default()
        print(f"✅ Default credentials loaded")
        print(f"   Project: {project}")
        print(f"   Credentials type: {type(credentials).__name__}")
        
        # Try to refresh credentials
        if hasattr(credentials, 'expired') and credentials.expired:
            print("   Credentials expired, refreshing...")
            credentials.refresh(Request())
            print("✅ Credentials refreshed successfully")
        
        # Check scopes
        if hasattr(credentials, 'scopes'):
            print(f"   Scopes: {credentials.scopes}")
        elif hasattr(credentials, '_scopes'):
            print(f"   Scopes: {credentials._scopes}")
        else:
            print("⚠️  Cannot determine credential scopes")
        
        return True, credentials
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        traceback.print_exc()
        return False, None

def check_vertex_init():
    """Check Vertex AI initialization"""
    print_section("3. Vertex AI Initialization Check")
    
    try:
        import vertexai
        from google.cloud import aiplatform
        
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        
        print(f"Initializing Vertex AI...")
        print(f"   Project: {project_id}")
        print(f"   Location: {location}")
        
        vertexai.init(project=project_id, location=location)
        aiplatform.init(project=project_id, location=location)
        
        print("✅ Vertex AI initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Vertex AI initialization failed: {e}")
        traceback.print_exc()
        return False

def check_rag_permissions():
    """Check RAG-specific permissions by listing corpora"""
    print_section("4. RAG Permissions Check (List Corpora)")
    
    try:
        from vertexai import rag
        
        print("Attempting to list RAG corpora...")
        corpora = rag.list_corpora()
        
        print(f"✅ Successfully listed corpora")
        corpus_list = list(corpora)
        print(f"   Found {len(corpus_list)} corpora:")
        
        for corpus in corpus_list:
            print(f"   - {corpus.display_name} ({corpus.name})")
        
        return True, corpus_list
        
    except Exception as e:
        print(f"❌ Failed to list corpora: {e}")
        print(f"   Error type: {type(e).__name__}")
        traceback.print_exc()
        return False, []

def test_corpus_creation():
    """Test creating a RAG corpus"""
    print_section("5. Test Corpus Creation")
    
    try:
        from vertexai import rag
        
        test_corpus_name = f"test-diagnostic-corpus-{os.getpid()}"
        print(f"Creating test corpus: {test_corpus_name}")
        
        corpus = rag.create_corpus(
            display_name=test_corpus_name,
            description="Diagnostic test corpus - safe to delete"
        )
        
        print(f"✅ Successfully created corpus: {corpus.name}")
        
        # Try to delete it
        print(f"Cleaning up test corpus...")
        rag.delete_corpus(name=corpus.name)
        print(f"✅ Successfully deleted test corpus")
        
        return True
        
    except Exception as e:
        print(f"❌ Corpus creation/deletion failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_file_upload():
    """Test uploading a file to RAG"""
    print_section("6. Test File Upload to RAG")
    
    try:
        from vertexai import rag
        import tempfile
        
        # Get or create a test corpus
        print("Getting existing corpus or creating new one...")
        corpora = list(rag.list_corpora())
        
        if corpora:
            corpus = corpora[0]
            print(f"Using existing corpus: {corpus.display_name}")
        else:
            print("No corpora found, creating test corpus...")
            corpus = rag.create_corpus(
                display_name=f"test-upload-corpus-{os.getpid()}",
                description="Test corpus for file upload"
            )
            print(f"Created corpus: {corpus.name}")
        
        # Create a temporary test file
        print("Creating temporary test file...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test document for Vertex AI RAG diagnostics.\n")
            f.write("It contains sample text to verify file upload functionality.\n")
            f.write("RAG stands for Retrieval-Augmented Generation.\n")
            temp_path = f.name
        
        print(f"Temporary file: {temp_path}")
        
        # Try to upload the file
        print(f"Uploading file to corpus {corpus.name}...")
        rag_file = rag.upload_file(
            corpus_name=corpus.name,
            path=temp_path,
            display_name="diagnostic-test-file.txt",
            description="Diagnostic test file"
        )
        
        print(f"✅ Successfully uploaded file: {rag_file.name}")
        
        # Clean up
        print("Cleaning up temporary file...")
        os.unlink(temp_path)
        
        return True, rag_file
        
    except Exception as e:
        print(f"❌ File upload failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Check for specific OAuth errors
        if 'invalid_scope' in str(e).lower():
            print("\n⚠️  OAUTH SCOPE ERROR DETECTED!")
            print("   This indicates the service account credentials are missing required scopes.")
            print("   Required scopes for Vertex AI RAG:")
            print("   - https://www.googleapis.com/auth/cloud-platform")
            print("   - https://www.googleapis.com/auth/aiplatform")
            print("\n   To fix:")
            print("   1. Regenerate service account key with proper scopes")
            print("   2. Or use: gcloud auth application-default login")
        
        traceback.print_exc()
        
        # Clean up temp file if it exists
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
        except:
            pass
        
        return False, None

def test_retrieval():
    """Test RAG retrieval"""
    print_section("7. Test RAG Retrieval")
    
    try:
        from vertexai import rag
        
        # Get a corpus with files
        corpora = list(rag.list_corpora())
        if not corpora:
            print("⚠️  No corpora available for retrieval test")
            return False
        
        corpus = corpora[0]
        print(f"Testing retrieval from corpus: {corpus.display_name}")
        
        # Try a simple retrieval query
        response = rag.retrieval_query(
            rag_resources=[
                rag.RagResource(rag_corpus=corpus.name)
            ],
            text="What is RAG?",
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
        )
        
        print(f"✅ Successfully performed retrieval query")
        print(f"   Response: {response}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Retrieval test failed: {e}")
        print(f"   (This may be expected if no documents are uploaded yet)")
        return False

def main():
    """Run all diagnostic checks"""
    print("\n" + "="*70)
    print("  VERTEX AI RAG DIAGNOSTICS")
    print("="*70)
    
    results = {}
    
    # Run checks in sequence
    results['env_vars'] = check_env_vars()
    
    if not results['env_vars']:
        print("\n❌ Environment variables check failed. Cannot proceed.")
        sys.exit(1)
    
    results['auth'], credentials = check_gcloud_auth()
    
    if not results['auth']:
        print("\n❌ Authentication failed. Cannot proceed.")
        sys.exit(1)
    
    results['vertex_init'] = check_vertex_init()
    
    if not results['vertex_init']:
        print("\n❌ Vertex AI initialization failed. Cannot proceed.")
        sys.exit(1)
    
    results['rag_list'], corpora = check_rag_permissions()
    results['corpus_create'] = test_corpus_creation()
    results['file_upload'], rag_file = test_file_upload()
    results['retrieval'] = test_retrieval()
    
    # Summary
    print_section("DIAGNOSTIC SUMMARY")
    
    for check, passed in results.items():
        if isinstance(passed, bool):
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {check}")
    
    all_passed = all(v for v in results.values() if isinstance(v, bool))
    
    if all_passed:
        print("\n🎉 All diagnostics passed! Vertex AI RAG is working correctly.")
        return 0
    else:
        print("\n⚠️  Some diagnostics failed. Review the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())



