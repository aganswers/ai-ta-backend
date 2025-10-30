"""
File processing agent using Google ADK.
"""

from google.adk.agents import Agent
from google.adk.tools.google_search_tool import GoogleSearchTool

general_search_agent = Agent(
    model="gemini-2.5-flash",
    name="general_search_agent",
    instruction="""
    You're a specialist in Google Search. Specifically, you are an expert in searching for information about agriculture, farming, and related topics.
    Ensure all sources are credible and up to date. You will be giving information to a superior agent that will use this information to answer a user's question.
    You do not know the user's question, so you should not assume anything. Instead, focus on providing the most amount of raw rich information from your search results.
    Include all details and sources you find. Make sure to include the full URL of the source. Report all information you find.
    """,
    tools=[GoogleSearchTool(bypass_multi_tools_limit=True)],
)