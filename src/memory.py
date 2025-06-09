"""
Conversation Memory Management for SMS AI Agent

This module handles persistent conversation memory using Google Firestore,
including conversation history, context windowing, and expiration.
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import structlog
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain.memory.chat_message_histories import BaseChatMessageHistory

from .exceptions import ConversationMemoryError
from .config import Config


logger = structlog.get_logger(__name__)


class FirestoreChatMessageHistory(BaseChatMessageHistory):
    """Custom chat message history implementation using Firestore."""
    
    def __init__(self, 
                 phone_number: str, 
                 firestore_client: firestore.Client,
                 collection_name: str = 'conversations',
                 max_messages: int = 20):
        """
        Initialize Firestore chat message history.
        
        Args:
            phone_number: User's phone number (used as document ID)
            firestore_client: Initialized Firestore client
            collection_name: Firestore collection name
            max_messages: Maximum messages to keep in memory
        """
        self.phone_number = phone_number
        self.collection_name = collection_name
        self.max_messages = max_messages
        self.db = firestore_client
        
        # Create document reference
        self.doc_ref = self.db.collection(collection_name).document(phone_number)
        
        # Cache for messages
        self._messages: List[BaseMessage] = []
        self._loaded = False
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Get all messages, loading from Firestore if needed."""
        if not self._loaded:
            self._load_messages()
        return self._messages
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the chat history."""
        if not self._loaded:
            self._load_messages()
        
        self._messages.append(message)
        
        # Apply window limit
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]
        
        # Save to Firestore
        self._save_messages()
    
    def clear(self) -> None:
        """Clear all messages from history."""
        self._messages = []
        self._loaded = True
        
        # Delete from Firestore
        try:
            self.doc_ref.delete()
            logger.info("Conversation history cleared", phone_number=self.phone_number)
        except Exception as e:
            logger.error(
                "Failed to clear conversation history",
                phone_number=self.phone_number,
                error=str(e)
            )
            raise ConversationMemoryError(f"Failed to clear history: {e}")
    
    def _load_messages(self) -> None:
        """Load messages from Firestore."""
        try:
            doc = self.doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                
                # Check if conversation has expired
                if self._is_conversation_expired(data):
                    logger.info(
                        "Conversation expired, starting fresh",
                        phone_number=self.phone_number
                    )
                    self.clear()
                    return
                
                # Load messages
                messages_data = data.get('messages', [])
                self._messages = []
                
                for msg_data in messages_data:
                    if msg_data['type'] == 'human':
                        message = HumanMessage(content=msg_data['content'])
                    elif msg_data['type'] == 'ai':
                        message = AIMessage(content=msg_data['content'])
                    else:
                        logger.warning(
                            "Unknown message type",
                            type=msg_data['type'],
                            phone_number=self.phone_number
                        )
                        continue
                    
                    self._messages.append(message)
                
                logger.info(
                    "Loaded conversation history",
                    phone_number=self.phone_number,
                    message_count=len(self._messages)
                )
            else:
                self._messages = []
                logger.info(
                    "No existing conversation found",
                    phone_number=self.phone_number
                )
            
            self._loaded = True
            
        except Exception as e:
            logger.error(
                "Failed to load conversation history",
                phone_number=self.phone_number,
                error=str(e)
            )
            # Start with empty history on error
            self._messages = []
            self._loaded = True
    
    def _save_messages(self) -> None:
        """Save messages to Firestore."""
        try:
            # Convert messages to serializable format
            messages_data = []
            for message in self._messages:
                if isinstance(message, HumanMessage):
                    msg_data = {
                        'type': 'human',
                        'content': message.content,
                        'timestamp': time.time()
                    }
                elif isinstance(message, AIMessage):
                    msg_data = {
                        'type': 'ai',
                        'content': message.content,
                        'timestamp': time.time()
                    }
                else:
                    logger.warning(
                        "Unknown message type during save",
                        type=type(message),
                        phone_number=self.phone_number
                    )
                    continue
                
                messages_data.append(msg_data)
            
            # Save to Firestore
            doc_data = {
                'phone_number': self.phone_number,
                'messages': messages_data,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'created_at': firestore.SERVER_TIMESTAMP,
                'message_count': len(messages_data)
            }
            
            self.doc_ref.set(doc_data, merge=True)
            
            logger.debug(
                "Saved conversation history",
                phone_number=self.phone_number,
                message_count=len(messages_data)
            )
            
        except Exception as e:
            logger.error(
                "Failed to save conversation history",
                phone_number=self.phone_number,
                error=str(e)
            )
            raise ConversationMemoryError(f"Failed to save history: {e}")
    
    def _is_conversation_expired(self, data: Dict[str, Any]) -> bool:
        """Check if conversation has expired based on last update time."""
        if 'last_updated' not in data:
            return True
        
        last_updated = data['last_updated']
        if hasattr(last_updated, 'timestamp'):
            last_updated_time = last_updated.timestamp()
        else:
            last_updated_time = last_updated
        
        # Default to 24 hours expiration
        expiration_hours = 24
        expiration_seconds = expiration_hours * 3600
        
        return (time.time() - last_updated_time) > expiration_seconds


class ConversationMemory:
    """Main conversation memory manager."""
    
    def __init__(self, config: Config):
        """
        Initialize conversation memory manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Initialize Firestore client
        if config.google_cloud_project:
            self.db = firestore.Client(project=config.google_cloud_project)
        else:
            self.db = firestore.Client()  # Use default project
        
        self.collection_name = config.firestore_collection
        self.max_conversation_length = config.max_conversation_length
        
        # Cache for memory instances
        self._memory_cache: Dict[str, ConversationBufferWindowMemory] = {}
        
        logger.info(
            "Initialized conversation memory",
            collection=self.collection_name,
            max_length=self.max_conversation_length
        )
    
    def get_memory_for_user(self, phone_number: str) -> ConversationBufferWindowMemory:
        """
        Get conversation memory for a specific user.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            ConversationBufferWindowMemory instance for the user
        """
        # Return cached memory if available
        if phone_number in self._memory_cache:
            return self._memory_cache[phone_number]
        
        # Create new memory instance
        chat_history = FirestoreChatMessageHistory(
            phone_number=phone_number,
            firestore_client=self.db,
            collection_name=self.collection_name,
            max_messages=self.max_conversation_length
        )
        
        memory = ConversationBufferWindowMemory(
            chat_memory=chat_history,
            k=self.max_conversation_length,
            return_messages=True,
            memory_key="chat_history"
        )
        
        # Cache the memory instance
        self._memory_cache[phone_number] = memory
        
        logger.info(
            "Created memory for user",
            phone_number=phone_number
        )
        
        return memory
    
    def add_user_message(self, phone_number: str, message: str) -> None:
        """
        Add a user message to conversation history.
        
        Args:
            phone_number: User's phone number
            message: User's message content
        """
        memory = self.get_memory_for_user(phone_number)
        memory.chat_memory.add_user_message(message)
        
        logger.debug(
            "Added user message",
            phone_number=phone_number,
            message_length=len(message)
        )
    
    def add_ai_message(self, phone_number: str, message: str) -> None:
        """
        Add an AI message to conversation history.
        
        Args:
            phone_number: User's phone number
            message: AI's message content
        """
        memory = self.get_memory_for_user(phone_number)
        memory.chat_memory.add_ai_message(message)
        
        logger.debug(
            "Added AI message",
            phone_number=phone_number,
            message_length=len(message)
        )
    
    def get_conversation_context(self, phone_number: str) -> str:
        """
        Get conversation context as a formatted string.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Formatted conversation context
        """
        memory = self.get_memory_for_user(phone_number)
        messages = memory.chat_memory.messages
        
        if not messages:
            return "No previous conversation."
        
        context_lines = []
        for message in messages[-10:]:  # Last 10 messages for context
            if isinstance(message, HumanMessage):
                context_lines.append(f"User: {message.content}")
            elif isinstance(message, AIMessage):
                context_lines.append(f"Assistant: {message.content}")
        
        return "\n".join(context_lines)
    
    def clear_conversation(self, phone_number: str) -> None:
        """
        Clear conversation history for a user.
        
        Args:
            phone_number: User's phone number
        """
        if phone_number in self._memory_cache:
            memory = self._memory_cache[phone_number]
            memory.chat_memory.clear()
            del self._memory_cache[phone_number]
        
        logger.info("Cleared conversation", phone_number=phone_number)
    
    def get_conversation_stats(self, phone_number: str) -> Dict[str, Any]:
        """
        Get conversation statistics for a user.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Dictionary with conversation statistics
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(phone_number)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return {
                    'message_count': data.get('message_count', 0),
                    'last_updated': data.get('last_updated'),
                    'created_at': data.get('created_at'),
                    'exists': True
                }
            else:
                return {
                    'message_count': 0,
                    'last_updated': None,
                    'created_at': None,
                    'exists': False
                }
                
        except Exception as e:
            logger.error(
                "Failed to get conversation stats",
                phone_number=phone_number,
                error=str(e)
            )
            return {
                'message_count': 0,
                'last_updated': None,
                'created_at': None,
                'exists': False,
                'error': str(e)
            }
    
    def cleanup_expired_conversations(self, hours: int = 24) -> int:
        """
        Clean up expired conversations.
        
        Args:
            hours: Number of hours after which conversations expire
            
        Returns:
            Number of conversations cleaned up
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Query for expired conversations
            query = self.db.collection(self.collection_name).where(
                filter=FieldFilter("last_updated", "<", cutoff_time)
            )
            
            docs = query.stream()
            deleted_count = 0
            
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            logger.info(
                "Cleaned up expired conversations",
                deleted_count=deleted_count,
                cutoff_hours=hours
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error("Failed to cleanup expired conversations", error=str(e))
            return 0 