import os
import requests
from dotenv import load_dotenv

# Load .env file (if you have one)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

if not SUPABASE_URL or not SUPABASE_API_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SUPABASE_API_KEY in environment")

# Ensure the URL doesn’t end with a slash
SUPABASE_URL = SUPABASE_URL.rstrip("/")

# Full schema dump endpoint
DUMP_URL = f"{SUPABASE_URL}/pg/dump"

print("Fetching full database schema from Supabase...")

headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
}

response = requests.get(DUMP_URL, headers=headers)
if response.status_code != 200:
    print("❌ Failed to fetch schema dump:")
    print(response.text)
    exit(1)

schema_sql = response.text

# Save to file
with open("schema.sql", "w") as f:
    f.write(schema_sql)

print("✅ Schema successfully saved to schema.sql")
