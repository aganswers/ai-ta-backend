from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
# from .tools.tools import get_current_tools
from .tools.sub_agents import get_current_sub_agents

from .prompt import agent_instruction
# Import the module, not the variable, so we get the updated global reference

def create_agent_with_model(model_info: dict = None, available_files: list = None) -> LlmAgent:
    """
    Create an AgAnswers agent with a specific model configuration.
    
    Args:
        model_info (dict): Model configuration from frontend with keys:
            - id: Model identifier (e.g., "openai/gpt-5-mini-2025-08-07")
            - name: Display name
            - tokenLimit: Token limit
            - enabled: Whether model is enabled
        available_files (list): List of available file names for context
    
    Returns:
        LlmAgent: Configured agent instance
    """
    
    # Build instruction with available files context
    instruction = agent_instruction
    if available_files and len(available_files) > 0:
        files_list = "\n".join([f"  - {file}" for file in available_files])
        instruction = f"""{agent_instruction}

**Available Files in This Project:**

The following files are currently available for analysis:
{files_list}

When the user asks about data, reports, or analysis, you should use the file_agent tool to access and analyze these files.
"""
    # tools = get_current_tools()
    sub_agents = get_current_sub_agents()
    if not model_info or not model_info.get("id"):
        print("No model info provided, using default gemini-2.5-flash")
        return LlmAgent(
            model="gemini-2.5-flash",
            name="aganswers_no_model_info",
            instruction=instruction,
            # tools=tools,
            sub_agents=sub_agents,
        )
    
    model_id = model_info.get("id")
    print(f"Creating agent with model: {model_id}")
    if available_files:
        print(f"Agent has access to {len(available_files)} files")
    
    # Format model ID for LiteLLM based on provider
    formatted_model_id = _format_model_id_for_litellm(model_id)
    print(f"Formatted model ID for LiteLLM: {formatted_model_id}")
    
    try:
        # Create agent with LiteLLM wrapper for non-Google models
        # For non-Google models (OpenAI, etc.), use LiteLLM wrapper with openrouter
        agent = LlmAgent(
            model=LiteLlm(model=formatted_model_id),
            name="aganswers", 
            instruction=instruction,
            # tools=tools,
            sub_agents=sub_agents,
        )
        
        print(f"Successfully created agent with model: {model_id}")
        return agent
        
    except Exception as e:
        print(f"Error creating agent with model {model_id}: {e}")
        print("Falling back to default agent")
        return LlmAgent(
            model="gemini-2.5-flash",
            name="aganswers_fallback",
            instruction=instruction,
            # tools=tools,
            sub_agents=sub_agents,
        )

def _format_model_id_for_litellm(model_id: str) -> str:
    """
    Format model ID for LiteLLM compatibility.
    
    Args:
        model_id (str): Original model ID from frontend
        
    Returns:
        str: Formatted model ID for LiteLLM
    """
    # Google models: remove "google/" prefix for direct ADK usage
    # if model_id.startswith("google/"):
    #     return model_id.replace("google/", "")
    
    # For all non-Google models, use OpenRouter
    return "openrouter/" + model_id