"""
Chat API Endpoints
Handles chatbot conversation requests
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging

from app.core.firebase import db
from app.core.security import get_guest_id
from app.services.chatbot.orchestrator import orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models
class ChatMessageRequest(BaseModel):
    """Chat message request"""
    session_id: Optional[str] = Field(None, description="Chat session ID (auto-generated if not provided)")
    message: str = Field(..., description="User's message", min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Chat message response"""
    session_id: str = Field(..., description="Chat session ID")
    reply: str = Field(..., description="Assistant's reply")
    intent: str = Field(..., description="Detected intent")
    extracted: Dict[str, Any] = Field(default_factory=dict, description="Extracted structured data")
    pricing_info: Optional[Dict[str, Any]] = Field(None, description="Pricing information if requested")
    timestamp: str = Field(..., description="Response timestamp")


class ChatSession(BaseModel):
    """Chat session summary"""
    session_id: str
    user_id: str
    last_message: str
    last_activity: str
    message_count: int
    created_at: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message in history"""
    role: str  # 'user' or 'assistant'
    message: str
    timestamp: str
    intent: Optional[str] = None
    extracted: Optional[Dict[str, Any]] = None


class ConversationHistory(BaseModel):
    """Conversation history response"""
    session_id: str
    messages: List[ChatMessage]
    total_messages: int


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    guest_id: str = Depends(get_guest_id)
):
    """
    Send a message to the chatbot
    
    - **session_id**: Optional session ID. If not provided, a new session will be created
    - **message**: User's message (max 2000 characters)
    
    Returns the assistant's reply with detected intent and extracted information.
    Requires X-Guest-Id header.
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"Processing chat message for guest {guest_id}, session {session_id}")
        
        # Call orchestrator
        result = await orchestrator.handle_message(
            user_message=request.message,
            session_id=session_id,
            guest_id=guest_id
        )
        
        return ChatMessageResponse(
            session_id=result['session_id'],
            reply=result['reply'],
            intent=result.get('state', 'unknown'),
            extracted={},
            pricing_info=result.get('data'),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSession])
async def get_user_sessions(
    guest_id: str = Depends(get_guest_id),
    limit: int = 20
):
    """
    Get all chat sessions for the current user
    
    - **limit**: Maximum number of sessions to return (default: 20)
    
    Returns list of chat sessions ordered by last activity
    """
    try:
        # Query user's sessions
        sessions_ref = db.collection('chat_sessions')
        sessions_query = sessions_ref\
            .where('guest_id', '==', guest_id)\
            .order_by('last_activity', direction='DESCENDING')\
            .limit(limit)\
            .stream()
        
        sessions = []
        for doc in sessions_query:
            data = doc.to_dict()
            
            # Convert timestamp to ISO format
            last_activity = data.get('last_activity')
            if hasattr(last_activity, 'isoformat'):
                last_activity_str = last_activity.isoformat()
            else:
                last_activity_str = str(last_activity) if last_activity else None
            
            created_at = data.get('created_at')
            if hasattr(created_at, 'isoformat'):
                created_at_str = created_at.isoformat()
            else:
                created_at_str = str(created_at) if created_at else None
            
            sessions.append(ChatSession(
                session_id=doc.id,
                user_id=data.get('user_id', ''),
                last_message=data.get('last_message', ''),
                last_activity=last_activity_str or '',
                message_count=data.get('message_count', 0),
                created_at=created_at_str
            ))
        
        logger.info(f"Retrieved {len(sessions)} sessions for guest {guest_id}")
        
        return sessions
        
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: str,
    guest_id: str = Depends(get_guest_id),
    limit: int = 50
):
    """
    Get conversation history for a specific session
    
    - **session_id**: Chat session ID
    - **limit**: Maximum number of messages to return (default: 50)
    
    Returns all messages in the conversation ordered by timestamp
    """
    try:
        # Verify session belongs to user
        session_ref = db.collection('chat_sessions').document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        if session_data.get('user_id') != current_user.get('uid'):
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        # Get messages
        messages_ref = db.collection('chat_messages')
        messages_query = messages_ref\
            .where('session_id', '==', session_id)\
            .order_by('timestamp', direction='ASCENDING')\
            .limit(limit)\
            .stream()
        
        messages = []
        for doc in messages_query:
            data = doc.to_dict()
            
            # Convert timestamp
            timestamp = data.get('timestamp')
            if hasattr(timestamp, 'isoformat'):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = str(timestamp) if timestamp else ''
            
            messages.append(ChatMessage(
                role=data.get('role', 'user'),
                message=data.get('message', ''),
                timestamp=timestamp_str,
                intent=data.get('intent'),
                extracted=data.get('extracted')
            ))
        
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
        
        return ConversationHistory(
            session_id=session_id,
            messages=messages,
            total_messages=len(messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation history: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    guest_id: str = Depends(get_guest_id)
):
    """
    Delete a chat session (soft delete - marks as deleted)
    
    - **session_id**: Chat session ID
    
    Returns success message
    """
    try:
        # Verify session belongs to user
        session_ref = db.collection('chat_sessions').document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        if session_data.get('user_id') != current_user.get('uid'):
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        # Soft delete - mark as deleted
        session_ref.update({
            'deleted': True,
            'deleted_at': datetime.utcnow()
        })
        
        logger.info(f"Session {session_id} deleted by user {current_user.get('uid')}")
        
        return {
            "message": "Session deleted successfully",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )

