"""
Vertex AI Ingestion Service for Spotlight Search

Handles document ingestion using Google Vertex AI RAG Engine for unstructured data
and metadata extraction for structured data (CSVs).
"""

import os
import io
import csv
import traceback
from typing import Dict, List, Optional, Any
from pathlib import Path
from tempfile import NamedTemporaryFile

from injector import inject
from google.cloud import aiplatform
from google.api_core import exceptions as google_exceptions
import vertexai
from vertexai import rag
from vertexai.generative_models import GenerativeModel
import pandas as pd
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.database.aws import AWSStorage


class VertexIngestionService:
    """Service for ingesting documents using Vertex AI RAG Engine."""

    @inject
    def __init__(self, sql_db: SQLDatabase, aws_storage: AWSStorage):
        """Initialize Vertex AI ingestion service.
        
        Args:
            sql_db: SQL database instance for metadata storage
            aws_storage: AWS/S3 storage instance for file access
        """
        self.sql_db = sql_db
        self.aws_storage = aws_storage
        
        # Initialize Vertex AI
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        self.location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        self.corpus_display_name = os.getenv('VERTEX_RAG_CORPUS_NAME', 'aganswers-documents')
        self.vertex_enabled = False
        
        if self.project_id:
            try:
                vertexai.init(project=self.project_id, location=self.location)
                aiplatform.init(project=self.project_id, location=self.location)
                self.text_model = GenerativeModel(os.getenv('VERTEX_TEXT_MODEL', 'gemini-2.5-flash-lite'))
                self.vertex_enabled = True
            except Exception as e:
                print(f"⚠️ Vertex initialization failed, falling back to local ingestion: {e}")
        else:
            print('⚠️ GOOGLE_CLOUD_PROJECT_ID not set. Vertex ingestion disabled; using local fallback ingestion.')
            self.text_model = None
        
        openai_key = (os.getenv('AGANSWERS_OPENAI_KEY') or os.getenv('OPENAI_API_KEY'))
        self.openai_embeddings: Optional[OpenAIEmbeddings] = None
        if openai_key:
            self.openai_embeddings = OpenAIEmbeddings(api_key=SecretStr(openai_key))
        
        # Track corpus by course name
        self._corpus_cache: Dict[str, Any] = {}

    def _get_file_type(self, filename: str) -> str:
        """Determine file type from filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            File type string (e.g., 'pdf', 'csv', 'txt')
        """
        ext = Path(filename).suffix.lower()
        return ext[1:] if ext else 'unknown'

    def _is_structured_data(self, file_type: str) -> bool:
        """Check if file type is structured data.
        
        Args:
            file_type: File extension/type
            
        Returns:
            True if structured data (CSV, Excel, etc.)
        """
        structured_types = {'csv', 'xlsx', 'xls', 'json', 'xml'}
        return file_type in structured_types

    def _get_bucket_name(self) -> str:
        bucket = os.getenv('AGANSWERS_S3_BUCKET_NAME') or os.getenv('S3_BUCKET_NAME')
        if not bucket:
            raise ValueError('Missing S3 bucket name for ingestion')
        return bucket

    def create_or_get_corpus(self, course_name: str) -> Any:
        """Create or retrieve Vertex AI RAG corpus for a course.
        
        Args:
            course_name: Name of the course/project
            
        Returns:
            Vertex AI RAG corpus object
        """
        # Check cache first
        if course_name in self._corpus_cache:
            return self._corpus_cache[course_name]
        
        try:
            # Try to list existing corpora and find matching one
            corpus_display_name = f"{self.corpus_display_name}-{course_name}"
            
            try:
                # List corpora to find existing one
                corpora = rag.list_corpora()
                for corpus in corpora:
                    if corpus.display_name == corpus_display_name:
                        print(f"✅ Found existing corpus: {corpus.name}")
                        self._corpus_cache[course_name] = corpus
                        return corpus
            except Exception as e:
                print(f"Error listing corpora: {e}")
            
            # Create new corpus if not found
            print(f"📦 Creating new RAG corpus: {corpus_display_name}")
            
            # Create corpus with managed database
            # Vertex AI will use the default text-multilingual-embedding-002 model
            # which provides excellent multilingual support
            embedding_model_config = rag.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                    publisher_model="publishers/google/models/gemini-embedding-001"
                )
            )
            corpus = rag.create_corpus(
                display_name=corpus_display_name,
                description=f"Document corpus for {course_name} project",
                # backend_config=rag.RagVectorDbConfig(
                #     rag_embedding_model_config=embedding_model_config
                # ),
            )
            
            print(f"✅ Created corpus: {corpus.name}")
            self._corpus_cache[course_name] = corpus
            return corpus
            
        except Exception as e:
            print(f"❌ Error creating/getting corpus: {e}")
            traceback.print_exc()
            raise

    def ingest_unstructured_document(
        self, 
        course_name: str, 
        s3_path: str, 
        readable_filename: str
    ) -> Dict[str, Any]:
        """Ingest unstructured document to Vertex AI RAG Engine.
        
        Args:
            course_name: Course/project name
            s3_path: S3 path to document
            readable_filename: Human-readable filename
            
        Returns:
            Dictionary with ingestion results including vertex_document_id
        """
        try:
            print(f"📄 Ingesting unstructured document: {readable_filename}")
            
            # Get or create corpus
            corpus = self.create_or_get_corpus(course_name)
            
            # Get GCS bucket for Vertex AI
            gcs_bucket = os.getenv('VERTEX_GCS_BUCKET')
            
            # Initialize variables
            content_sample = ""
            rag_file_name = None
            
            if gcs_bucket:
                # Use import_files with GCS path (avoids OAuth scope issues)
                print(f"Using GCS import method for {readable_filename}")
                
                # Copy file from S3 to GCS
                from google.cloud import storage
                gcs_client = storage.Client(project=self.project_id)
                gcs_bucket_obj = gcs_client.bucket(gcs_bucket)
                
                # Download from S3
                bucket_name = self._get_bucket_name()
                with NamedTemporaryFile(suffix=Path(s3_path).suffix, delete=False) as tmp_file:
                    self.aws_storage.s3_client.download_fileobj(
                        Bucket=bucket_name,
                        Key=s3_path,
                        Fileobj=tmp_file
                    )
                    tmp_file.flush()
                    tmp_file_path = tmp_file.name
                
                # Extract metadata before uploading
                with open(tmp_file_path, 'rb') as f:
                    content_sample = self._extract_content_sample(f, Path(s3_path).suffix)
                
                # Upload to GCS
                gcs_path = f"vertex-rag/{course_name}/{readable_filename}"
                blob = gcs_bucket_obj.blob(gcs_path)
                blob.upload_from_filename(tmp_file_path)
                os.unlink(tmp_file_path)
                
                print(f"✅ Copied to GCS: gs://{gcs_bucket}/{gcs_path}")
                
                # Import from GCS using import_files
                rag.import_files(
                    corpus.name,
                    [f"gs://{gcs_bucket}/{gcs_path}"],
                    transformation_config=rag.TransformationConfig(
                        chunking_config=rag.ChunkingConfig(
                            chunk_size=512,
                            chunk_overlap=100,
                        ),
                    ),
                )
                
                # List files to get the document ID
                files = rag.list_files(corpus_name=corpus.name)
                for f in files:
                    if readable_filename in f.display_name:
                        rag_file_name = f.name
                        break
                
                print(f"✅ Imported to Vertex RAG: {rag_file_name}")
                
            else:
                # Fallback to upload_file (requires proper OAuth scopes)
                print(f"Using upload_file method for {readable_filename}")
                bucket_name = self._get_bucket_name()
                with NamedTemporaryFile(suffix=Path(s3_path).suffix) as tmp_file:
                    self.aws_storage.s3_client.download_fileobj(
                        Bucket=bucket_name,
                        Key=s3_path,
                        Fileobj=tmp_file
                    )
                    tmp_file.flush()
                    tmp_file.seek(0)
                    
                    rag_file = rag.upload_file(
                        corpus_name=corpus.name,
                        path=tmp_file.name,
                        display_name=readable_filename,
                        description=f"Document from {course_name}: {readable_filename}"
                    )
                    
                    print(f"✅ Uploaded to Vertex RAG: {rag_file.name}")
                    rag_file_name = rag_file.name
                    
                    tmp_file.seek(0)
                    content_sample = self._extract_content_sample(tmp_file, Path(s3_path).suffix)
            
            # Extract metadata using Vertex AI
            metadata = self.extract_metadata_with_vertex(content_sample, readable_filename)
            
            return {
                'vertex_corpus_id': corpus.name,
                'vertex_document_id': rag_file_name,
                'summary': metadata.get('summary'),
                'keywords': metadata.get('keywords', []),
            }
                
        except Exception as e:
            print(f"❌ Error ingesting unstructured document: {e}")
            traceback.print_exc()
            raise

    def _extract_content_sample(self, file_obj, suffix: str, max_chars: int = 5000) -> str:
        """Extract a sample of content from file for metadata generation.
        
        Args:
            file_obj: File object to read from
            suffix: File extension
            max_chars: Maximum characters to extract
            
        Returns:
            Sample text content
        """
        try:
            if suffix.lower() in ['.txt', '.md']:
                content = file_obj.read(max_chars)
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                return content
            elif suffix.lower() == '.pdf':
                # For PDFs, return placeholder - Vertex will handle OCR
                return f"PDF document (Vertex AI will process content)"
            else:
                return f"Document type: {suffix}"
        except Exception as e:
            print(f"⚠️ Error extracting content sample: {e}")
            return ""

    def extract_metadata_with_vertex(self, content: str, filename: str) -> Dict[str, Any]:
        """Extract metadata (summary, keywords) using Vertex AI.
        
        Args:
            content: Document content or description
            filename: Document filename for context
            
        Returns:
            Dictionary with 'summary' and 'keywords'
        """
        try:
            if not self.text_model:
                return {
                    'summary': f"Document: {filename}",
                    'keywords': [Path(filename).stem]
                }

            prompt = f"""Analyze this document and provide:
1. A concise 2-3 sentence summary
2. A list of 5-10 relevant keywords

Document: {filename}
Content sample: {content[:2000]}

Respond in this exact format:
SUMMARY: [your summary here]
KEYWORDS: keyword1, keyword2, keyword3, keyword4, keyword5"""

            response = self.text_model.generate_content(prompt)
            text = response.text.strip()
            
            # Parse response
            summary = ""
            keywords = []
            
            lines = text.split('\n')
            for line in lines:
                if line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                elif line.startswith('KEYWORDS:'):
                    keywords_str = line.replace('KEYWORDS:', '').strip()
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
            
            return {
                'summary': summary or "No summary available",
                'keywords': keywords[:10]  # Limit to 10 keywords
            }
            
        except Exception as e:
            print(f"⚠️ Error extracting metadata: {e}")
            # Return defaults on error
            return {
                'summary': f"Document: {filename}",
                'keywords': [Path(filename).stem]
            }

    def extract_csv_metadata(self, s3_path: str) -> Dict[str, Any]:
        """Extract metadata from CSV file.
        
        Args:
            s3_path: S3 path to CSV file
            
        Returns:
            Dictionary with column_headers, row_count, and sample data
        """
        try:
            print(f"📊 Extracting CSV metadata: {s3_path}")
            
            bucket_name = self._get_bucket_name()
            
            # Download CSV from S3
            with NamedTemporaryFile(suffix='.csv') as tmp_file:
                self.aws_storage.s3_client.download_fileobj(
                    Bucket=bucket_name,
                    Key=s3_path,
                    Fileobj=tmp_file
                )
                tmp_file.flush()
                tmp_file.seek(0)
                
                # Read CSV with pandas
                try:
                    df = pd.read_csv(tmp_file.name, nrows=5)  # Read first 5 rows for sample
                    
                    column_headers = df.columns.tolist()
                    
                    # Get actual row count
                    tmp_file.seek(0)
                    df_full = pd.read_csv(tmp_file.name)
                    row_count = len(df_full)
                    
                    # Generate summary
                    summary = f"CSV file with {row_count} rows and {len(column_headers)} columns"
                    
                    # Generate keywords from column names
                    keywords = [col.lower().replace('_', ' ') for col in column_headers[:10]]
                    
                    return {
                        'column_headers': column_headers,
                        'row_count': row_count,
                        'summary': summary,
                        'keywords': keywords
                    }
                    
                except Exception as e:
                    print(f"⚠️ Error parsing CSV: {e}")
                    return {
                        'column_headers': [],
                        'row_count': 0,
                        'summary': f"CSV file (parsing error: {str(e)[:100]})",
                        'keywords': ['csv', 'data']
                    }
                    
        except Exception as e:
            print(f"❌ Error extracting CSV metadata: {e}")
            traceback.print_exc()
            raise

    def ingest_plain_text_document(
        self,
        course_name: str,
        s3_path: str,
        readable_filename: str
    ) -> Dict[str, Any]:
        """Fallback ingestion that converts HTML to text and stores contexts locally."""
        try:
            bucket_name = self._get_bucket_name()
            response = self.aws_storage.s3_client.get_object(
                Bucket=bucket_name,
                Key=s3_path,
            )
            html_bytes = response['Body'].read()
            html = html_bytes.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script', 'style', 'noscript']):
                try:
                    tag.decompose()
                except Exception:
                    pass
            text = soup.get_text(separator='\n')
            text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
            splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
            chunks = splitter.split_text(text)
            contexts: List[Dict[str, Any]] = []
            embeddings: List[List[float]] = []
            if self.openai_embeddings and chunks:
                try:
                    embeddings = self.openai_embeddings.embed_documents(chunks)
                except Exception as e:
                    print(f"⚠️ Embedding generation failed: {e}")
                    embeddings = []
            for idx, chunk in enumerate(chunks):
                ctx = {
                    'text': chunk,
                    'chunk_index': idx,
                    'pagenumber': '',
                    'timestamp': '',
                    's3_path': s3_path,
                    'readable_filename': readable_filename,
                }
                if embeddings and idx < len(embeddings):
                    ctx['embedding'] = embeddings[idx]
                contexts.append(ctx)
            summary = text[:500] + ('…' if len(text) > 500 else '') if text else f'Document: {readable_filename}'
            keywords = list({word.lower() for word in summary.split()[:10]}) if summary else []
            keywords = keywords[:10]
            metadata = {
                'summary': summary or f'Document: {readable_filename}',
                'keywords': keywords,
                'contexts': contexts,
            }
            return metadata
        except Exception as e:
            print(f"❌ Error in local ingestion fallback: {e}")
            traceback.print_exc()
            raise

    def store_document_metadata(
        self,
        course_name: str,
        s3_path: str,
        readable_filename: str,
        file_type: str,
        metadata: Dict[str, Any]
    ) -> Any:
        """Store document metadata in Supabase.
        
        Args:
            course_name: Course/project name
            s3_path: S3 path to document
            readable_filename: Human-readable filename
            file_type: File type (pdf, csv, txt, etc.)
            metadata: Metadata dictionary from ingestion
            
        Returns:
            Supabase insert response
        """
        try:
            contexts = metadata.get('contexts', []) if metadata else []
            document_data = {
                'course_name': course_name,
                's3_path': s3_path,
                'readable_filename': readable_filename,
                'file_type': file_type,
                'summary': metadata.get('summary'),
                'keywords': metadata.get('keywords', []),
                'vertex_corpus_id': metadata.get('vertex_corpus_id'),
                'vertex_document_id': metadata.get('vertex_document_id'),
                'column_headers': metadata.get('column_headers'),
                'row_count': metadata.get('row_count'),
                'url': '',
                'base_url': '',
                'contexts': contexts,
            }
            
            # Remove None values
            document_data = {k: v for k, v in document_data.items() if v is not None}
            
            response = self.sql_db.supabase_client.table('documents').insert(document_data).execute()
            
            print(f"✅ Stored metadata in Supabase for: {readable_filename}")
            return response
            
        except Exception as e:
            print(f"❌ Error storing metadata: {e}")
            traceback.print_exc()
            raise

    def ingest_document(
        self,
        course_name: str,
        s3_path: str,
        readable_filename: str
    ) -> Dict[str, Any]:
        """Main ingestion method - routes to appropriate handler.
        
        Args:
            course_name: Course/project name
            s3_path: S3 path to document
            readable_filename: Human-readable filename
            
        Returns:
            Dictionary with ingestion status and metadata
        """
        try:
            print(f"\n{'='*60}")
            print(f"🚀 Starting ingestion: {readable_filename}")
            print(f"   Course: {course_name}")
            print(f"   S3 Path: {s3_path}")
            print(f"{'='*60}\n")
            
            # Determine file type
            file_type = self._get_file_type(readable_filename)
            is_structured = self._is_structured_data(file_type)
            
            metadata = {}
            
            if is_structured:
                # Structured data - extract metadata only
                print(f"📊 Processing as structured data ({file_type})")
                if file_type == 'csv':
                    metadata = self.extract_csv_metadata(s3_path)
                else:
                    # For other structured formats, basic metadata
                    metadata = {
                        'summary': f"{file_type.upper()} file: {readable_filename}",
                        'keywords': [file_type, 'structured data']
                    }
            else:
                # Unstructured data
                print(f"📄 Processing as unstructured data ({file_type})")
                if self.vertex_enabled:
                    try:
                        metadata = self.ingest_unstructured_document(
                            course_name, s3_path, readable_filename
                        )
                    except Exception as vertex_error:
                        print(f"⚠️ Vertex ingestion failed, using local fallback: {vertex_error}")
                        metadata = self.ingest_plain_text_document(
                            course_name, s3_path, readable_filename
                        )
                else:
                    metadata = self.ingest_plain_text_document(
                        course_name, s3_path, readable_filename
                    )
            
            # Store metadata in Supabase
            self.store_document_metadata(
                course_name, s3_path, readable_filename, file_type, metadata
            )
            
            print(f"\n✅ Ingestion complete: {readable_filename}\n")
            
            return {
                'success': True,
                'file_type': file_type,
                'is_structured': is_structured,
                'metadata': metadata
            }
            
        except Exception as e:
            error_msg = f"Failed to ingest {readable_filename}: {str(e)}"
            print(f"\n❌ {error_msg}\n")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': error_msg,
                'traceback': traceback.format_exc()
            }
