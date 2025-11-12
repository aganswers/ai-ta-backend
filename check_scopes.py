#!/usr/bin/env python3
"""
Check Google Cloud service account scopes and permissions
"""

import os
import json
import dotenv
from pathlib import Path

dotenv.load_dotenv()

def check_service_account_key():
    """Check the service account key file for scopes"""
    print("="*70)
    print("  SERVICE ACCOUNT KEY ANALYSIS")
    print("="*70)
    
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not creds_path:
        print("\n❌ GOOGLE_APPLICATION_CREDENTIALS not set")
        return False
    
    print(f"\n📄 Credentials file: {creds_path}")
    
    if not Path(creds_path).exists():
        print(f"❌ File does not exist!")
        return False
    
    print("✅ File exists")
    
    try:
        with open(creds_path, 'r') as f:
            key_data = json.load(f)
        
        print(f"\n📋 Service Account Details:")
        print(f"   Type: {key_data.get('type', 'N/A')}")
        print(f"   Project ID: {key_data.get('project_id', 'N/A')}")
        print(f"   Client Email: {key_data.get('client_email', 'N/A')}")
        print(f"   Private Key ID: {key_data.get('private_key_id', 'N/A')[:20]}...")
        
        # Check for scopes (they're not in the key file, but we can check the structure)
        if 'private_key' in key_data:
            print("   ✅ Private key present")
        else:
            print("   ❌ Private key missing!")
        
        # The scopes are not in the key file itself, they're determined by:
        # 1. The IAM roles assigned to the service account
        # 2. The scopes requested when using the credentials
        
        print(f"\n💡 Important Notes:")
        print(f"   - Service account scopes are determined by IAM roles")
        print(f"   - The key file itself doesn't contain scope information")
        print(f"   - Check IAM roles in Google Cloud Console")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in credentials file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading credentials: {e}")
        return False

def check_required_iam_roles():
    """Display required IAM roles for Vertex AI RAG"""
    print("\n" + "="*70)
    print("  REQUIRED IAM ROLES FOR VERTEX AI RAG")
    print("="*70)
    
    print("""
The service account needs these IAM roles:

1. ✅ Vertex AI User (roles/aiplatform.user)
   - Allows access to Vertex AI services
   - Required for: RAG corpus creation, file upload, retrieval

2. ✅ Storage Object Viewer (roles/storage.objectViewer)
   - Allows reading files from Cloud Storage
   - Required for: importing files from GCS

3. ✅ Service Account Token Creator (roles/iam.serviceAccountTokenCreator)
   - Allows creating OAuth tokens
   - Required for: proper authentication flow

To check/add roles in Google Cloud Console:
1. Go to: IAM & Admin > IAM
2. Find your service account: {client_email}
3. Click "Edit" (pencil icon)
4. Add the roles listed above
5. Save changes

Or use gcloud CLI:
    gcloud projects add-iam-policy-binding {project_id} \\
        --member="serviceAccount:{client_email}" \\
        --role="roles/aiplatform.user"
    
    gcloud projects add-iam-policy-binding {project_id} \\
        --member="serviceAccount:{client_email}" \\
        --role="roles/storage.objectViewer"
""")

def check_oauth_scopes():
    """Check what OAuth scopes are being used"""
    print("\n" + "="*70)
    print("  OAUTH SCOPES CHECK")
    print("="*70)
    
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        
        credentials, project = default()
        
        print(f"\n📋 Credentials Info:")
        print(f"   Type: {type(credentials).__name__}")
        print(f"   Project: {project}")
        
        # Try to get scopes
        scopes = None
        if hasattr(credentials, 'scopes'):
            scopes = credentials.scopes
        elif hasattr(credentials, '_scopes'):
            scopes = credentials._scopes
        elif hasattr(credentials, 'default_scopes'):
            scopes = credentials.default_scopes
        
        if scopes:
            print(f"\n✅ Current Scopes:")
            for scope in scopes:
                print(f"   - {scope}")
        else:
            print(f"\n⚠️  Cannot determine scopes (this is normal for service accounts)")
            print(f"   Service accounts have full access based on IAM roles")
        
        print(f"\n📋 Required Scopes for Vertex AI RAG:")
        required_scopes = [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/aiplatform",
        ]
        for scope in required_scopes:
            print(f"   - {scope}")
        
        # For service accounts, scopes are typically not restricted
        # The IAM roles determine what the account can do
        if isinstance(credentials, type(credentials)) and 'ServiceAccount' in type(credentials).__name__:
            print(f"\n💡 Service Account Credentials:")
            print(f"   - Scopes are not restricted in the credentials")
            print(f"   - Access is controlled by IAM roles")
            print(f"   - Make sure the service account has the required IAM roles")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check OAuth scopes: {e}")
        import traceback
        traceback.print_exc()
        return False

def suggest_fixes():
    """Suggest fixes for common OAuth scope issues"""
    print("\n" + "="*70)
    print("  SUGGESTED FIXES FOR OAUTH SCOPE ERRORS")
    print("="*70)
    
    print("""
If you're seeing "invalid_scope" errors, try these fixes:

1. 🔧 Regenerate Service Account Key
   - Go to: IAM & Admin > Service Accounts
   - Select your service account
   - Keys tab > Add Key > Create new key
   - Choose JSON format
   - Download and replace your current key file

2. 🔧 Use Application Default Credentials (ADC)
   Instead of a service account key, use:
   
   $ gcloud auth application-default login
   
   This will use your user credentials with full scopes.
   Then unset GOOGLE_APPLICATION_CREDENTIALS:
   
   $ unset GOOGLE_APPLICATION_CREDENTIALS

3. 🔧 Verify IAM Roles
   Make sure the service account has these roles:
   - Vertex AI User (roles/aiplatform.user)
   - Storage Object Viewer (roles/storage.objectViewer)

4. 🔧 Check API Enablement
   Make sure these APIs are enabled:
   - Vertex AI API
   - Cloud Storage API
   
   $ gcloud services enable aiplatform.googleapis.com
   $ gcloud services enable storage.googleapis.com

5. 🔧 Test with gcloud
   Verify your credentials work:
   
   $ gcloud auth list
   $ gcloud projects describe {project_id}
   $ gcloud ai indexes list --region=us-east4

6. 🔧 Use a Different Region
   Some regions may have different requirements.
   Try: us-central1, us-east1, or europe-west1
""")

def main():
    """Run all checks"""
    print("\n" + "="*70)
    print("  GOOGLE CLOUD CREDENTIALS & SCOPES CHECKER")
    print("="*70)
    
    check_service_account_key()
    check_oauth_scopes()
    check_required_iam_roles()
    suggest_fixes()
    
    print("\n" + "="*70)
    print("  NEXT STEPS")
    print("="*70)
    print("""
1. Run the diagnostics script:
   $ python diagnose_vertex.py

2. If diagnostics fail, apply the suggested fixes above

3. Test the ingestion endpoint:
   $ python test_ingest_endpoint.py

4. Check the backend logs for detailed error messages
""")

if __name__ == '__main__':
    main()



