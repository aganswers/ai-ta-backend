#!/usr/bin/env python3
"""
Test GCS import method for Vertex AI RAG
This tests the solution to the OAuth scope issue
"""

import os
import sys
import dotenv
import tempfile
from pathlib import Path

dotenv.load_dotenv()

def test_gcs_import():
    """Test importing files from GCS to Vertex AI RAG"""
    print("="*70)
    print("  TEST: GCS Import Method (Solution to OAuth Issue)")
    print("="*70)
    
    try:
        from vertexai import rag
        from google.cloud import storage
        import vertexai
        
        # Initialize
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        gcs_bucket = os.getenv('VERTEX_GCS_BUCKET')
        
        if not gcs_bucket:
            print("\n❌ VERTEX_GCS_BUCKET not set")
            print("   Please set it to your GCS bucket name")
            print("   Example: export VERTEX_GCS_BUCKET=aganswers-vertex-rag")
            return False
        
        print(f"\n📋 Configuration:")
        print(f"   Project: {project_id}")
        print(f"   Location: {location}")
        print(f"   GCS Bucket: {gcs_bucket}")
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        print("\n✅ Vertex AI initialized")
        
        # Get or create test corpus
        print("\n📦 Getting test corpus...")
        corpora = list(rag.list_corpora())
        if corpora:
            corpus = corpora[0]
            print(f"✅ Using existing corpus: {corpus.display_name}")
        else:
            corpus = rag.create_corpus(
                display_name="test-gcs-import",
                description="Test corpus for GCS import method"
            )
            print(f"✅ Created new corpus: {corpus.display_name}")
        
        # Create a test file
        print("\n📄 Creating test file...")
        test_content = """
# Test Document for GCS Import

This document tests the GCS import method for Vertex AI RAG.

## Why GCS Import?

The GCS import method (rag.import_files) avoids OAuth scope issues that occur
with the local file upload method (rag.upload_file).

## How it works

1. Files are copied from S3 to GCS
2. Vertex AI imports directly from GCS using gs:// paths
3. No OAuth scope issues because it's server-to-server

## Benefits

- Faster for large files
- No OAuth scope configuration needed
- Follows Google's recommended pattern
- Better for batch operations
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            temp_path = f.name
        
        print(f"✅ Created temporary file: {temp_path}")
        
        # Upload to GCS
        print(f"\n☁️  Uploading to GCS...")
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(gcs_bucket)
        
        gcs_path = f"test/gcs-import-test-{os.getpid()}.txt"
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(temp_path)
        
        print(f"✅ Uploaded to gs://{gcs_bucket}/{gcs_path}")
        
        # Clean up local file
        os.unlink(temp_path)
        
        # Import from GCS to Vertex AI RAG
        print(f"\n🚀 Importing to Vertex AI RAG using import_files()...")
        rag.import_files(
            corpus.name,
            [f"gs://{gcs_bucket}/{gcs_path}"],
            transformation_config=rag.TransformationConfig(
                chunking_config=rag.ChunkingConfig(
                    chunk_size=512,
                    chunk_overlap=100,
                ),
            ),
        )
        
        print(f"✅ Successfully imported file using GCS method!")
        print(f"   This method avoids the OAuth scope error!")
        
        # Verify by listing files
        print(f"\n📋 Verifying import...")
        files = rag.list_files(corpus_name=corpus.name)
        file_count = len(list(files))
        print(f"✅ Corpus now has {file_count} file(s)")
        
        # Test retrieval
        print(f"\n🔍 Testing retrieval...")
        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=corpus.name)],
            text="What is GCS import and why use it?",
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
        )
        
        if response:
            print(f"✅ Retrieval successful!")
            print(f"   Response: {str(response)[:200]}...")
        
        print(f"\n{'='*70}")
        print(f"  ✅ GCS IMPORT METHOD WORKS!")
        print(f"  This is the solution to the OAuth scope issue.")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    print("\n" + "="*70)
    print("  GCS IMPORT METHOD TEST")
    print("  Solution to: OAuth scope error with rag.upload_file()")
    print("="*70)
    
    success = test_gcs_import()
    
    if success:
        print("\n✅ SUCCESS! The GCS import method works.")
        print("\nNext steps:")
        print("1. Set VERTEX_GCS_BUCKET in your .env file")
        print("2. Restart your backend server")
        print("3. Test the /ingest endpoint")
        return 0
    else:
        print("\n❌ Test failed. Check the error messages above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())



