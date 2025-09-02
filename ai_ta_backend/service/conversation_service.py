"""Service for managing conversation persistence and history."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation history and persistence."""
    
    def __init__(self, supabase_client=None):
        """Initialize with optional Supabase client."""
        self.supabase = supabase_client
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all messages for a conversation from the database.
        Returns messages in chronological order.
        """
        if not self.supabase:
            logger.warning("No Supabase client available, returning empty history")
            return []
        
        try:
            # Query messages for this conversation
            response = self.supabase.table('messages') \
                .select('*') \
                .eq('conversation_id', conversation_id) \
                .order('created_at', desc=False) \
                .execute()
            
            if response.data:
                # Convert database messages to the format expected by ADK
                messages = []
                for msg in response.data:
                    message = {
                        'role': msg['role'],
                        'content': msg['content_text'],
                        'id': msg['id'],
                        'created_at': msg['created_at']
                    }
                    
                    # Add image content if present
                    if msg.get('content_image_url'):
                        message['content'] = [
                            {'type': 'text', 'text': msg['content_text']}
                        ]
                        for img_url in msg['content_image_url']:
                            message['content'].append({
                                'type': 'image_url',
                                'image_url': {'url': img_url}
                            })
                    
                    # Add tool information if present
                    if msg.get('tools'):
                        message['tools'] = msg['tools']
                    
                    # Add context information if present
                    if msg.get('contexts'):
                        message['contexts'] = msg['contexts']
                    
                    messages.append(message)
                
                logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
                return messages
            else:
                logger.info(f"No messages found for conversation {conversation_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving conversation messages: {e}")
            return []
    
    def save_adk_events(self, events: List[Dict], conversation_id: str, message_id: Optional[str] = None) -> bool:
        """
        Save ADK events to the database for persistence.
        """
        if not self.supabase:
            logger.warning("No Supabase client available, skipping event save")
            return False
        
        try:
            for event in events:
                event_data = {
                    'adk_event_id': event.get('id'),
                    'conversation_id': conversation_id,
                    'message_id': message_id,
                    'author': event.get('author', 'unknown'),
                    'invocation_id': event.get('invocationId', ''),
                    'event_ts': datetime.now().isoformat(),
                    'event_type': self._determine_event_type(event),
                    'partial': event.get('partial', False),
                    'is_final': not event.get('partial', False),
                    'long_running_tool_ids': event.get('longRunningToolIds', []),
                    'event': event  # Store full event as JSONB
                }
                
                # Extract token usage if available
                usage = event.get('usageMetadata', {})
                if usage:
                    event_data['input_tokens'] = usage.get('promptTokenCount')
                    event_data['output_tokens'] = usage.get('candidatesTokenCount')
                
                # Save to database
                self.supabase.table('adk_events').insert(event_data).execute()
            
            logger.info(f"Saved {len(events)} ADK events for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving ADK events: {e}")
            return False
    
    def get_adk_events(self, conversation_id: str) -> List[Dict]:
        """
        Retrieve ADK events for a conversation from the database.
        """
        if not self.supabase:
            logger.warning("No Supabase client available, returning empty events")
            return []
        
        try:
            response = self.supabase.table('adk_events') \
                .select('*') \
                .eq('conversation_id', conversation_id) \
                .order('event_ts', desc=False) \
                .execute()
            
            if response.data:
                logger.info(f"Retrieved {len(response.data)} ADK events for conversation {conversation_id}")
                return [event['event'] for event in response.data]
            else:
                logger.info(f"No ADK events found for conversation {conversation_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving ADK events: {e}")
            return []
    
    def _determine_event_type(self, event: Dict) -> str:
        """Determine the type of ADK event."""
        content = event.get('content', {})
        if not content:
            return 'unknown'
        
        parts = content.get('parts', [])
        for part in parts:
            if 'thoughtSignature' in part:
                return 'thinking'
            elif 'functionCall' in part:
                return 'tool_call'
            elif 'functionResponse' in part:
                return 'tool_response'
            elif 'text' in part:
                return 'text'
        
        return 'other'
    
    def rebuild_session_from_database(self, conversation_id: str) -> List[Dict]:
        """
        Rebuild a conversation session from stored messages and events.
        This provides full conversation history even after backend restarts.
        """
        messages = self.get_conversation_messages(conversation_id)
        
        # Optionally, we could also replay ADK events if needed
        # events = self.get_adk_events(conversation_id)
        
        return messages
