"""List all projects to see what exists."""

import os
from dotenv import load_dotenv
load_dotenv()

from ai_ta_backend.database.sql import SQLDatabase

sql_db = SQLDatabase()

projects = sql_db.supabase_client.table('projects')\
    .select('id, course_name, group_email')\
    .limit(20)\
    .execute()

print(f"\n{'='*80}")
print(f"Projects in Database")
print(f"{'='*80}\n")

if projects.data:
    for p in projects.data:
        group_status = "✅" if p.get('group_email') else "❌"
        print(f"{group_status} {p['course_name']:<30} | Group: {p.get('group_email') or 'NOT SET'}")
else:
    print("No projects found")

print(f"\n{'='*80}\n")

