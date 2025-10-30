from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "/etc/aganswers/service-account.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES,
    subject="admin@aganswers.ai",  # <-- impersonation target
)

drive = build("drive", "v3", credentials=creds)

# Example: get metadata for a file
file = drive.files().get(fileId="1AT5AuRHkKwx3YD2Y7D0RphiDYc0SZEIwa6wTq4vxsxw", fields="id,name,owners").execute()
print(file)
GROUP_EMAIL = "another-test@aganswers.ai"
PAGE_SIZE = 200

def list_group_files(drive, group_email):
    results = []
    page_token = None
    q = "sharedWithMe = true and trashed = false"
    fields_files = "files(id,name,mimeType,modifiedTime,owners(emailAddress,displayName))"
    while True:
        resp = drive.files().list(
            q=q,
            pageSize=PAGE_SIZE,
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields=f"nextPageToken,{fields_files}",
        ).execute()

        for f in resp.get("files", []):
            try:
                perms = drive.permissions().list(
                    fileId=f["id"],
                    supportsAllDrives=True,
                    fields="permissions(emailAddress,type,role,deleted)"
                ).execute().get("permissions", [])
            except Exception as e:
                # skip files we can't access permissions for
                continue

            has_group = any(
                (p.get("type") == "group" and (p.get("emailAddress") or "").lower() == group_email.lower())
                for p in perms if not p.get("deleted", False)
            )
            if has_group:
                results.append(f)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results

# Example usage:
files = list_group_files(drive, GROUP_EMAIL)
print(f"Found {len(files)} files shared with group: {GROUP_EMAIL}\n")
for f in files:
    owners = ", ".join(o.get("emailAddress", "") for o in f.get("owners", []))
    print(f"{f['id']}  |  {f['name']}  |  owners: {owners}  |  modified: {f['modifiedTime']}")
