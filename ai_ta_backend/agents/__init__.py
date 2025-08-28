# Build a base agent (orchestrator) in @ai_ta_backend/agents                                                                                                                                                                                                  
# Focus on simplicity. We are implimenting the base functionality and will build on top of it. The only thing we need to prioritize is speed (time to first token), streaming responses, and basic setup. Have absolutely no tools or anything, just          
# setup the base agent. It needs to be ready to use via api with streaming. Ensure when looking through code you do it in batches and not all at once.
# Your final goal is to have an __init__.py file that can be directly passed a query and return a stream of tokens ready to be sent to the frontend via api.                                                                                                        
# You must use google-adk. Here is the source code for it:                                                                                                                                                                                                    
# /adk-python                                                                                                                                                                                                                                                 
# @adk-python/README.md

from . import agent
