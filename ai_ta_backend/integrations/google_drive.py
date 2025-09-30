"""
Google Drive integration service.
Handles OAuth, file listing, selection, and sync operations.
"""

import io
import os
import tempfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from flask import Blueprint, jsonify, redirect, request

from ..database.aws import AWSStorage
from ..database.sql import SQLDatabase
from .utils import (
    decrypt_token,
    encrypt_token,
    expires_in,
    get_user_email_from_request,
    retryable_request,
    should_refresh_token,
    utcnow,
    validate_course_access,
)

# Create blueprint
drive_bp = Blueprint('drive_integrations', __name__, url_prefix='/integrations')

# Google Drive API configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
GOOGLE_SCOPES = 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.metadata.readonly'

# Beam ingest configuration
BEAM_INGEST_URL = os.environ.get('BEAM_INGEST_URL', 'https://aganswers-demo-task-queue-1bf6066.app.beam.cloud')
BEAM_API_KEY = os.environ.get('BEAM_API_KEY')
MAX_FILE_SIZE_MB = int(os.environ.get('MAX_DRIVE_FILE_SIZE_MB', '40'))
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME') or os.environ.get('AGANSWERS_S3_BUCKET_NAME', 'aganswers')


class GoogleDriveService:
    """Service class for Google Drive operations."""
    
    def __init__(self, sql_db: SQLDatabase, aws_storage: AWSStorage = None):
        self.sql_db = sql_db
        self.supabase = sql_db.supabase_client
        self.aws_storage = aws_storage or AWSStorage()

    def get_auth_url(self) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'scope': GOOGLE_SCOPES,
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{requests.compat.urlencode(params)}"

    def handle_oauth_callback(self, code: str, user_email: str) -> bool:
        """Handle OAuth callback and store temporary tokens."""
        try:
            print(f"🔧 OAuth callback - code: {code[:20]}..., user_email: {user_email}")
            # Exchange code for tokens
            token_data = {
                'code': code,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'redirect_uri': GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            if response.status_code != 200:
                print(f"❌ Token exchange failed: {response.status_code}, {response.text}")
                return False
                
            tokens = response.json()
            print(f"✅ Token exchange successful, expires_in: {tokens.get('expires_in')}")
            
            # Get user info
            user_info_response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f"Bearer {tokens['access_token']}"}
            )
            
            if user_info_response.status_code != 200:
                print(f"❌ User info failed: {user_info_response.status_code}, response: {user_info_response.text}")
                # For development, let's continue without user info and use a default email
                user_info = {'email': f'google_user_{user_email}@drive.local'}
                print(f"🔧 Using fallback user info: {user_info}")
            else:
                user_info = user_info_response.json()
                print(f"✅ User info retrieved: {user_info.get('email')}")
            
            # Store temporary tokens
            token_payload = {
                'access_token': tokens['access_token'],
                'refresh_token': tokens.get('refresh_token'),
                'token_expires_at': expires_in(tokens.get('expires_in', 3600)).isoformat(),
                'account_email': user_info.get('email')
            }
            
            self.supabase.table('user_temp_drive_tokens').upsert({
                'user_email': user_email,
                'provider': 'google_drive',
                'token_blob': encrypt_token(token_payload),
                'updated_at': utcnow().isoformat()
            }).execute()
            
            print(f"✅ OAuth callback successful for {user_info.get('email')}")
            return True
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return False

    def connect_to_course(self, course_name: str, user_email: str) -> Dict:
        """Connect Google Drive integration to a course."""
        try:
            print(f"🔧 Connect to course - course_name: {course_name}, user_email: {user_email}")
            # Validate course access
            if not validate_course_access(course_name, user_email, self.supabase):
                print(f"❌ Access denied to course: {course_name}")
                return {'error': 'Access denied to course'}
            
            # Get temp tokens
            temp_tokens = self.supabase.table('user_temp_drive_tokens')\
                .select('token_blob')\
                .eq('user_email', user_email)\
                .eq('provider', 'google_drive')\
                .single().execute()
            
            if not temp_tokens.data:
                print(f"❌ No temporary tokens found for user: {user_email}")
                return {'error': 'No temporary tokens found. Please authenticate first.'}
            
            tokens = decrypt_token(temp_tokens.data['token_blob'])
            
            # First, let's find the project_id for this course
            project_result = self.supabase.table('projects').select('id').eq('course_name', course_name).execute()
            if not project_result.data:
                return {'error': f'Course {course_name} not found'}
            
            project_id = project_result.data[0]['id']
            
            # Store in project integrations
            integration_data = {
                'project_id': project_id,
                'provider': 'google_drive',
                'external_account_email': tokens['account_email'],
                'access_token': encrypt_token({'token': tokens['access_token']}),
                'refresh_token': encrypt_token({'token': tokens.get('refresh_token')}),
                'token_expires_at': tokens['token_expires_at'],
                'scope': GOOGLE_SCOPES,
                'granted_by_user_id': user_email,
                'updated_at': utcnow().isoformat()
            }
            
            # Add course_name if the column exists
            try:
                # Try to add course_name - this will work if the column exists
                integration_data['course_name'] = course_name
                self.supabase.table('project_integrations').upsert(integration_data).execute()
            except Exception as e:
                # If that fails, try without course_name
                print(f"Warning: course_name column might not exist: {e}")
                integration_data.pop('course_name', None)
                self.supabase.table('project_integrations').upsert(integration_data).execute()
            
            # Clean up temp tokens
            self.supabase.table('user_temp_drive_tokens')\
                .delete()\
                .eq('user_email', user_email)\
                .eq('provider', 'google_drive')\
                .execute()
            
            return {'success': True, 'account_email': tokens['account_email']}
            
        except Exception as e:
            print(f"Connect to course error: {e}")
            return {'error': str(e)}

    def get_project_tokens(self, course_name: str) -> Optional[Dict]:
        """Get and refresh project tokens if needed."""
        try:
            integration = self.supabase.table('project_integrations')\
                .select('*')\
                .eq('course_name', course_name)\
                .eq('provider', 'google_drive')\
                .single().execute()
            
            if not integration.data:
                return None
            
            data = integration.data
            access_token = decrypt_token(data['access_token'])['token']
            refresh_token = decrypt_token(data['refresh_token'])['token'] if data['refresh_token'] else None
            
            # Check if token needs refresh
            expires_at = datetime.fromisoformat(data['token_expires_at'].replace('Z', '+00:00')) if data['token_expires_at'] else None
            
            if should_refresh_token(expires_at) and refresh_token:
                # Refresh token
                refresh_data = {
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'refresh_token': refresh_token,
                    'grant_type': 'refresh_token'
                }
                
                response = requests.post('https://oauth2.googleapis.com/token', data=refresh_data)
                if response.status_code == 200:
                    new_tokens = response.json()
                    access_token = new_tokens['access_token']
                    
                    # Update stored tokens
                    self.supabase.table('project_integrations').update({
                        'access_token': encrypt_token({'token': access_token}),
                        'token_expires_at': expires_in(new_tokens.get('expires_in', 3600)).isoformat(),
                        'updated_at': utcnow().isoformat()
                    }).eq('id', data['id']).execute()
            
            return {
                'integration_id': data['id'],
                'access_token': access_token,
                'account_email': data['external_account_email']
            }
            
        except Exception as e:
            print(f"Get project tokens error: {e}")
            return None

    def list_files(self, course_name: str, folder_id: str = 'root') -> Dict:
        """List files in Google Drive folder."""
        try:
            tokens = self.get_project_tokens(course_name)
            if not tokens:
                return {'error': 'Integration not found or expired'}
            
            # Build query
            query = f"'{folder_id}' in parents and trashed=false"
            url = (
                f"https://www.googleapis.com/drive/v3/files"
                f"?q={requests.utils.quote(query)}"
                f"&fields=files(id,name,mimeType,modifiedTime,md5Checksum,size)"
                f"&includeItemsFromAllDrives=true&supportsAllDrives=true"
            )
            
            def make_request():
                return requests.get(url, headers={'Authorization': f"Bearer {tokens['access_token']}"})
            
            response = retryable_request(make_request)
            
            if response.status_code != 200:
                return {'error': f'Failed to list files: {response.status_code}'}
            
            files_data = response.json().get('files', [])
            files = []
            
            for file_data in files_data:
                files.append({
                    'id': file_data['id'],
                    'name': file_data['name'],
                    'isFolder': file_data.get('mimeType', '').endswith('folder'),
                    'mimeType': file_data.get('mimeType'),
                    'modifiedTime': file_data.get('modifiedTime'),
                    'size': file_data.get('size'),
                    'md5Checksum': file_data.get('md5Checksum')
                })
            
            return {'files': files}
            
        except Exception as e:
            print(f"List files error: {e}")
            return {'error': str(e)}

    def save_selections(self, course_name: str, user_email: str, selected_items: List[Dict]) -> Dict:
        """Save selected files/folders for syncing."""
        try:
            # Validate access
            if not validate_course_access(course_name, user_email, self.supabase):
                return {'error': 'Access denied'}
            
            # Get integration
            tokens = self.get_project_tokens(course_name)
            if not tokens:
                return {'error': 'Integration not found'}
            
            # Save selections
            items_to_insert = []
            for item in selected_items:
                items_to_insert.append({
                    'project_integration_id': tokens['integration_id'],
                    'provider': 'google_drive',
                    'item_type': 'folder' if item.get('isFolder') else 'file',
                    'drive_item_id': item['id'],
                    'name': item['name'],
                    'mime_type': item.get('mimeType'),
                    'recursive': True,
                    'created_at': utcnow().isoformat(),
                    'updated_at': utcnow().isoformat()
                })
            
            if items_to_insert:
                self.supabase.table('integration_items').upsert(items_to_insert).execute()
                
                # Trigger initial sync
                self._sync_items(course_name, [item['id'] for item in selected_items])
            
            return {'success': True, 'count': len(items_to_insert)}
            
        except Exception as e:
            print(f"Save selections error: {e}")
            return {'error': str(e)}

    def _sync_items(self, course_name: str, item_ids: Optional[List[str]] = None):
        """Sync selected items (internal method)."""
        try:
            tokens = self.get_project_tokens(course_name)
            if not tokens:
                return
            
            # Get items to sync
            query = self.supabase.table('integration_items')\
                .select('*')\
                .eq('project_integration_id', tokens['integration_id'])
            
            if item_ids:
                query = query.in_('drive_item_id', item_ids)
            
            items = query.execute().data
            
            for item in items:
                if item['item_type'] == 'folder':
                    self._sync_folder(course_name, tokens, item)
                else:
                    self._sync_file(course_name, tokens, item)
                    
        except Exception as e:
            print(f"Sync items error: {e}")

    def _sync_folder(self, course_name: str, tokens: Dict, folder_item: Dict):
        """Sync all files in a folder."""
        try:
            # List folder contents
            result = self.list_files(course_name, folder_item['drive_item_id'])
            if 'error' in result:
                return
            
            # Process each file (not subfolders for now - keep it simple)
            for file_data in result['files']:
                if not file_data['isFolder']:
                    self._sync_individual_file(course_name, tokens, file_data)
                    
        except Exception as e:
            print(f"Sync folder error: {e}")

    def _sync_file(self, course_name: str, tokens: Dict, file_item: Dict):
        """Sync a single file."""
        try:
            # Get current file metadata
            url = f"https://www.googleapis.com/drive/v3/files/{file_item['drive_item_id']}?fields=id,name,mimeType,modifiedTime,md5Checksum,size&supportsAllDrives=true"
            
            def make_request():
                return requests.get(url, headers={'Authorization': f"Bearer {tokens['access_token']}"})
            
            response = retryable_request(make_request)
            if response.status_code != 200:
                return
            
            file_data = response.json()
            self._sync_individual_file(course_name, tokens, file_data)
            
        except Exception as e:
            print(f"Sync file error: {e}")

    def _sync_individual_file(self, course_name: str, tokens: Dict, file_data: Dict):
        """Download and ingest a single file."""
        try:
            file_id = file_data['id']
            file_name = file_data['name']
            mime_type = file_data.get('mimeType', '')
            version_hint = file_data.get('md5Checksum') or file_data.get('modifiedTime')
            
            # Check if already processed
            existing = self.supabase.table('ingestion_assets')\
                .select('id')\
                .eq('course_name', course_name)\
                .eq('provider', 'google_drive')\
                .eq('drive_item_id', file_id)\
                .eq('drive_version_hint', version_hint)\
                .eq('status', 'succeeded')\
                .execute().data
            
            if existing:
                return  # Already processed this version
            
            # Check file size
            file_size = int(file_data.get('size', 0))
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                self._record_ingestion_failure(
                    course_name, file_id, file_name, version_hint,
                    f"File too large: {file_size / (1024*1024):.1f}MB"
                )
                return
            
            # Download file
            file_content = self._download_file(tokens['access_token'], file_id, mime_type)
            if not file_content:
                return
            
            # Generate unique S3 key
            file_extension = self._get_file_extension(file_name, mime_type)
            s3_key = f"courses/{course_name}/drive_{uuid.uuid4()}{file_extension}"
            
            # Submit to Beam ingest
            self._submit_to_beam_ingest(course_name, file_id, file_name, s3_key, file_content, version_hint)
            
        except Exception as e:
            print(f"Sync individual file error: {e}")

    def _download_file(self, access_token: str, file_id: str, mime_type: str) -> Optional[bytes]:
        """Download file from Google Drive."""
        try:
            # Handle Google Workspace files (export as PDF)
            if mime_type.startswith('application/vnd.google-apps'):
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=application/pdf&supportsAllDrives=true"
            else:
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
            
            def make_request():
                return requests.get(url, headers={'Authorization': f"Bearer {access_token}"}, stream=True)
            
            response = retryable_request(make_request)
            if response.status_code == 200:
                return response.content
            
            return None
            
        except Exception as e:
            print(f"Download file error: {e}")
            return None

    def _get_file_extension(self, file_name: str, mime_type: str) -> str:
        """Get appropriate file extension."""
        if '.' in file_name:
            return '.' + file_name.split('.')[-1]
        elif mime_type.startswith('application/vnd.google-apps'):
            return '.pdf'  # Google Workspace files exported as PDF
        elif 'pdf' in mime_type:
            return '.pdf'
        elif 'word' in mime_type or 'document' in mime_type:
            return '.docx'
        elif 'sheet' in mime_type:
            return '.xlsx'
        elif 'presentation' in mime_type:
            return '.pptx'
        else:
            return '.txt'

    def _submit_to_beam_ingest(self, course_name: str, file_id: str, file_name: str, s3_key: str, file_content: bytes, version_hint: str):
        """Submit file to Beam ingest pipeline."""
        try:
            # Upload file to S3 first
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                
                # Upload to S3
                self.aws_storage.upload_file(temp_file.name, S3_BUCKET_NAME, s3_key)
            
            # Get project_id for the course
            project_result = self.supabase.table('projects').select('id').eq('course_name', course_name).execute()
            if not project_result.data:
                raise ValueError(f'Project not found for course: {course_name}')
            project_id = project_result.data[0]['id']
            
            # Record ingestion attempt
            ingestion_record = {
                'project_id': project_id,
                'provider': 'google_drive',
                'drive_item_id': file_id,
                'drive_version_hint': version_hint,
                's3_key': s3_key,
                'readable_filename': file_name,
                'status': 'queued',
                'created_at': utcnow().isoformat(),
                'course_name': course_name  # Keep for backwards compatibility
            }
            
            result = self.supabase.table('ingestion_assets').insert(ingestion_record).execute()
            
            # Submit to Beam using the same format as existing ingest
            beam_payload = {
                'course_name': course_name,
                'readable_filename': file_name,
                's3_paths': s3_key,
            }
            
            beam_response = requests.post(
                BEAM_INGEST_URL,
                headers={
                    'Authorization': f'Bearer {BEAM_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json=beam_payload,
                timeout=30
            )
            
            if beam_response.status_code == 200:
                task_data = beam_response.json()
                # Note: Don't update to 'processing' since the constraint only allows queued/succeeded/failed
                # The record stays as 'queued' until Beam calls back with success/failure
                
                print(f"✅ Successfully submitted {file_name} to Beam ingest: {task_data.get('task_id')}")
            else:
                self._record_ingestion_failure(
                    course_name, file_id, file_name, version_hint,
                    f"Beam submission failed: {beam_response.status_code}"
                )
                
        except Exception as e:
            print(f"Submit to beam error: {e}")
            self._record_ingestion_failure(
                course_name, file_id, file_name, version_hint,
                f"Submission error: {str(e)}"
            )

    def _record_ingestion_failure(self, course_name: str, file_id: str, file_name: str, version_hint: str, error_msg: str):
        """Record ingestion failure."""
        # Get project_id for the course
        project_result = self.supabase.table('projects').select('id').eq('course_name', course_name).execute()
        if not project_result.data:
            print(f'Warning: Project not found for course: {course_name}')
            return
        project_id = project_result.data[0]['id']
        
        self.supabase.table('ingestion_assets').insert({
            'project_id': project_id,
            'provider': 'google_drive',
            'drive_item_id': file_id,
            'drive_version_hint': version_hint,
            'readable_filename': file_name,
            'status': 'failed',
            'error_message': error_msg,
            'created_at': utcnow().isoformat(),
            'course_name': course_name  # Keep for backwards compatibility
        }).execute()


# Initialize service (will be injected)
drive_service = None

def get_drive_service() -> GoogleDriveService:
    """Get the drive service instance from Flask app context."""
    from flask import current_app
    if hasattr(current_app, 'drive_service'):
        return current_app.drive_service
    raise RuntimeError("Drive service not initialized")


@drive_bp.route('/google/auth-url', methods=['GET'])
def get_google_auth_url():
    """Get Google OAuth authorization URL."""
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        service = get_drive_service()
        auth_url = service.get_auth_url()
        return jsonify({'url': auth_url})
        
    except Exception as e:
        print(f"Auth URL error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to generate auth URL'}), 500


@drive_bp.route('/google/callback', methods=['GET'])
def google_oauth_callback():
    """Handle Google OAuth callback."""
    print("🔧 CALLBACK ROUTE CALLED")
    try:
        code = request.args.get('code')
        user_email = get_user_email_from_request(request)
        
        if not code:
            return redirect('https://dev.aganswers.ai/oauth-failed')
        
        if not user_email:
            return redirect('https://dev.aganswers.ai/oauth-failed')
        
        service = get_drive_service()
        success = service.handle_oauth_callback(code, user_email)
        
        if success:
            return redirect('https://dev.aganswers.ai/oauth-success')
        else:
            return redirect('https://dev.aganswers.ai/oauth-failed')
            
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return redirect('https://dev.aganswers.ai/oauth-failed')


@drive_bp.route('/google/connect', methods=['POST'])
def connect_google_drive():
    """Connect Google Drive to a course."""
    print("🔧 CONNECT ROUTE CALLED")
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        course_name = data.get('course_name')
        
        if not course_name:
            return jsonify({'error': 'course_name required'}), 400
        
        service = get_drive_service()
        result = service.connect_to_course(course_name, user_email)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Connect Google Drive error: {e}")
        return jsonify({'error': 'Connection failed'}), 500


@drive_bp.route('/google/list', methods=['GET'])
def list_google_drive_files():
    """List Google Drive files."""
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        course_name = request.args.get('course_name')
        folder_id = request.args.get('folder_id', 'root')
        
        if not course_name:
            return jsonify({'error': 'course_name required'}), 400
        
        # Validate access
        service = get_drive_service()
        if not validate_course_access(course_name, user_email, service.supabase):
            return jsonify({'error': 'Access denied'}), 403
        
        result = service.list_files(course_name, folder_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"List files error: {e}")
        return jsonify({'error': 'Failed to list files'}), 500


@drive_bp.route('/google/select', methods=['POST'])
def select_google_drive_files():
    """Select Google Drive files for syncing."""
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        course_name = data.get('course_name')
        selected_items = data.get('items', [])
        
        if not course_name:
            return jsonify({'error': 'course_name required'}), 400
        
        service = get_drive_service()
        result = service.save_selections(course_name, user_email, selected_items)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Select files error: {e}")
        return jsonify({'error': 'Failed to save selections'}), 500


@drive_bp.route('/google/sync', methods=['POST'])
def sync_google_drive():
    """Trigger manual sync of Google Drive files."""
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        course_name = data.get('course_name')
        
        if not course_name:
            return jsonify({'error': 'course_name required'}), 400
        
        # Validate access
        service = get_drive_service()
        if not validate_course_access(course_name, user_email, service.supabase):
            return jsonify({'error': 'Access denied'}), 403
        
        # Trigger sync
        service._sync_items(course_name)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Sync error: {e}")
        return jsonify({'error': 'Sync failed'}), 500


@drive_bp.route('/google/ingest-callback', methods=['POST'])
def handle_ingest_callback():
    """Handle Beam ingest completion callback."""
    try:
        data = request.get_json()
        course_name = data.get('course_name')
        readable_filename = data.get('readable_filename')
        s3_key = data.get('s3_key', data.get('s3_paths'))  # Handle both formats
        success = data.get('success', False)
        error_message = data.get('error')
        
        if not course_name or not readable_filename:
            return jsonify({'error': 'Missing required fields'}), 400
        
        service = get_drive_service()
        
        # Find the ingestion record by course_name and readable_filename
        # Since we don't have the exact drive_item_id in callback, match by filename and s3_key
        query = service.supabase.table('ingestion_assets')\
            .select('id')\
            .eq('provider', 'google_drive')\
            .eq('readable_filename', readable_filename)
        
        if s3_key:
            query = query.eq('s3_key', s3_key)
        else:
            # Fallback to course_name match if no s3_key
            query = query.eq('course_name', course_name)
        
        records = query.execute()
        
        if not records.data:
            print(f"Warning: No ingestion record found for {readable_filename} in {course_name}")
            return jsonify({'warning': 'No matching ingestion record found'}), 200
        
        # Update the most recent record (in case of duplicates)
        record_id = records.data[0]['id']
        
        update_data = {
            'status': 'succeeded' if success else 'failed',
            'ingested_at': utcnow().isoformat() if success else None
        }
        
        if error_message:
            update_data['error_message'] = str(error_message)
        
        service.supabase.table('ingestion_assets')\
            .update(update_data)\
            .eq('id', record_id)\
            .execute()
        
        status = 'succeeded' if success else 'failed'
        print(f"✅ Updated ingestion status to '{status}' for {readable_filename}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Ingest callback error: {e}")
        return jsonify({'error': 'Callback processing failed'}), 500


@drive_bp.route('/google/ingestion-status', methods=['GET'])
def get_ingestion_status():
    """Get ingestion status for Google Drive files."""
    try:
        user_email = get_user_email_from_request(request)
        if not user_email:
            return jsonify({'error': 'Authentication required'}), 401
        
        course_name = request.args.get('course_name')
        if not course_name:
            return jsonify({'error': 'course_name required'}), 400
        
        service = get_drive_service()
        
        # Get all Google Drive ingestion statuses for this course
        records = service.supabase.table('ingestion_assets')\
            .select('drive_item_id, readable_filename, status, error_message, created_at, ingested_at')\
            .eq('provider', 'google_drive')\
            .eq('course_name', course_name)\
            .order('created_at', desc=True)\
            .execute()
        
        return jsonify({
            'success': True,
            'ingestions': records.data or []
        })
        
    except Exception as e:
        print(f"Ingestion status error: {e}")
        return jsonify({'error': 'Failed to get ingestion status'}), 500
