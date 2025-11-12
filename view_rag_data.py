#!/usr/bin/env python3
"""
View Vertex AI RAG Corpus and Data
Shows all corpora, files, and their details
"""

import os
import sys
import dotenv
from datetime import datetime

dotenv.load_dotenv()

def format_timestamp(timestamp):
    """Format timestamp for display"""
    if hasattr(timestamp, 'seconds'):
        dt = datetime.fromtimestamp(timestamp.seconds)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return str(timestamp)

def view_all_corpora():
    """List all RAG corpora and their contents"""
    print("="*80)
    print("  VERTEX AI RAG DATA VIEWER")
    print("="*80)
    
    try:
        from vertexai import rag
        import vertexai
        
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        
        print(f"\n📋 Project: {project_id}")
        print(f"📍 Location: {location}")
        
        # Initialize
        vertexai.init(project=project_id, location=location)
        
        # List all corpora
        print(f"\n{'='*80}")
        print("  📦 RAG CORPORA")
        print(f"{'='*80}\n")
        
        corpora = list(rag.list_corpora())
        
        if not corpora:
            print("❌ No corpora found")
            return
        
        print(f"Found {len(corpora)} corpus/corpora:\n")
        
        for idx, corpus in enumerate(corpora, 1):
            print(f"\n{'─'*80}")
            print(f"📦 CORPUS #{idx}")
            print(f"{'─'*80}")
            print(f"   Name: {corpus.display_name}")
            print(f"   ID: {corpus.name}")
            
            if hasattr(corpus, 'description') and corpus.description:
                print(f"   Description: {corpus.description}")
            
            if hasattr(corpus, 'create_time'):
                print(f"   Created: {format_timestamp(corpus.create_time)}")
            
            # List files in this corpus
            print(f"\n   📄 FILES IN THIS CORPUS:")
            print(f"   {'-'*76}")
            
            try:
                files = list(rag.list_files(corpus_name=corpus.name))
                
                if not files:
                    print(f"   (No files uploaded yet)")
                else:
                    print(f"   Total files: {len(files)}\n")
                    
                    for file_idx, rag_file in enumerate(files, 1):
                        print(f"   {file_idx}. {rag_file.display_name}")
                        print(f"      ID: {rag_file.name}")
                        
                        if hasattr(rag_file, 'size_bytes'):
                            size_mb = rag_file.size_bytes / (1024 * 1024)
                            print(f"      Size: {size_mb:.2f} MB")
                        
                        if hasattr(rag_file, 'create_time'):
                            print(f"      Uploaded: {format_timestamp(rag_file.create_time)}")
                        
                        if hasattr(rag_file, 'description') and rag_file.description:
                            print(f"      Description: {rag_file.description}")
                        
                        print()
                        
            except Exception as e:
                print(f"   ⚠️  Error listing files: {e}")
        
        print(f"\n{'='*80}")
        print("  🔗 VIEW IN CONSOLE")
        print(f"{'='*80}")
        print(f"\nVertex AI Console:")
        print(f"https://console.cloud.google.com/vertex-ai?project={project_id}")
        print(f"\nAgent Builder (RAG Data Stores):")
        print(f"https://console.cloud.google.com/gen-app-builder/engines?project={project_id}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def search_corpus(query: str):
    """Test search across all corpora"""
    print(f"\n{'='*80}")
    print(f"  🔍 SEARCH TEST: '{query}'")
    print(f"{'='*80}\n")
    
    try:
        from vertexai import rag
        import vertexai
        
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        
        vertexai.init(project=project_id, location=location)
        
        corpora = list(rag.list_corpora())
        
        for corpus in corpora:
            print(f"\n📦 Searching in: {corpus.display_name}")
            print(f"{'─'*80}")
            
            try:
                response = rag.retrieval_query(
                    rag_resources=[rag.RagResource(rag_corpus=corpus.name)],
                    text=query,
                    rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
                )
                
                if response and hasattr(response, 'contexts') and response.contexts:
                    print(f"✅ Found {len(response.contexts.contexts)} result(s)")
                    
                    for idx, context in enumerate(response.contexts.contexts, 1):
                        print(f"\n   Result {idx}:")
                        if hasattr(context, 'source_uri'):
                            print(f"   Source: {context.source_uri}")
                        if hasattr(context, 'text'):
                            preview = context.text[:200] + "..." if len(context.text) > 200 else context.text
                            print(f"   Text: {preview}")
                else:
                    print(f"   No results found")
                    
            except Exception as e:
                print(f"   ⚠️  Search error: {e}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def get_corpus_stats():
    """Get statistics about all corpora"""
    print(f"\n{'='*80}")
    print("  📊 CORPUS STATISTICS")
    print(f"{'='*80}\n")
    
    try:
        from vertexai import rag
        import vertexai
        
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('VERTEX_AI_LOCATION', 'us-east4')
        
        vertexai.init(project=project_id, location=location)
        
        corpora = list(rag.list_corpora())
        
        total_files = 0
        total_size = 0
        
        stats = []
        
        for corpus in corpora:
            try:
                files = list(rag.list_files(corpus_name=corpus.name))
                file_count = len(files)
                total_files += file_count
                
                corpus_size = 0
                for f in files:
                    if hasattr(f, 'size_bytes'):
                        corpus_size += f.size_bytes
                
                total_size += corpus_size
                
                stats.append({
                    'name': corpus.display_name,
                    'files': file_count,
                    'size_mb': corpus_size / (1024 * 1024)
                })
                
            except Exception as e:
                stats.append({
                    'name': corpus.display_name,
                    'files': 'Error',
                    'size_mb': 0
                })
        
        # Print table
        print(f"{'Corpus Name':<40} {'Files':<10} {'Size (MB)':<15}")
        print(f"{'-'*40} {'-'*10} {'-'*15}")
        
        for stat in stats:
            files_str = str(stat['files'])
            size_str = f"{stat['size_mb']:.2f}" if isinstance(stat['size_mb'], (int, float)) else "N/A"
            print(f"{stat['name']:<40} {files_str:<10} {size_str:<15}")
        
        print(f"{'-'*40} {'-'*10} {'-'*15}")
        print(f"{'TOTAL':<40} {total_files:<10} {total_size/(1024*1024):.2f}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'search' and len(sys.argv) > 2:
            query = ' '.join(sys.argv[2:])
            search_corpus(query)
        elif command == 'stats':
            get_corpus_stats()
        else:
            print(f"Unknown command: {command}")
            print("\nUsage:")
            print("  python view_rag_data.py              # View all corpora and files")
            print("  python view_rag_data.py stats        # Show statistics")
            print("  python view_rag_data.py search <query>  # Search across corpora")
    else:
        view_all_corpora()
        get_corpus_stats()

if __name__ == '__main__':
    main()



