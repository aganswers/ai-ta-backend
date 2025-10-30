# Google Drive Integration - Complete Implementation

## ✅ Status: PRODUCTION READY

The Google Drive integration is fully implemented and tested. Users can now share Google Drive files with their projects by simply sharing them to a project-specific email address, and agents can access and analyze those files.

---

## 🎯 Overview

When a project is created, a Google Group is automatically created for it. Users share their Google Drive files to this group email, and the backend uses Domain-Wide Delegation to access those files on behalf of `admin@aganswers.ai`.

---

## 🔑 Key Features

### 1. **Automatic Group Creation**
- When a project is created, a Google Group is automatically created
- Group email format: `<sanitized-project-name>@aganswers.ai`
- Example: Project "My Farm" → `my-farm@aganswers.ai`
- **Admin membership**: `admin@aganswers.ai` is automatically added as a MEMBER to every group
- Retry logic handles eventual consistency delays (up to 5 retries with exponential backoff)

### 2. **File Sharing Flow**
- Project dashboard displays the group email
- Users share Google Drive files/folders with the group email
- Backend automatically detects and loads shared files
- Supports: Google Sheets (exported as CSV), CSV files

### 3. **Agent Integration**
- Base agent receives a list of available files in its instruction
- File queries are routed to the `file_agent`
- Both CSV files (from R2) and Google Drive files are loaded into pandas DataFrames
- Agent can analyze, visualize, and answer questions about the data

### 4. **Security & Access Control**
- All access happens through Domain-Wide Delegation
- Service account impersonates `admin@aganswers.ai`
- Files are scoped to the requesting project's group
- No user re-authentication required

---

## 📁 Implementation Files

### Backend Services

1. **`ai_ta_backend/integrations/google_groups.py`**
   - `GoogleGroupsService` class
   - Methods:
     - `create_project_group()` - Creates group and adds admin as member
     - `_add_admin_to_group()` - Adds admin with retry logic
     - `ensure_admin_is_member()` - Retroactive admin membership
     - `list_files_shared_with_group()` - Lists files shared with group
     - `get_file_content()` - Downloads file content
     - `delete_project_group()` - Deletes group
     - `_configure_group_settings()` - Configures group settings

2. **`ai_ta_backend/service/project_service.py`**
   - Modified `create_project()` to create Google Group
   - Modified `generate_json_schema()` to store `group_email` in Supabase
   - Returns `{"success": True, "group_email": "..."}` on success

3. **`ai_ta_backend/service/file_agent_service.py`**
   - Modified `prepare_file_agent()` to load both CSV and Drive files
   - Handles JSON-encoded group_email from Supabase
   - Merges CSV and Drive DataFrames

4. **`ai_ta_backend/agents/tools/drive/agent.py`**
   - `load_drive_files_for_project()` - Loads Drive files into DataFrames
   - Supports Google Sheets (exported as CSV)
   - Supports direct CSV files

5. **`ai_ta_backend/main.py`**
   - Added `/getProjectGroupEmail` endpoint
   - Modified `/createProject` to handle group_email
   - Modified `/Chat` to dynamically inject available files into agent instruction
   - Loads files after `prepare_file_agent()` completes

6. **`ai_ta_backend/agents/agent.py`**
   - Modified `create_agent_with_model()` to accept `available_files` parameter
   - Dynamically injects file list into agent instruction

### Frontend Components

1. **`frontend/src/utils/apiUtils.ts`**
   - Added `fetchProjectGroupEmail()` function

2. **`frontend/src/pages/[course_name]/dashboard.tsx`**
   - Fetches group_email on page load
   - Passes to `MakeOldCoursePage`

3. **`frontend/src/components/UIUC-Components/MakeOldCoursePage.tsx`**
   - Accepts `group_email` prop
   - Passes to `UploadCard`

4. **`frontend/src/components/UIUC-Components/UploadCard.tsx`**
   - Accepts `group_email` prop
   - Passes to `GoogleDriveIngestForm`

5. **`frontend/src/components/UIUC-Components/GoogleDriveIngestForm.tsx`**
   - Displays the group email in a modal
   - Shows sharing instructions
   - Handles loading state

---

## 🧪 Testing

### Test Results

```bash
# Test 1: Create new group with admin membership
✅ Group created: test-74b90e@aganswers.ai
✅ admin@aganswers.ai added as MEMBER
✅ Verified membership after eventual consistency delay

# Test 2: Check existing group
✅ andrew@aganswers.ai has admin@aganswers.ai as OWNER

# Test 3: Load Drive files
✅ Loaded "fruit" file (41 rows × 20 columns) from Google Sheets
✅ Successfully converted to pandas DataFrame
```

### Verified Functionality

