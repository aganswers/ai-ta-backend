"""
Test script to verify Google Drive integration end-to-end.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.integrations.google_groups import GoogleGroupsService
from ai_ta_backend.agents.tools.drive.agent import load_drive_files_for_project

def test_project_group_email(project_name="andrew"):
    """Test if project has a group email."""
    print(f"\n{'='*60}")
    print(f"Testing Project: {project_name}")
    print(f"{'='*60}\n")
    
    sql_db = SQLDatabase()
    
    # Check if project exists and has group_email
    try:
        project = sql_db.supabase_client.table('projects')\
            .select('id, course_name, group_email')\
            .eq('course_name', project_name)\
            .single()\
            .execute()
        
        if project.data:
            print(f"✅ Project found:")
            print(f"   ID: {project.data.get('id')}")
            print(f"   Name: {project.data.get('course_name')}")
            print(f"   Group Email: {project.data.get('group_email')}")
            
            group_email = project.data.get('group_email')
            
            if not group_email:
                print(f"\n⚠️  WARNING: Project has no group_email set!")
                print(f"   This project was created before the Google Drive integration.")
                print(f"   To fix: Manually set group_email to 'andrew@aganswers.ai' in Supabase")
                return None
            
            return group_email
        else:
            print(f"❌ Project '{project_name}' not found")
            return None
            
    except Exception as e:
        print(f"❌ Error checking project: {e}")
        return None


def test_list_drive_files(group_email):
    """Test listing files shared with the group."""
    print(f"\n{'='*60}")
    print(f"Testing Drive File Listing")
    print(f"{'='*60}\n")
    
    try:
        groups_service = GoogleGroupsService()
        files = groups_service.list_files_shared_with_group(group_email)
        
        print(f"✅ Found {len(files)} files shared with {group_email}:")
        for file in files:
            print(f"   📊 {file['name']} (ID: {file['id']})")
        
        return files
        
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_load_drive_files(project_name, group_email):
    """Test loading Drive files into DataFrames."""
    print(f"\n{'='*60}")
    print(f"Testing Drive File Loading")
    print(f"{'='*60}\n")
    
    try:
        dataframes = load_drive_files_for_project(project_name, group_email)
        
        if dataframes:
            print(f"✅ Loaded {len(dataframes)} DataFrames:")
            for name, df in dataframes.items():
                print(f"   📊 {name}: {df.shape[0]} rows × {df.shape[1]} columns")
                print(f"      Columns: {list(df.columns)[:5]}...")
        else:
            print(f"⚠️  No DataFrames loaded (files might not be spreadsheets)")
        
        return dataframes
        
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        import traceback
        traceback.print_exc()
        return {}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Google Drive Integration End-to-End Test")
    print("="*60)
    
    # Test 1: Check project has group_email
    group_email = test_project_group_email("andrew")
    
    if not group_email:
        print("\n" + "="*60)
        print("❌ TEST FAILED: Project has no group_email")
        print("="*60)
        exit(1)
    
    # Test 2: List files shared with group
    files = test_list_drive_files(group_email)
    
    if not files:
        print("\n" + "="*60)
        print("⚠️  No files shared with group (this is OK if none shared yet)")
        print("="*60)
        exit(0)
    
    # Test 3: Load files into DataFrames
    dataframes = test_load_drive_files("andrew", group_email)
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED")
    print("="*60)

