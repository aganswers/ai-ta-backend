from __future__ import annotations

import base64
import logging
import uuid
from typing import Generator, Dict, Any, Optional, List
import asyncio
import threading
from datetime import datetime

from google.genai import types
from google.adk.runners import Runner
from google.adk.events.event import Event
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ADKLLMService:
    """Service for streaming ADK agent responses via SSE."""
    
    def __init__(self, base_agent: BaseAgent):
        """Initialize with the base agent."""
        self.base_agent = base_agent
        self.runner = Runner(
            app_name="aganswers",
            agent=base_agent,
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            artifact_service=InMemoryArtifactService(),
        )
    
    def ensure_session(self, user_id: str, session_id: str, historical_messages: Optional[List[Dict]] = None) -> bool:
        """
        Ensure ADK session exists, create if needed.
        Returns True if session already had history, False if it's new/empty.
        
        NOTE: We no longer rebuild session history by replaying messages through the LLM
        as this causes exponential slowdown with complex conversation history.
        Instead, we pass conversation context directly to the model.
        """
        try:
            # Use asyncio to run the async session methods
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            session = loop.run_until_complete(
                self.runner.session_service.get_session(
                    app_name="aganswers", 
                    user_id=user_id, 
                    session_id=session_id
                )
            )
            
            session_exists = session is not None
            
            if not session:
                # Create session with conversation history in state (for context)
                # but DON'T replay messages through the LLM
                conversation_context = {}
                if historical_messages and len(historical_messages) > 1:
                    # Store a summary of conversation history in session state
                    # This is much faster than replaying all messages
                    conversation_context = {
                        'message_count': len(historical_messages) - 1,
                        'has_history': True,
                        # Store last few messages for context without replaying them
                        'recent_context': self._extract_recent_context(historical_messages[:-1])
                    }
                    logger.info(f"Created session {session_id} with {len(historical_messages) - 1} messages in context (not replayed)")
                
                session = loop.run_until_complete(
                    self.runner.session_service.create_session(
                        app_name="aganswers",
                        user_id=user_id,
                        state=conversation_context,
                        session_id=session_id
                    )
                )
                logger.info(f"Created new ADK session: {session_id}")
            
            loop.close()
            return session_exists
            
        except Exception as e:
            logger.error(f"Error ensuring session {session_id}: {e}")
            raise
    
    def _extract_recent_context(self, historical_messages: List[Dict], max_messages: int = 10) -> List[Dict]:
        """
        Extract recent conversation context without replaying through LLM.
        Returns a lightweight summary of recent messages for context.
        """
        try:
            # Take the last N messages for context
            recent_messages = historical_messages[-max_messages:] if len(historical_messages) > max_messages else historical_messages
            
            context = []
            for msg in recent_messages:
                # Extract just the essential info without processing through LLM
                content = msg.get('content', '')
                if isinstance(content, list):
                    # Handle mixed content (text + images)
                    text_parts = []
                    has_images = False
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                        elif isinstance(item, dict) and item.get('type') == 'image_url':
                            has_images = True
                    content = ' '.join(text_parts)
                    if has_images:
                        content += ' [includes images]'
                
                # Store lightweight message summary
                context.append({
                    'role': msg.get('role', 'user'),
                    'content_preview': content[:500] if isinstance(content, str) else str(content)[:500],  # Truncate long messages
                    'timestamp': msg.get('created_at', '')
                })
            
            return context
            
        except Exception as e:
            logger.error(f"Error extracting recent context: {e}")
            return []
    
    def _rebuild_session_history(self, user_id: str, session_id: str, historical_messages: List[Dict]) -> None:
        """
        DEPRECATED: This method is no longer used as it causes exponential slowdown.
        We now pass conversation context directly instead of replaying messages.
        
        Previously this would replay all historical messages through the LLM,
        which was extremely inefficient for long conversations.
        """
        logger.warning("_rebuild_session_history called but is deprecated - skipping replay")
        return  # Don't replay messages anymore
    
    def convert_message_to_content(self, message: Dict[str, Any]) -> types.Content:
        """Convert Next.js message format to ADK types.Content."""
        parts = []
        content = message.get('content', '')
        
        if isinstance(content, str):
            # Simple text message
            if content.strip():
                parts.append(types.Part(text=content))
        elif isinstance(content, list):
            # Mixed content array (text + images)
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text' and item.get('text'):
                        parts.append(types.Part(text=item['text']))
                    elif item.get('type') == 'image_url':
                        # Handle base64 images
                        image_url = item.get('image_url', {}).get('url', '')
                        if image_url.startswith('data:'):
                            # Parse data URL: data:image/jpeg;base64,/9j/4AAQ...
                            try:
                                header, data = image_url.split(',', 1)
                                mime_type = header.split(';')[0].split(':')[1]
                                parts.append(types.Part(
                                    inline_data=types.Blob(
                                        mime_type=mime_type,
                                        data=data
                                    )
                                ))
                            except Exception as e:
                                logger.warning(f"Failed to parse image data URL: {e}")
                elif isinstance(item, str) and item.strip():
                    parts.append(types.Part(text=item))
        
        if not parts:
            parts.append(types.Part(text=""))
        
        return types.Content(role='user', parts=parts)
    
    def stream_events(
        self, 
        user_id: str, 
        session_id: str, 
        new_message: types.Content,
        state_delta: Optional[Dict[str, Any]] = None
    ) -> Generator[Event, None, None]:
        """Stream ADK Events using synchronous Runner.run()."""
        try:
            run_config = RunConfig(streaming_mode=StreamingMode.SSE)
            
            # Use the synchronous Runner.run() method
            for event in self.runner.run(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
                run_config=run_config
            ):
                yield event
                
        except Exception as e:
            logger.error(f"Error streaming events: {e}")
            # Yield error event
            error_event = Event(
                invocation_id=str(uuid.uuid4()),
                author='system',
                content=types.Content(
                    role='assistant',
                    parts=[types.Part(text=f"Error: {str(e)}")]
                )
            )
            yield error_event


