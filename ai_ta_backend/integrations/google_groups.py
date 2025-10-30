"""
Google Groups management service for project-specific file sharing.
Creates and manages Google Groups for projects to enable Drive file sharing.
"""

import os
import re
import time
import uuid
from typing import Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SERVICE_ACCOUNT_FILE = "/etc/aganswers/service-account.json"
ADMIN_EMAIL = "admin@aganswers.ai"
DOMAIN = "aganswers.ai"

# Required scopes for Groups and Drive API
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member",
    "https://www.googleapis.com/auth/apps.groups.settings",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]


class GoogleGroupsService:
    """Service for managing Google Groups for projects."""
    
    def __init__(self):
        """Initialize the service with domain-wide delegation."""
        self.credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES,
            subject=ADMIN_EMAIL
        )
        self.admin_service = build('admin', 'directory_v1', credentials=self.credentials)
        self.settings_service = build('groupssettings', 'v1', credentials=self.credentials)
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
    
    def sanitize_project_name(self, project_name: str) -> str:
        """
        Convert project name to valid group email prefix.
        
        Examples:
            "My Farm" -> "my-farm"
            "Test!@#$% Project" -> "test-project"
            "AgAnswers 2024" -> "aganswers-2024"
        
        Args:
            project_name: Original project name
            
        Returns:
            Sanitized email prefix (lowercase, alphanumeric and hyphens only)
        """
        # Convert to lowercase
        sanitized = project_name.lower()
        
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^a-z0-9]+', '-', sanitized)
        
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        
        # Collapse multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = f"project-{uuid.uuid4().hex[:8]}"
        
        return sanitized
    
    def create_project_group(self, project_name: str, project_id: Optional[str] = None) -> str:
        """
        Create a Google Group for a project.
        
        Args:
            project_name: Name of the project
            project_id: Optional project ID for uniqueness
            
        Returns:
            Group email address (e.g., "my-farm-drive@aganswers.ai")
            
        Raises:
            Exception: If group creation fails
        """
        base_email_prefix = self.sanitize_project_name(project_name)
        group_email = f"{base_email_prefix}-drive@{DOMAIN}"
        
        # Handle duplicate group names by appending UUID
        attempt = 0
        max_attempts = 5
        
        while attempt < max_attempts:
            try:
                # Try to create the group
                group_body = {
                    'email': group_email,
                    'name': f"{project_name} Project Group",
                    'description': f"Google Group for {project_name} project file sharing"
                }
                
                print(f"Creating Google Group: {group_email}")
                created_group = self.admin_service.groups().insert(body=group_body).execute()
                print(f"✅ Successfully created group: {group_email}")
                
                # Add admin@aganswers.ai as a member of the group
                self._add_admin_to_group(group_email)
                
                # Configure group settings
                self._configure_group_settings(group_email)
                
                return group_email
                
            except HttpError as e:
                if e.resp.status == 409:  # Conflict - group already exists
                    print(f"⚠️  Group {group_email} already exists, trying with UUID suffix")
                    # Append UUID suffix and retry (before -drive suffix)
                    suffix = uuid.uuid4().hex[:8]
                    group_email = f"{base_email_prefix}-{suffix}-drive@{DOMAIN}"
                    attempt += 1
                else:
                    print(f"❌ Failed to create group: {e}")
                    raise Exception(f"Failed to create Google Group: {e}")
        
        raise Exception(f"Failed to create unique group after {max_attempts} attempts")
    
    def _add_admin_to_group(self, group_email: str):
        """
        Add admin@aganswers.ai as a member of the group.
        This ensures the admin account has access to all files shared with the group.
        
        Uses retry logic to handle eventual consistency delays in Google's systems.
        
        Args:
            group_email: Email address of the group
        """
        member_body = {
            'email': ADMIN_EMAIL,
            'role': 'OWNER'  # Can be MEMBER, MANAGER, or OWNER
        }
        
        # Retry up to 5 times with exponential backoff
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.admin_service.members().insert(
                    groupKey=group_email,
                    body=member_body
                ).execute()
                
                print(f"✅ Added {ADMIN_EMAIL} as member of {group_email}")
                return
                
            except HttpError as e:
                if e.resp.status == 409:
                    # Admin is already a member
                    print(f"ℹ️  {ADMIN_EMAIL} is already a member of {group_email}")
                    return
                elif e.resp.status == 404 and attempt < max_retries - 1:
                    # Group not found yet (eventual consistency issue), retry with backoff
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8 seconds
                    print(f"⏳ Group not ready yet, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                elif attempt == max_retries - 1:
                    # Final attempt failed
                    print(f"⚠️  Warning: Failed to add {ADMIN_EMAIL} to {group_email} after {max_retries} attempts: {e}")
                else:
                    # Other error, don't retry
                    print(f"⚠️  Warning: Failed to add {ADMIN_EMAIL} to {group_email}: {e}")
                    return
    
    def _configure_group_settings(self, group_email: str):
        """
        Configure group settings for project file sharing.
        
        Settings:
        - External members: Not allowed (internal domain only)
        - Who can post: All members
        - Who can join: Invited only
        - Who can view members: All members
        """
        try:
            settings_body = {
                'allowExternalMembers': 'false',
                'whoCanPostMessage': 'ALL_MEMBERS_CAN_POST',
                'whoCanJoin': 'INVITED_CAN_JOIN',
                'whoCanViewMembership': 'ALL_MEMBERS_CAN_VIEW',
                'whoCanViewGroup': 'ALL_MEMBERS_CAN_VIEW',
                'allowWebPosting': 'false',
                'primaryLanguage': 'en',
                'isArchived': 'false',
                'membersCanPostAsTheGroup': 'false'
            }
            
            self.settings_service.groups().patch(
                groupUniqueId=group_email,
                body=settings_body
            ).execute()
            
            print(f"✅ Configured settings for group: {group_email}")
            
        except HttpError as e:
            print(f"⚠️  Warning: Failed to configure group settings for {group_email}: {e}")
            # Don't fail group creation if settings update fails
    
    def ensure_admin_is_member(self, group_email: str) -> bool:
        """
        Ensure admin@aganswers.ai is a member of the specified group.
        Can be used to retroactively add admin to existing groups.
        
        Args:
            group_email: Email address of the group
            
        Returns:
            True if admin is a member (or was successfully added), False otherwise
        """
        try:
            # Check if admin is already a member
            members = self.admin_service.members().list(groupKey=group_email).execute()
            
            for member in members.get('members', []):
                if member.get('email', '').lower() == ADMIN_EMAIL.lower():
                    print(f"✅ {ADMIN_EMAIL} is already a member of {group_email}")
                    return True
            
            # Admin is not a member, add them
            self._add_admin_to_group(group_email)
            return True
            
        except HttpError as e:
            print(f"❌ Failed to ensure admin membership for {group_email}: {e}")
            return False
    
    def delete_project_group(self, group_email: str) -> bool:
        """
        Delete a Google Group.
        
        Args:
            group_email: Email address of the group to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.admin_service.groups().delete(groupKey=group_email).execute()
            print(f"✅ Deleted group: {group_email}")
            return True
            
        except HttpError as e:
            print(f"❌ Failed to delete group {group_email}: {e}")
            return False
    
    def list_files_shared_with_group(self, group_email: str) -> List[Dict]:
        """
        List all files shared with a specific Google Group.
        
        Uses the Drive API with domain-wide delegation to find files
        that have been shared with the group email.
        
        Args:
            group_email: Email address of the group
            
        Returns:
            List of file metadata dictionaries with keys:
            - id: File ID
            - name: File name
            - mimeType: MIME type
            - modifiedTime: Last modified timestamp
            - webViewLink: Link to view the file
        """
        try:
            results = []
            page_token = None
            
            # Query for files shared with the group
            # We need to check permissions on files shared with admin@aganswers.ai
            # and filter for those shared with the specific group
            query = "sharedWithMe = true and trashed = false"
            
            while True:
                response = self.drive_service.files().list(
                    q=query,
                    pageSize=100,
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,owners(emailAddress))"
                ).execute()
                
                files = response.get('files', [])
                
                # Filter files by checking permissions
                for file_data in files:
                    file_id = file_data['id']
                    file_name = file_data.get('name', 'unknown')
                    
                    try:
                        # Get permissions for this file
                        permissions = self.drive_service.permissions().list(
                            fileId=file_id,
                            supportsAllDrives=True,
                            fields="permissions(emailAddress,type,role,deleted)"
                        ).execute().get('permissions', [])
                        
                        # Check if group has access
                        has_group_access = any(
                            p.get('type') == 'group' and 
                            (p.get('emailAddress') or '').lower() == group_email.lower() and
                            not p.get('deleted', False)
                            for p in permissions
                        )
                        
                        if has_group_access:
                            results.append({
                                'id': file_id,
                                'name': file_name,
                                'mimeType': file_data.get('mimeType', ''),
                                'modifiedTime': file_data.get('modifiedTime', ''),
                                'webViewLink': file_data.get('webViewLink', ''),
                                'owners': file_data.get('owners', [])
                            })
                            
                    except HttpError as e:
                        if e.resp.status in (403, 404):
                            # Skip files we can't access (permissions removed or insufficient access)
                            # This is normal - file may have been shared then unshared, or permissions changed
                            print(f"⚠️  Skipping file '{file_name}' (ID: {file_id}): insufficient permissions")
                            continue
                        raise
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"📁 Found {len(results)} files shared with {group_email}")
            return results
            
        except HttpError as e:
            print(f"❌ Error listing files for group {group_email}: {e}")
            return []
    
    def get_file_content(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """
        Download file content from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file
            
        Returns:
            File content as bytes, or None if download fails
        """
        try:
            # Handle Google Workspace files (export as appropriate format)
            if mime_type.startswith('application/vnd.google-apps'):
                # Export Google Sheets as CSV
                if 'spreadsheet' in mime_type:
                    export_mime = 'text/csv'
                # Export Google Docs as plain text
                elif 'document' in mime_type:
                    export_mime = 'text/plain'
                else:
                    export_mime = 'application/pdf'
                
                request = self.drive_service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )
            else:
                # Download regular files
                request = self.drive_service.files().get_media(fileId=file_id)
            
            content = request.execute()
            return content
            
        except HttpError as e:
            print(f"❌ Error downloading file {file_id}: {e}")
            return None

