# Google Drive Project Groups Integration

## Overview

This integration enables project admins to link Google Drive files to their projects by simply sharing them to a project-specific Google Group email address (e.g., `my-farm@aganswers.ai`). The backend automatically creates these groups when projects are created, and agents can access and analyze shared files conversationally.

## Architecture

### Components

1. **Google Groups Service** (`ai_ta_backend/integrations/google_groups.py`)
   - Creates and manages Google Groups for projects
   - Lists files shared with groups using Drive API
   - Downloads file content for analysis

2. **Project Service** (`ai_ta_backend/service/project_service.py`)
   - Automatically creates Google Group on project creation
   - Stores group email in database

3. **Drive Agent** (`ai_ta_backend/agents/tools/drive/`)
   - Loads Google Sheets/CSVs into pandas DataFrames
   - Provides data analysis capabilities via code execution

4. **File Agent Service** (`ai_ta_backend/service/file_agent_service.py`)
   - Integrates Drive files with existing CSV file handling
   - Merges Drive DataFrames with R2 CSV DataFrames

## How It Works

### 1. Project Creation Flow

```
User creates project
    ↓
ProjectService.create_project()
    ↓
GoogleGroupsService.create_project_group()
    ↓
Group created: "project-name@aganswers.ai"
    ↓
group_email stored in projects table
    ↓
Returned to frontend in response
```

### 2. File Sharing Flow

```
Admin shares Google Sheet to group email
    ↓
File permissions updated in Google Drive
    ↓
Backend can access file via service account (DWD)
```

### 3. Agent Query Flow

```
User sends message to agent
    ↓
FileAgentService.prepare_file_agent()
    ↓
Load R2 CSVs + Drive files for project
    ↓
Merge into single DataFrame collection
    ↓
Agent analyzes data and responds
```

## API Endpoints

### Create Project
```http
POST /createProject
Content-Type: application/json

{
  "project_name": "My Farm",
  "project_description": "Farm management project",
  "project_owner_email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "group_email": "my-farm@aganswers.ai"
}
```

### Get Project Group Email
```http
GET /getProjectGroupEmail?project_name=My%20Farm
```

**Response:**
```json
{
  "project_name": "My Farm",
  "group_email": "my-farm@aganswers.ai"
}
```

## Database Schema

### projects Table

```sql
CREATE TABLE public.projects (
  id bigint PRIMARY KEY,
  course_name character varying UNIQUE,
  group_email character varying UNIQUE,  -- Added for Drive integration
  -- ... other columns
);
```

The `group_email` column stores the project-specific Google Group email address.

## Configuration

### Service Account Setup

**Location:** `/etc/aganswers/service-account.json`

**Required Scopes:**
- `https://www.googleapis.com/auth/admin.directory.group`
- `https://www.googleapis.com/auth/admin.directory.group.member`
- `https://www.googleapis.com/auth/admin.directory.group.member.readonly`
- `https://www.googleapis.com/auth/apps.groups.settings`
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/drive.metadata.readonly`

**Domain-Wide Delegation:**
- Subject: `admin@aganswers.ai`
- Client ID: `105228981945699118145`

### Environment Variables

No additional environment variables required. Uses existing:
- `SUPABASE_URL`
- `SUPABASE_API_KEY`

## Usage Examples

### For Project Admins

1. **Create a project** via the frontend
2. **Get the group email** from the project dashboard
3. **Share Google Drive files:**
   - Open Google Sheet/Doc
   - Click "Share"
   - Enter: `your-project@aganswers.ai`
   - Grant "Viewer" or "Editor" access
4. **Query the agent** about your data

### For Developers

#### Create a Google Group Manually

```python
from ai_ta_backend.integrations.google_groups import GoogleGroupsService

service = GoogleGroupsService()
group_email = service.create_project_group("Test Project")
print(f"Created: {group_email}")
# Output: Created: test-project@aganswers.ai
```

#### List Files Shared with Group

```python
from ai_ta_backend.integrations.google_groups import GoogleGroupsService

service = GoogleGroupsService()
files = service.list_files_shared_with_group("test-project@aganswers.ai")

for file in files:
    print(f"{file['name']} ({file['mimeType']})")
```

#### Load Drive Files into Agent

```python
from ai_ta_backend.agents.tools.drive.agent import load_drive_files_for_project

dataframes = load_drive_files_for_project(
    project_name="Test Project",
    group_email="test-project@aganswers.ai"
)

for name, df in dataframes.items():
    print(f"{name}: {df.shape}")
