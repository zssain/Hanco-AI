"""
Chat request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatSessionCreate(BaseModel):
    """Create chat session request"""
    user_id: Optional[str] = None  # Can be inferred from auth


class ChatSessionResponse(BaseModel):
    """Chat session response"""
    session_id: str
    user_id: str
    created_at: datetime
    last_message_at: Optional[datetime] = None
    is_active: bool = True
    
    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    """Send chat message request"""
    session_id: str
    content: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Chat message response"""
    message_id: Optional[str] = None
    session_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Chat history response"""
    session_id: str
    messages: List[ChatMessageResponse]
    total_messages: int


class ChatStreamResponse(BaseModel):
    """Streaming chat response"""
    session_id: str
    content: str
    is_complete: bool = False
