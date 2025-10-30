from google.adk.tools import AgentTool  

def get_current_sub_agents():
    """
    Get current sub_agents with fresh agent references.
    
    This function is called every time an agent is created, ensuring we always
    use the most up-to-date file_agent state (which gets updated by prepare_file_agent).
    
    By importing inside the function, we avoid stale module-level references.
    """
    # Import inside function to get fresh references
    # from .search import general_search_agent
    from .file import agent as file_agent_module
    
    # Create fresh AgentTool wrappers
    # file_agent_module.file_agent is a global that gets reassigned by prepare_file_agent()
    # general_search_tool = AgentTool(general_search_agent)
    
    return [file_agent_module.file_agent]