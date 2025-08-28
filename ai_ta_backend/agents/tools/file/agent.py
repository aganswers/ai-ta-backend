"""
File processing agent using Google ADK.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from typing import Dict, Any, Optional, Union
import pandas as pd
from .prompt import get_agent_prompt
from .code_executor import (
    setup_execution_environment,
    run_code,
    set_plot_directory,
    set_supabase_client,
    generate_dataframes_info
)


# Global dataframes storage for the file agent
_file_agent_dataframes = {}


def update_agent_dataframes(dataframes: Dict[str, Union[pd.DataFrame, Any]]):
    """Update the global dataframes for the file agent."""
    global _file_agent_dataframes
    _file_agent_dataframes.update(dataframes)


def add_dataframe(df: Union[pd.DataFrame, Any], filename: str):
    """Add a single dataframe to the file agent."""
    global _file_agent_dataframes
    _file_agent_dataframes[filename] = df


def clear_dataframes():
    """Clear all dataframes."""
    global _file_agent_dataframes
    _file_agent_dataframes = {}


def get_current_dataframes():
    """Get current dataframes."""
    global _file_agent_dataframes
    return _file_agent_dataframes


def create_file_agent(conversation_id: Optional[str] = None) -> Agent:
    """
    Create a new file agent instance with current dataframes.
    
    Args:
        conversation_id: Optional conversation ID for organizing outputs
    
    Returns:
        Configured Agent instance
    """
    global _file_agent_dataframes
    
    # Setup the execution environment with current dataframes
    setup_execution_environment(_file_agent_dataframes)
    
    # Set plot directory if conversation_id provided
    if conversation_id:
        plot_dir = f"plots/{conversation_id}"
        set_plot_directory(plot_dir)
    
    # Get the prompt with dataframe information
    instruction = get_agent_prompt(_file_agent_dataframes)
    
    # Create the run_code tool
    run_code_tool = FunctionTool(run_code)
    
    # Create and return the ADK agent
    agent = Agent(
        model="gemini-2.0-flash-exp",
        name="file_agent",
        instruction=instruction,
        tools=[run_code_tool]
    )
    
    return agent


# Create the default file agent instance
file_agent = create_file_agent()


def prepare_file_agent(dataframes: Dict[str, Union[pd.DataFrame, Any]], 
                      conversation_id: Optional[str] = None,
                      supabase_client=None) -> Agent:
    """
    Prepare the file agent with new dataframes and settings.
    
    Args:
        dataframes: Dictionary of dataframes to load
        conversation_id: Optional conversation ID
        supabase_client: Optional Supabase client for saving outputs
    
    Returns:
        Configured Agent instance
    """
    global file_agent, _file_agent_dataframes
    
    # Update dataframes
    _file_agent_dataframes = dataframes
    
    # Set Supabase client if provided
    if supabase_client:
        set_supabase_client(supabase_client)
    
    # Create new agent instance
    file_agent = create_file_agent(conversation_id)
    
    return file_agent


# For backward compatibility
root_agent = file_agent