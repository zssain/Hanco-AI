"""
Chat models for Firestore
Represents chat sessions and messages
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import DocumentSnapshot


@dataclass
class ChatSession:
    """Chat session model for Firestore storage"""
    
    session_id: str
    user_id: str
    created_at: datetime
    last_message_at: Optional[datetime] = None
    is_active: bool = True
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'is_active': self.is_active,
        }
        
        if self.last_message_at:
            data['last_message_at'] = self.last_message_at
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['ChatSession']:
        """Create ChatSession instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            session_id=data.get('session_id', doc.id),
            user_id=data.get('user_id', ''),
            created_at=data.get('created_at', datetime.now()),
            last_message_at=data.get('last_message_at'),
            is_active=data.get('is_active', True)
        )


@dataclass
class ChatMessage:
    """Chat message model for Firestore storage"""
    
    session_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    message_id: Optional[str] = None
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert model to Firestore-compatible dictionary"""
        data = {
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp,
        }
        
        if self.message_id:
            data['message_id'] = self.message_id
            
        return data
    
    @classmethod
    def from_firestore(cls, doc: DocumentSnapshot) -> Optional['ChatMessage']:
        """Create ChatMessage instance from Firestore document"""
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        return cls(
            message_id=doc.id,
            session_id=data.get('session_id', ''),
            role=data.get('role', 'user'),
            content=data.get('content', ''),
            timestamp=data.get('timestamp', datetime.now())
        )
    
    def validate_role(self) -> bool:
        """Validate message role"""
        valid_roles = ['user', 'assistant', 'system']
        return self.role in valid_roles
