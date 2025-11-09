from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

deepresearch_agent = Agent(
    model=LiteLlm(model="openai/o4-mini-deep-research"),
    name="deepresearch_agent",
    instruction="""
    You are a deep research agent. You are given a question and you need to find the most relevant information from the web.
    """
)