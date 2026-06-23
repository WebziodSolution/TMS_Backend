from fastapi import HTTPException
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from database import get_db
from core.response import APIResponse, success_response
from routes.tickets.service import get_current_user_id
from .service import TicketCommentService

router = APIRouter(prefix="/ticket_comments", tags=["Ticket Comments"])

# -----------------
# SCHEMAS
# -----------------
class CommentAttachmentResponse(BaseModel):
    id: int
    file_name: str
    file_url: str
    created_date: datetime
    created_by: int

class TicketCommentResponse(BaseModel):
    id: int
    ticket_id: int
    comment: str
    parent_comment_id: Optional[int]
    comment_type_id: Optional[int]
    comment_type_name: Optional[str]
    created_by: int
    created_by_name: str
    created_date_time: datetime
    updated_date_time: datetime
    attachments: List[CommentAttachmentResponse] = []
    replies: List['TicketCommentResponse'] = []

# This is needed for self-referencing pydantic model
TicketCommentResponse.model_rebuild()

class TicketCommentCreate(BaseModel):
    ticket_id: int
    comment: str
    parent_comment_id: Optional[int] = None
    comment_type_id: Optional[int] = 1 # Default to 'Open'

class TicketCommentUpdate(BaseModel):
    comment: str
    comment_type_id: Optional[int] = None

# -----------------
# ROUTES
# -----------------

@router.get("", response_model=APIResponse[List[TicketCommentResponse]])
def get_comments(ticket_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketCommentService.get_comments_by_ticket(ticket_id, db, current_user_id)
    return success_response(result, "Comments fetched successfully")

@router.post("", response_model=APIResponse[TicketCommentResponse], status_code=status.HTTP_201_CREATED)
def create_comment(comment: TicketCommentCreate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketCommentService.create_comment(comment, db, current_user_id)
    return success_response(result, "Comment added successfully", 201)

@router.put("/{id}", response_model=APIResponse[TicketCommentResponse])
def update_comment(id: int, comment_update: TicketCommentUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketCommentService.update_comment(id, comment_update, db, current_user_id)
    return success_response(result, "Comment updated successfully")

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketCommentService.delete_comment(id, db, current_user_id)
    return success_response(None, "Comment deleted successfully", 204)
