"""
File Agent Service for handling CSV files and data processing with LLM integration.
"""

import os
import io
import boto3
import pandas as pd
import supabase
from typing import List, Dict, Any, Optional
from injector import inject
from tempfile import NamedTemporaryFile
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.agents.tools.file.agent import (
    prepare_file_agent,
    update_agent_dataframes,
    add_dataframe,
    clear_dataframes,
    get_current_dataframes
)


class FileAgentService:
    """Service for managing file agent operations with CSV files from R2 S3."""
    
    @inject
    def __init__(self, sql_db: SQLDatabase):
        self.sql_db = sql_db
        self.current_agent = None  # Store the current file agent instance
        
        # Initialize R2 S3 client
        self.r2_client = boto3.client(
            's3',
            endpoint_url=os.environ.get('CLOUDFLARE_R2_ENDPOINT'),
            aws_access_key_id=os.environ.get('CLOUDFLARE_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('CLOUDFLARE_SECRET_ACCESS_KEY'),
            region_name='auto'
        )
        
        # Initialize Supabase storage client
        supabase_url = os.environ.get('AGANSWERS_SUPABASE_URL') or os.environ['SUPABASE_URL']
        supabase_key = (os.environ.get('AGANSWERS_SUPABASE_API_KEY') or
                        os.environ.get('AGANSWERS_SUPABASE_SERVICE_ROLE_KEY') or
                        os.environ['SUPABASE_API_KEY'])
        self.supabase_client = supabase.create_client(
            supabase_url=supabase_url,
            supabase_key=supabase_key
        )
        
        # R2 bucket name
        self.r2_bucket_name = os.environ.get('AGANSWERS_S3_BUCKET_NAME', 'aganswers')
        
        # Thread pool for parallel CSV loading
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def get_csv_files_for_course(self, course_name: str) -> List[Dict[str, Any]]:
        """
        Query the documents table for CSV files belonging to a course.
        Uses the optimized index for CSV files.
        """
        try:
            # Use the optimized SQL method
            response = self.sql_db.getCSVFilesForCourse(course_name, limit=10)
            return response.data if response.data else []
        except Exception as e:
            print(f"Error querying CSV files: {e}")
            return []
    
    def load_csv_from_r2(self, s3_path: str, readable_filename: str) -> Optional[pd.DataFrame]:
        """Load a single CSV file from R2 S3."""
        try:
            # Get object from R2
            response = self.r2_client.get_object(
                Bucket=self.r2_bucket_name,
                Key=s3_path
            )
            
            # Read CSV directly from bytes
            csv_content = response['Body'].read()
            df = pd.read_csv(io.BytesIO(csv_content))
            
            return df
        except Exception as e:
            print(f"Error loading CSV from R2 {s3_path}: {e}")
            return None
    
    async def load_csvs_for_course_async(self, course_name: str) -> Dict[str, pd.DataFrame]:
        """
        Asynchronously load all CSV files for a course.
        Returns a dictionary mapping filename to dataframe.
        """
        csv_files = self.get_csv_files_for_course(course_name)
        
        if not csv_files:
            print(f"No CSV files found for course: {course_name}")
            return {}
        
        print(f"Found {len(csv_files)} CSV files for course: {course_name}")
        
        # Create tasks for parallel loading
        loop = asyncio.get_event_loop()
        tasks = []
        
        for csv_file in csv_files[:10]:  # Limit to first 10 CSVs for performance
            s3_path = csv_file['s3_path']
            readable_filename = csv_file['readable_filename'] or os.path.basename(s3_path)
            
            task = loop.run_in_executor(
                self.executor,
                self.load_csv_from_r2,
                s3_path,
                readable_filename
            )
            tasks.append((readable_filename, task))
        
        # Wait for all tasks to complete
        loaded_dataframes = {}
        for filename, task in tasks:
            df = await task
            if df is not None:
                loaded_dataframes[filename] = df
                print(f"Loaded CSV: {filename} with shape {df.shape}")
        
        return loaded_dataframes
    
    def load_csvs_for_course(self, course_name: str) -> Dict[str, pd.DataFrame]:
        """
        Synchronous wrapper for loading CSV files.
        """
        return asyncio.run(self.load_csvs_for_course_async(course_name))
    
    def prepare_file_agent(self, course_name: str, conversation_id: str) -> bool:
        """
        Prepare the file agent with CSV files and Google Drive files for a course.
        Sets up the plot save directory for the conversation.
        """
        try:
            # Clear any existing dataframes
            clear_dataframes()
            
            # Load CSV files from R2
            dataframes = self.load_csvs_for_course(course_name)

            # Also load recent DigiDocs (OCR HTML) as plain-text DataFrames from Supabase
            try:
                digidocs_frames = self._load_digidocs_texts_for_course(course_name, limit=5)
                if digidocs_frames:
                    dataframes.update(digidocs_frames)
                    print(f"✅ Added {len(digidocs_frames)} DigiDocs text files to agent")
            except Exception as e:
                print(f"⚠️  Could not load DigiDocs text files: {e}")
            
            # Load Google Drive files if project has a group
            try:
                from ai_ta_backend.integrations.google_groups import GoogleGroupsService
                from ai_ta_backend.agents.tools.drive.agent import load_drive_files_for_project
                
                # Get project's group email
                project = self.sql_db.supabase_client.table('projects')\
                    .select('group_email')\
                    .eq('course_name', course_name)\
                    .single()\
                    .execute()
                
                if project.data and project.data.get('group_email'):
                    group_email = project.data['group_email']
                    
                    # Handle case where group_email might be stored as JSON string
                    if isinstance(group_email, str) and group_email.startswith('"') and group_email.endswith('"'):
                        import json
                        group_email = json.loads(group_email)
                    
                    print(f"📁 Loading Drive files for group: {group_email}")
                    
                    drive_dataframes = load_drive_files_for_project(course_name, group_email)
                    
                    # Merge Drive dataframes with CSV dataframes
                    if drive_dataframes:
                        dataframes.update(drive_dataframes)
                        print(f"✅ Added {len(drive_dataframes)} Drive files to agent")
                        
            except Exception as e:
                print(f"⚠️  Could not load Drive files: {e}")
                # Continue with just CSV files
            
            if not dataframes:
                print(f"No files to load for course: {course_name}")
                # Still prepare the agent even with no files
                self.current_agent = prepare_file_agent({}, conversation_id, self.supabase_client)
                return True
            
            # Prepare the agent with the loaded dataframes
            self.current_agent = prepare_file_agent(dataframes, conversation_id, self.supabase_client)
            
            print(f"File agent prepared with {len(dataframes)} dataframes")
            
            # Print dataframes info for debugging
            for filename, df in dataframes.items():
                df_type = "GeoDataFrame" if hasattr(df, 'crs') else "DataFrame"
                print(f"  - Loaded: {filename} ({df_type}, {df.shape})")
            
            return True
            
        except Exception as e:
            print(f"Error preparing file agent: {e}")
            return False

    def _load_digidocs_texts_for_course(self, course_name: str, limit: int = 5) -> Dict[str, pd.DataFrame]:
        """
        Load recent OCR HTML ingested documents from Supabase and convert their contexts
        to pandas DataFrames so the file_agent can use them in chat.

        The resulting DataFrame has columns: ['chunk_index', 'text', 's3_path', 'readable_filename']
        and is named using the readable filename.
        """
        try:
            docs_table = os.environ.get('SUPABASE_DOCUMENTS_TABLE', 'documents')
            # Fetch recent DigiDocs HTML documents for the course
            resp = self.sql_db.supabase_client.table(docs_table) \
                .select('readable_filename,s3_path,contexts') \
                .eq('course_name', course_name) \
                .like('s3_path', 'courses/' + course_name + '/%html') \
                .order('created_at', desc=True) \
                .limit(limit) \
                .execute()

            rows = resp.data or []
            frames: Dict[str, pd.DataFrame] = {}
            for row in rows:
                contexts = row.get('contexts') or []
                if not isinstance(contexts, list):
                    continue
                # Build a DataFrame from contexts array
                records = []
                for c in contexts:
                    try:
                        records.append({
                            'chunk_index': c.get('chunk_index'),
                            'text': c.get('text') or '',
                            's3_path': row.get('s3_path'),
                            'readable_filename': row.get('readable_filename') or os.path.basename(row.get('s3_path') or ''),
                        })
                    except Exception:
                        continue
                if not records:
                    continue
                df = pd.DataFrame.from_records(records)
                # Use a clean filename key for the agent environment
                rf = row.get('readable_filename') or os.path.basename(row.get('s3_path') or '')
                key = f"{rf.replace('/', '_')}_text"
                frames[key] = df
            return frames
        except Exception as e:
            print(f"Error loading DigiDocs texts: {e}")
            return {}
    
    def save_plot_to_supabase(self, plot_path: str, conversation_id: str) -> Optional[str]:
        """
        Save a matplotlib plot to Supabase storage.
        Returns the public URL if successful.
        """
        try:
            bucket_name = 'llm_output'
            
            # Construct the storage path
            storage_path = f"{conversation_id}/graphs/{os.path.basename(plot_path)}"
            
            # Read the plot file
            with open(plot_path, 'rb') as f:
                plot_data = f.read()
            
            # Upload to Supabase storage
            response = self.supabase_client.storage.from_(bucket_name).upload(
                path=storage_path,
                file=plot_data,
                file_options={"content-type": "image/png"}
            )
            
            # Get public URL
            public_url = self.supabase_client.storage.from_(bucket_name).get_public_url(storage_path)
            
            print(f"Plot saved to Supabase: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"Error saving plot to Supabase: {e}")
            return None
    
    def save_csv_to_supabase(self, df: pd.DataFrame, filename: str, conversation_id: str) -> Optional[str]:
        """
        Save a dataframe as CSV to Supabase storage.
        Returns the public URL if successful.
        """
        try:
            bucket_name = 'llm_output'
            
            # Construct the storage path
            storage_path = f"{conversation_id}/csvs/{filename}"
            
            # Convert dataframe to CSV bytes
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue().encode('utf-8')
            
            # Upload to Supabase storage
            response = self.supabase_client.storage.from_(bucket_name).upload(
                path=storage_path,
                file=csv_data,
                file_options={"content-type": "text/csv"}
            )
            
            # Get public URL
            public_url = self.supabase_client.storage.from_(bucket_name).get_public_url(storage_path)
            
            print(f"CSV saved to Supabase: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"Error saving CSV to Supabase: {e}")
            return None
    
    def process_file_agent_outputs(self, conversation_id: str) -> Dict[str, List[str]]:
        """
        Process and save any outputs from the file agent.
        Returns URLs of saved files.
        """
        saved_files = {
            'plots': [],
            'csvs': []
        }
        
        # Check for plots in the plot directory
        plot_dir = f"plots/{conversation_id}"
        if os.path.exists(plot_dir):
            for filename in os.listdir(plot_dir):
                if filename.endswith(('.png', '.jpg', '.svg')):
                    plot_path = os.path.join(plot_dir, filename)
                    url = self.save_plot_to_supabase(plot_path, conversation_id)
                    if url:
                        saved_files['plots'].append(url)
        
        return saved_files
    
    def cleanup_temp_files(self, conversation_id: str):
        """Clean up temporary files created during processing."""
        import shutil
        
        # Clean up plot directory
        plot_dir = f"plots/{conversation_id}"
        if os.path.exists(plot_dir):
            try:
                shutil.rmtree(plot_dir)
                print(f"Cleaned up plot directory: {plot_dir}")
            except Exception as e:
                print(f"Error cleaning up plot directory: {e}")
