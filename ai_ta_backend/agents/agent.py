from google.adk.agents import Agent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.models.lite_llm import LiteLlm

from .prompt import agent_instruction
from .tools.tools import tools
# from .tools.file import file_agent

root_agent = Agent(
    model="gemini-2.5-flash",
    name="aganswers",
    instruction=agent_instruction,
    tools=tools,
    # sub_agents=[file_agent],
)

# class AgAnswersAgent(Agent):
#     def __init__(self, model_str: str):
#         super().__init__(
#             model=LiteLlm(model=model_str),
#             name="aganswers",
#             instruction=agent_instruction,
#             tools=tools,
#         )