#!/usr/bin/env python3
"""
Test script for /ingest endpoint
Tests the full ingestion flow via HTTP
"""

import os
import sys
import json
import requests
import tempfile
import dotenv
from pathlib import Path

dotenv.load_dotenv()

# Configuration
BASE_URL = os.getenv('BACKEND_URL', 'http://localhost:8002')
INGEST_ENDPOINT = f'{BASE_URL}/ingest'

def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def upload_test_file_to_s3():
    """Upload a test file to S3 and return its path"""
    print_section("1. Uploading Test File to S3")
    
    try:
        import boto3
        
        bucket_name = os.getenv('AGANSWERS_S3_BUCKET_NAME') or os.getenv('S3_BUCKET_NAME')
        if not bucket_name:
            print("❌ S3 bucket name not configured")
            return None
        
        s3_client = boto3.client('s3')
        
        # Create a test file
        test_content = """
# Test Document for Vertex AI RAG

This is a test document to verify the ingestion pipeline.

## About RAG

RAG stands for Retrieval-Augmented Generation. It's a technique that combines:
- Document retrieval from a knowledge base
- Large language model generation
- Context-aware responses

## Key Benefits

1. Accurate information retrieval
2. Reduced hallucinations
3. Grounded responses in actual documents
4. Scalable knowledge management

This document is used for testing the Vertex AI ingestion service.
"""
        
        # Upload to S3
        test_filename = f"test-document-{os.getpid()}.txt"
        s3_path = f"courses/test/{test_filename}"
        
        print(f"Uploading to s3://{bucket_name}/{s3_path}")
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_path,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        
        print(f"✅ Successfully uploaded test file")
        print(f"   S3 Path: {s3_path}")
        
        return s3_path
        
    except Exception as e:
        print(f"❌ Failed to upload test file: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_ingest_endpoint(s3_path: str, readable_filename: str):
    """Test the /ingest endpoint"""
    print_section("2. Testing /ingest Endpoint")
    
    payload = {
        'course_name': 'test',
        's3_path': s3_path,
        'readable_filename': readable_filename
    }
    
    print(f"POST {INGEST_ENDPOINT}")
    print(f"Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            INGEST_ENDPOINT,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=120  # 2 minute timeout
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text)
        
        if response.status_code == 200:
            print("\n✅ Ingestion successful!")
            return True, response_json
        else:
            print(f"\n❌ Ingestion failed with status {response.status_code}")
            return False, None
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out after 120 seconds")
        return False, None
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def verify_in_database(readable_filename: str):
    """Verify the document was stored in Supabase"""
    print_section("3. Verifying Database Storage")
    
    try:
        from supabase import create_client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_API_KEY')
        
        if not supabase_url or not supabase_key:
            print("⚠️  Supabase credentials not configured, skipping verification")
            return False
        
        supabase = create_client(supabase_url, supabase_key)
        
        print(f"Querying documents table for: {readable_filename}")
        
        result = supabase.table('documents').select('*').eq(
            'readable_filename', readable_filename
        ).execute()
        
        if result.data:
            print(f"✅ Found {len(result.data)} document(s) in database")
            for doc in result.data:
                print(f"\n   Document ID: {doc.get('id')}")
                print(f"   Course: {doc.get('course_name')}")
                print(f"   File Type: {doc.get('file_type')}")
                print(f"   Summary: {doc.get('summary', 'N/A')[:100]}...")
                print(f"   Keywords: {doc.get('keywords', [])}")
                print(f"   Vertex Corpus ID: {doc.get('vertex_corpus_id', 'N/A')}")
                print(f"   Vertex Document ID: {doc.get('vertex_document_id', 'N/A')}")
            return True
        else:
            print("❌ Document not found in database")
            return False
            
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_s3(s3_path: str):
    """Clean up test file from S3"""
    print_section("4. Cleanup")
    
    try:
        import boto3
        
        bucket_name = os.getenv('AGANSWERS_S3_BUCKET_NAME') or os.getenv('S3_BUCKET_NAME')
        if not bucket_name:
            return
        
        s3_client = boto3.client('s3')
        
        print(f"Deleting s3://{bucket_name}/{s3_path}")
        s3_client.delete_object(Bucket=bucket_name, Key=s3_path)
        
        print("✅ Test file cleaned up")
        
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")

def test_with_existing_file():
    """Test with an existing file from the error log"""
    print_section("Testing with Existing File from Error Log")
    
    s3_path = "courses/test/2109542b-db7b-4d2e-bbc8-397807c2d739-img-5419.html"
    readable_filename = "DigiDocs - IMG_5419.html"
    
    success, response = test_ingest_endpoint(s3_path, readable_filename)
    
    if success:
        verify_in_database(readable_filename)
    
    return success

def main():
    """Run ingestion endpoint tests"""
    print("\n" + "="*70)
    print("  INGESTION ENDPOINT TEST")
    print("="*70)
    
    # Check if backend is running
    print(f"\nChecking if backend is running at {BASE_URL}...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is running (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Backend is not accessible: {e}")
        print(f"   Make sure the backend is running at {BASE_URL}")
        return 1
    
    # Test with existing file from error log
    print("\n" + "="*70)
    print("  TEST 1: Existing File (from error log)")
    print("="*70)
    
    success1 = test_with_existing_file()
    
    # Test with new file
    print("\n" + "="*70)
    print("  TEST 2: New Test File")
    print("="*70)
    
    s3_path = upload_test_file_to_s3()
    
    if s3_path:
        readable_filename = Path(s3_path).name
        success2, response = test_ingest_endpoint(s3_path, readable_filename)
        
        if success2:
            verify_in_database(readable_filename)
        
        # Cleanup
        cleanup_s3(s3_path)
    else:
        success2 = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    print(f"Test 1 (Existing File): {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Test 2 (New File): {'✅ PASS' if success2 else '❌ FAIL'}")
    
    if success1 or success2:
        print("\n✅ At least one test passed")
        return 0
    else:
        print("\n❌ All tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())



