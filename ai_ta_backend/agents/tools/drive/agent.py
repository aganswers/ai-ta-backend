"""
Google Drive agent for accessing and analyzing files shared with project groups.
"""

import io
from typing import Dict, Optional, Any
import pandas as pd

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from ai_ta_backend.integrations.google_groups import GoogleGroupsService
from ai_ta_backend.agents.tools.file.code_executor import (
    setup_execution_environment,
    run_code,
    set_plot_directory,
    generate_dataframes_info
)


def load_drive_files_for_project(project_name: str, group_email: str) -> Dict[str, pd.DataFrame]:
    """
    Load Google Drive files shared with a project's group into DataFrames.
    
    Args:
        project_name: Name of the project
        group_email: Google Group email for the project
        
    Returns:
        Dictionary mapping filename to DataFrame for supported file types
    """
    dataframes = {}
    
    try:
        groups_service = GoogleGroupsService()
        files = groups_service.list_files_shared_with_group(group_email)
        
        print(f"📁 Loading {len(files)} Drive files for project: {project_name}")
        
        for file_data in files:
            file_id = file_data['id']
            file_name = file_data['name']
            mime_type = file_data['mimeType']
            
            # Only process spreadsheet files
            if 'spreadsheet' in mime_type or mime_type == 'text/csv':
                try:
                    # Download file content
                    content = groups_service.get_file_content(file_id, mime_type)
                    
                    if content:
                        # Convert to DataFrame
                        if 'spreadsheet' in mime_type:
                            # Google Sheets exported as CSV
                            df = pd.read_csv(io.BytesIO(content))
                        elif mime_type == 'text/csv':
                            df = pd.read_csv(io.BytesIO(content))
                        else:
                            continue
                        
                        # Use filename as key (without extension for cleaner variable names)
                        clean_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                        # Sanitize for Python variable naming
                        clean_name = clean_name.replace(' ', '_').replace('-', '_')
                        clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '_')
                        
                        dataframes[clean_name] = df
                        print(f"✅ Loaded {file_name} as DataFrame '{clean_name}' ({len(df)} rows)")
                        
                except Exception as e:
                    print(f"⚠️  Failed to load file {file_name}: {e}")
                    continue
        
        print(f"✅ Successfully loaded {len(dataframes)} DataFrames from Drive")
        
    except Exception as e:
        print(f"❌ Error loading Drive files: {e}")
    
    return dataframes


def create_drive_agent(
    project_name: str,
    group_email: str,
    conversation_id: Optional[str] = None
) -> Agent:
    """
    Create a Google Drive agent for a specific project.
    
    Args:
        project_name: Name of the project
        group_email: Google Group email for the project
        conversation_id: Optional conversation ID for organizing outputs
        
    Returns:
        Configured Agent instance with access to project's Drive files
    """
    # Load Drive files into DataFrames
    dataframes = load_drive_files_for_project(project_name, group_email)
    
    # Setup execution environment
    setup_execution_environment(dataframes)
    
    # Set plot directory if conversation_id provided
    if conversation_id:
        plot_dir = f"plots/{conversation_id}"
        set_plot_directory(plot_dir)
    
    # Generate instruction with available data info
    df_info = generate_dataframes_info(dataframes)
    
    instruction = f"""You are a Google Drive data analysis agent for the project "{project_name}".

You have access to the following files shared with this project's Google Group ({group_email}):

{df_info}

Your capabilities:
1. Analyze data from Google Sheets and CSV files
2. Create visualizations and plots
3. Perform statistical analysis
4. Answer questions about the data
5. Generate insights and summaries

When analyzing data:
- Use the run_code tool to execute Python code
- DataFrames are already loaded and available as variables
- Save plots using plt.savefig() - they will be automatically captured
- Be precise and data-driven in your responses
- Show your work by explaining the code you run

Always scope your analysis to the files shared with this specific project."""

    # Create the run_code tool
    run_code_tool = FunctionTool(run_code)
    
    # Create and return the ADK agent
    agent = Agent(
        model="gemini-2.5-flash",
        name="google_drive_agent",
        instruction=instruction,
        tools=[run_code_tool]
    )
    
    return agent

