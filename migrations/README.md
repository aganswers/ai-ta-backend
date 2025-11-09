# Database Migrations

This directory contains SQL migrations for the AgAnswers backend database.

## How to Apply Migrations

### Via Supabase SQL Editor (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor (https://supabase.com/dashboard/project/YOUR_PROJECT/sql)
3. Copy the contents of the migration file
4. Paste into the SQL editor and click "Run"

### Via psql CLI

```bash
# Set your database connection string
export DATABASE_URL="postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"

# Apply migration
psql $DATABASE_URL -f migrations/add_spotlight_search_columns.sql
```

### Via Python Script

```python
from ai_ta_backend.database.sql import SQLDatabase

sql_db = SQLDatabase()

with open('migrations/add_spotlight_search_columns.sql', 'r') as f:
    migration_sql = f.read()
    
# Note: Supabase client doesn't directly support raw SQL execution
# Use Supabase dashboard SQL Editor instead
```

## Migration Files

### add_spotlight_search_columns.sql
Adds columns for Vertex AI Spotlight Search feature:
- `summary` - AI-generated document summaries
- `keywords` - Extracted keywords array
- `vertex_corpus_id` - Vertex AI corpus reference
- `vertex_document_id` - Vertex AI document reference
- `file_type` - File classification
- `column_headers` - CSV column names (for structured data)
- `row_count` - Row count (for structured data)

Includes indexes for:
- GIN index on keywords array
- B-tree index on file_type
- Composite index on vertex IDs
- Full-text search on summary
- Trigram index for fuzzy filename search

## Rollback

To rollback this migration:

```sql
-- Remove indexes
DROP INDEX IF EXISTS idx_documents_readable_filename_trgm;
DROP INDEX IF EXISTS idx_documents_summary_fts;
DROP INDEX IF EXISTS idx_documents_vertex;
DROP INDEX IF EXISTS idx_documents_file_type;
DROP INDEX IF EXISTS idx_documents_keywords;

-- Remove columns
ALTER TABLE public.documents
DROP COLUMN IF EXISTS row_count,
DROP COLUMN IF EXISTS column_headers,
DROP COLUMN IF EXISTS file_type,
DROP COLUMN IF EXISTS vertex_document_id,
DROP COLUMN IF EXISTS vertex_corpus_id,
DROP COLUMN IF EXISTS keywords,
DROP COLUMN IF EXISTS summary;
```

## Best Practices

1. **Backup First**: Always backup your database before applying migrations
2. **Test in Staging**: Apply to staging environment before production
3. **Monitor Performance**: Check query performance after adding indexes
4. **Version Control**: Keep migrations in git for team visibility
5. **Document Changes**: Update this README when adding new migrations

