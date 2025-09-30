from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.models.lite_llm import LiteLlm

from .prompt import agent_instruction
from .tools.tools import tools
# from .tools.file import file_agent

# Default agent for backwards compatibility
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="aganswers",
    instruction=agent_instruction,
    tools=tools,
)

def create_agent_with_model(model_info: dict = None) -> LlmAgent:
    """
    Create an AgAnswers agent with a specific model configuration.
    
    Args:
        model_info (dict): Model configuration from frontend with keys:
            - id: Model identifier (e.g., "openai/gpt-5-mini-2025-08-07")
            - name: Display name
            - tokenLimit: Token limit
            - enabled: Whether model is enabled
    
    Returns:
        LlmAgent: Configured agent instance
    """
    if not model_info or not model_info.get("id"):
        print("No model info provided, using default gemini-2.5-flash")
        return root_agent
    
    model_id = model_info.get("id")
    print(f"Creating agent with model: {model_id}")
    
    # Format model ID for LiteLLM based on provider
    formatted_model_id = _format_model_id_for_litellm(model_id)
    print(f"Formatted model ID for LiteLLM: {formatted_model_id}")
    
    try:
        # Create agent with LiteLLM wrapper for non-Google models
        if model_id.startswith("google/"):
            # For Google models, use direct model string (ADK handles natively)
            agent = LlmAgent(
                model=formatted_model_id,
                name="aganswers",
                instruction=agent_instruction,
                tools=tools,
            )
        else:
            # For non-Google models (OpenAI, etc.), use LiteLLM wrapper
            agent = LlmAgent(
                model=LiteLlm(model=formatted_model_id),
                name="aganswers", 
                instruction=agent_instruction,
                tools=tools,
            )
        
        print(f"Successfully created agent with model: {model_id}")
        return agent
        
    except Exception as e:
        print(f"Error creating agent with model {model_id}: {e}")
        print("Falling back to default agent")
        return root_agent

def _format_model_id_for_litellm(model_id: str) -> str:
    """
    Format model ID for LiteLLM compatibility.
    
    Args:
        model_id (str): Original model ID from frontend
        
    Returns:
        str: Formatted model ID for LiteLLM
    """
    # Google models: remove "google/" prefix for direct ADK usage
    if model_id.startswith("google/"):
        return model_id.replace("google/", "")
    
    # OpenAI models: keep as-is for LiteLLM (they expect "openai/" prefix)
    if model_id.startswith("openai/"):
        return model_id
    
    # For other providers, keep as-is
    return model_id