```

## Supported File Types

Currently supported for data analysis:
- **Google Sheets** (exported as CSV)
- **CSV files** (`.csv`)

Files are automatically converted to pandas DataFrames for analysis.

## Project Name Sanitization

Project names are automatically sanitized to create valid email addresses:

| Input | Output |
|-------|--------|
| `My Farm` | `my-farm@aganswers.ai` |
| `Test!@#$% Project` | `test-project@aganswers.ai` |
| `AgAnswers 2024` | `aganswers-2024@aganswers.ai` |
| `Multiple   Spaces` | `multiple-spaces@aganswers.ai` |

**Rules:**
- Lowercase conversion
- Spaces and special characters → hyphens
- Multiple consecutive hyphens collapsed
- Leading/trailing hyphens removed

## Error Handling

### Group Creation Failures

If group creation fails during project creation:
- Error is logged
- Project creation continues
- `group_email` is set to `null`
- User can retry later or contact support

### Duplicate Group Names

If a sanitized name conflicts with an existing group:
- System appends 8-character UUID suffix
- Example: `my-farm-a1b2c3d4@aganswers.ai`
- Retries up to 5 times

### File Access Failures

If Drive files cannot be loaded:
- Error is logged
- Agent continues with R2 CSV files only
- User experience is not interrupted

### Permission Errors

If service account lacks proper scopes:
- Clear error message in logs
- Group creation fails gracefully
- Admin should verify scopes in Google Workspace Admin Console

## Testing

### Test Script

Run the test script to verify setup:

```bash
cd /home/ubuntu/backend
source backend/bin/activate
python test_google_groups.py
```

**Expected Output:**
```
✅ Service account initialized successfully
✅ Successfully listed groups: X found
```

### Manual End-to-End Test

1. **Create a test project:**
   ```bash
   curl -X POST https://backend.aganswers.ai/createProject \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "Test Drive Integration",
       "project_description": "Testing Google Drive",
       "project_owner_email": "test@example.com"
     }'
   ```

2. **Verify group was created:**
   - Check Google Workspace Admin Console
   - Look for `test-drive-integration@aganswers.ai`

3. **Share a test Google Sheet:**
   - Create a simple spreadsheet
   - Share to the group email
   - Grant "Viewer" access

4. **Query the agent:**
   - Send a message asking about the data
   - Verify agent can access and analyze the file

## Troubleshooting

### "Failed to create Google Group"

**Cause:** Service account lacks proper scopes or permissions

**Solution:**
1. Verify scopes in Google Workspace Admin Console
2. Check service account has "Group Administrator" role
3. Ensure domain-wide delegation is enabled

### "No Drive files found"

**Cause:** Files not shared with group, or permissions issue

**Solution:**
1. Verify file is shared with correct group email
2. Check file permissions (must be "Viewer" or higher)
3. Verify service account can impersonate `admin@aganswers.ai`

### "Cannot access file"

**Cause:** File permissions or Drive API scope issue

**Solution:**
1. Ensure Drive API scopes are configured
2. Verify file is not restricted by DLP policies
3. Check file owner's sharing settings

## Security Considerations

### Access Control

- Groups are **internal only** (`allowExternalMembers: false`)
- Only domain users can be added to groups
- Service account uses domain-wide delegation with `admin@aganswers.ai`

### File Permissions

- Backend only accesses files explicitly shared with group
- Files remain in owner's Drive (not copied)
- Owner can revoke access at any time

### Data Privacy

- Files are loaded into memory temporarily for analysis
- No persistent storage of file content
- DataFrames cleared after conversation ends

## Performance Considerations

### File Loading

- Maximum 10 files loaded per project (configurable)
- Files loaded in parallel for better performance
- Only spreadsheet files are processed (others ignored)

### Caching

- DataFrames loaded once per conversation
- Cleared when conversation ends
- No cross-conversation caching (for security)

## Future Enhancements

Potential improvements for future versions:

1. **Additional File Types**
   - Google Docs (text analysis)
   - Google Slides (content extraction)
   - Excel files (.xlsx)

2. **File Management UI**
   - View linked files in dashboard
   - Manually select which files to include
   - File sync status indicators

3. **Advanced Features**
   - Real-time file updates
   - File version tracking
   - Collaborative editing support

4. **Performance Optimizations**
   - Smart caching strategies
   - Incremental file loading
   - Background sync jobs

## Support

For issues or questions:
- Check logs: `/home/ubuntu/backend/output.log`
- Run test script: `python test_google_groups.py`
- Contact: DevOps team

## References

- [Google Workspace Admin SDK](https://developers.google.com/admin-sdk)
- [Google Drive API](https://developers.google.com/drive)
- [Domain-Wide Delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)
- [Groups Settings API](https://developers.google.com/admin-sdk/groups-settings)

