-- Migration: Add Spotlight Search Columns to Documents Table
-- Date: 2025-01-06
-- Description: Adds columns for Vertex AI integration and enhanced metadata storage

-- Add new columns for spotlight search functionality
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS keywords TEXT[],
ADD COLUMN IF NOT EXISTS vertex_corpus_id TEXT,
ADD COLUMN IF NOT EXISTS vertex_document_id TEXT,
ADD COLUMN IF NOT EXISTS file_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS column_headers TEXT[],
ADD COLUMN IF NOT EXISTS row_count INTEGER;

-- Add comments to explain column purposes
COMMENT ON COLUMN public.documents.summary IS 'AI-generated summary of document content for quick preview';
COMMENT ON COLUMN public.documents.keywords IS 'Extracted keywords for improved search and categorization';
COMMENT ON COLUMN public.documents.vertex_corpus_id IS 'Vertex AI RAG Engine corpus ID for semantic search';
COMMENT ON COLUMN public.documents.vertex_document_id IS 'Vertex AI RAG Engine document ID for retrieval';
COMMENT ON COLUMN public.documents.file_type IS 'File type classification (e.g., pdf, csv, txt, docx)';
COMMENT ON COLUMN public.documents.column_headers IS 'For CSV/structured files: column names';
COMMENT ON COLUMN public.documents.row_count IS 'For CSV/structured files: number of data rows';

-- Create indexes for improved query performance
CREATE INDEX IF NOT EXISTS idx_documents_keywords 
  ON public.documents USING gin(keywords);

CREATE INDEX IF NOT EXISTS idx_documents_file_type 
  ON public.documents (file_type);

CREATE INDEX IF NOT EXISTS idx_documents_vertex 
  ON public.documents (vertex_corpus_id, vertex_document_id);

CREATE INDEX IF NOT EXISTS idx_documents_summary_fts
  ON public.documents USING gin(to_tsvector('english', COALESCE(summary, '')));

-- Create index for fuzzy filename search
CREATE INDEX IF NOT EXISTS idx_documents_readable_filename_trgm
  ON public.documents USING gin(readable_filename gin_trgm_ops);

-- Enable pg_trgm extension if not already enabled (for fuzzy search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verification query to check new columns
-- Uncomment to run after migration:
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'documents' 
--   AND column_name IN ('summary', 'keywords', 'vertex_corpus_id', 'vertex_document_id', 'file_type', 'column_headers', 'row_count')
-- ORDER BY column_name;