class EventLogger:
    """Async logger for ADK events and messages to Supabase."""
    
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.log_queue = asyncio.Queue()
        self.worker_task = None
    
    def start_worker(self):
        """Start background worker for async logging."""
        if self.worker_task is None:
            loop = asyncio.new_event_loop()
            def run_worker():
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._log_worker())
            
            self.worker_task = threading.Thread(target=run_worker, daemon=True)
            self.worker_task.start()
    
    async def _log_worker(self):
        """Background worker to process log queue."""
        while True:
            try:
                log_data = await self.log_queue.get()
                if log_data is None:  # Shutdown signal
                    break
                await self._write_to_supabase(log_data)
            except Exception as e:
                logger.error(f"Error in log worker: {e}")
    
    async def _write_to_supabase(self, log_data: Dict[str, Any]):
        """Write log data to Supabase."""
        if not self.supabase:
            return
            
        try:
            table_name = log_data.get('table')
            data = log_data.get('data')
            
            if table_name == 'adk_events':
                self.supabase.table('adk_events').insert(data).execute()
            elif table_name == 'messages':
                self.supabase.table('messages').upsert(data).execute()
                
        except Exception as e:
            logger.error(f"Error writing to Supabase: {e}")
    
    def log_event_async(
        self, 
        event: Event, 
        conversation_id: str, 
        message_id: Optional[str] = None
    ):
        """Queue an ADK event for async logging."""
        if not self.supabase:
            return
            
        try:
            # Determine event type from content
            event_type = 'unknown'
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        event_type = 'thought' if getattr(part, 'thought', False) else 'text'
                        break
                    elif part.function_call:
                        event_type = 'function_call'
                        break
                    elif part.function_response:
                        event_type = 'function_response'
                        break
                    elif part.code_execution_result:
                        event_type = 'code_execution'
                        break
            
            if event.actions and event.actions.artifact_delta:
                event_type = 'artifact'
            elif event.actions and event.actions.state_delta:
                event_type = 'state_delta'
            
            log_data = {
                'table': 'adk_events',
                'data': {
                    'adk_event_id': event.id,
                    'conversation_id': conversation_id,
                    'message_id': message_id,
                    'author': event.author,
                    'invocation_id': event.invocation_id,
                    'event_ts': datetime.fromtimestamp(event.timestamp),
                    'event_type': event_type,
                    'partial': getattr(event, 'partial', False),
                    'is_final': event.is_final_response(),
                    'long_running_tool_ids': list(event.long_running_tool_ids) if event.long_running_tool_ids else None,
                    'actions': event.actions.model_dump() if event.actions else None,
                    'content': event.content.model_dump() if event.content else None,
                    'event': event.model_dump(by_alias=True, exclude_none=True)
                }
            }
            
            # Queue for async processing
            asyncio.run_coroutine_threadsafe(
                self.log_queue.put(log_data),
                asyncio.get_event_loop()
            )
            
        except Exception as e:
            logger.error(f"Error queuing event log: {e}")
    
    def log_message_async(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content_text: str,
        event_ids: List[str] = None,
        **kwargs
    ):
        """Queue a message for async logging."""
        if not self.supabase:
            return
            
        try:
            log_data = {
                'table': 'messages',
                'data': {
                    'id': message_id,
                    'conversation_id': conversation_id,
                    'role': role,
                    'content_text': content_text,
                    'event_ids': event_ids,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                    **kwargs
                }
            }
            
            # Queue for async processing
            asyncio.run_coroutine_threadsafe(
                self.log_queue.put(log_data),
                asyncio.get_event_loop()
            )
            
        except Exception as e:
            logger.error(f"Error queuing message log: {e}")
