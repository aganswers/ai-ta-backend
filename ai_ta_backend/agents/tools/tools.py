from google.adk.tools import AgentTool  

def get_current_tools():
    """
    Get current tools with fresh agent references.
    
    This function is called every time an agent is created, ensuring we always
    use the most up-to-date file_agent state (which gets updated by prepare_file_agent).
    
    By importing inside the function, we avoid stale module-level references.
    """
    # Import inside function to get fresh references
    from .search import general_search_agent
    general_search_tool = AgentTool(general_search_agent)
    
    return [general_search_tool]