- ✅ Google Group creation with unique naming
- ✅ Admin membership with retry logic (handles 404 errors)
- ✅ File listing with permission filtering
- ✅ File content download and DataFrame conversion
- ✅ Agent instruction with dynamic file list
- ✅ Frontend displays group email
- ✅ Eventual consistency handling

---

## 🔧 Configuration

### Required Environment Variables

```bash
# Already configured in /etc/aganswers/
SERVICE_ACCOUNT_FILE="/etc/aganswers/service-account.json"
ADMIN_EMAIL="admin@aganswers.ai"
DOMAIN="aganswers.ai"
```

### Required Google API Scopes

```python
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member",
    "https://www.googleapis.com/auth/apps.groups.settings",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]
```

### Supabase Schema

Added `group_email` column to `projects` table:

```sql
ALTER TABLE projects ADD COLUMN group_email TEXT;
```

---

## 📊 Data Flow

```
1. User creates project
   ↓
2. Backend creates Google Group
   ↓
3. Admin added as MEMBER (with retry logic)
   ↓
4. Group email stored in Supabase
   ↓
5. Frontend displays group email
   ↓
6. User shares Drive file to group email
   ↓
7. User asks agent about the file
   ↓
8. Backend loads Drive files into DataFrames
   ↓
9. Agent analyzes and responds
```

---

## 🚀 Usage Example

### For Users

1. **Create a project** (or use existing project with group_email)
2. **View the project dashboard** - see the group email
3. **Share a Google Sheet** to that email (e.g., `my-farm@aganswers.ai`)
4. **Ask the agent**: "What files do we have?"
   - Response: "We have the following files: 📊 fruit"
5. **Ask about the data**: "What is in the fruit file?"
   - Agent loads the file and analyzes it

### For Developers

```python
# Create a group programmatically
from ai_ta_backend.integrations.google_groups import GoogleGroupsService

service = GoogleGroupsService()
group_email = service.create_project_group("My Farm Project")
# Returns: "my-farm-project@aganswers.ai"
# Admin is automatically a member

# Ensure admin membership (retroactive)
service.ensure_admin_is_member(group_email)

# List files shared with group
files = service.list_files_shared_with_group(group_email)

# Load Drive files for a project
from ai_ta_backend.agents.tools.drive.agent import load_drive_files_for_project
dataframes = load_drive_files_for_project("My Farm Project", group_email)
```

---

## ⚠️ Known Issues & Limitations

### Resolved Issues

- ✅ **Eventual consistency delays**: Fixed with retry logic (exponential backoff)
- ✅ **Group_email stored as JSON string**: Fixed with JSON.loads() handling
- ✅ **Admin not visible immediately**: Handled with retries and wait time

### Current Limitations

1. **Groups Settings API**: Currently disabled in project 789202960149
   - Impact: Group settings cannot be configured programmatically
   - Workaround: Groups work fine with default settings
   - Future: Enable API in Google Cloud Console if needed

2. **Supported File Types**: Currently limited to:
   - Google Sheets (exported as CSV)
   - CSV files
   - Future: Can extend to Google Docs, PDFs, etc.

3. **File Sync**: Not real-time
   - Files are loaded when conversation starts
   - Future: Implement periodic sync or webhook-based updates

---

## 🔮 Future Enhancements

1. **Real-time Sync**
   - Implement periodic background sync
   - Use Google Drive Push Notifications (webhooks)

2. **Additional File Types**
   - Google Docs → Markdown or plain text
   - PDFs → Text extraction
   - Images → OCR or vision analysis

3. **File Management UI**
   - List files in dashboard
   - Remove file access
   - View file metadata

4. **Advanced Permissions**
   - Allow project admins to add/remove files
   - Audit log for file access
   - Fine-grained permissions per file

5. **Group Settings UI**
   - Enable Groups Settings API
   - Allow customization of group settings
   - Manage external member access

---

## 📝 Testing Commands

```bash
# Test group creation
cd /home/ubuntu/backend
source backend/bin/activate
python test_google_groups.py

# Test Drive integration
python test_drive_integration.py

# Test admin membership
python -c "
from ai_ta_backend.integrations.google_groups import GoogleGroupsService
service = GoogleGroupsService()
result = service.ensure_admin_is_member('andrew@aganswers.ai')
print(f'Result: {result}')
"
```

---

## ✅ Production Checklist

- [x] Google Group creation working
- [x] Admin membership enforcement
- [x] Retry logic for eventual consistency
- [x] File listing and download
- [x] DataFrame conversion
- [x] Agent integration
- [x] Frontend display
- [x] Error handling
- [x] Testing completed
- [x] Documentation complete

---

## 🎉 Conclusion

The Google Drive integration is **fully functional and production-ready**. All core features are implemented, tested, and working correctly. The system handles eventual consistency gracefully and ensures `admin@aganswers.ai` is always a member of project groups.

**Next Steps**: Monitor production usage and implement future enhancements as needed.

