from fastapi import HTTPException
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from database import get_db
from core.response import APIResponse, success_response
from .service import TicketService, get_current_user_id

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# -----------------
# SCHEMAS
# -----------------
class AssigneeInput(BaseModel):
    id: int
    send_mail: str = "Y"

class TicketCreate(BaseModel):
    project_id: int
    parent_ticket_id: Optional[int] = None
    project_name: str
    department_id: Optional[int] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    priority: Optional[str] = "low"
    working_hours: Optional[str]
    due_date: datetime
    as_customer: Optional[bool] = False
    for_customer: Optional[bool] = False
    status_id: Optional[int] = None
    assignees: List[AssigneeInput] = Field(..., min_length=1)
    owner_id: Optional[int] = None
    type: Optional[str] = None

class TicketUpdate(BaseModel):
    project_id: int
    parent_ticket_id: Optional[int] = None
    department_id: Optional[int] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    priority: Optional[str] = "low"
    working_hours: Optional[str]
    due_date: datetime
    as_customer: Optional[bool] = False
    for_customer: Optional[bool] = False
    status_id: Optional[int] = None
    assignees: List[AssigneeInput] = Field(..., min_length=1)
    owner_id: Optional[int] = None
    type: Optional[str] = None

class TicketStatusUpdate(BaseModel):
    status_id: int

class TicketTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1)

class AssigneeResponse(BaseModel):
    id: int
    name: str
    send_mail:str

class TicketResponse(BaseModel):
    id: int
    parent_ticket_id: Optional[int] = None
    parent_ticket_no: Optional[str] = None
    parent_ticket_title: Optional[str] = None
    ticket_no: Optional[str] = None
    project_id: int
    project_name: Optional[str] = None
    department_id: Optional[int] = None
    title: str
    description: Optional[str]
    priority: Optional[str] = None
    due_date: Optional[datetime]
    working_hours: Optional[str]
    as_customer: bool
    for_customer: bool
    created_by: Optional[int]
    created_by_name: Optional[str]
    created_date: datetime
    status_id: Optional[int] = None
    status_name: Optional[str] = None
    assignees: List[AssigneeResponse] = []
    attachments: List[dict] = []
    owner_id: Optional[int] = None
    type: Optional[str] = None
    
# Add this schema near the other Pydantic models
class TicketFilter(BaseModel):
    as_customer: Optional[bool] = None
    for_customer: Optional[bool] = None
    startDueDate: Optional[datetime] = None
    endDueDate: Optional[datetime] = None
    search: Optional[str] = None
    type: Optional[str] = None

class TicketAssigneeMailUpdate(BaseModel):
    user_id: int
    send_mail: str

class TicketCloseReopen(BaseModel):
    status_id: Optional[int] = None

# Add this route after the existing ones
@router.post("/filter", response_model=APIResponse[List[TicketResponse]])
def filter_tickets(filter: TicketFilter, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.get_filtered_tickets(filter, db, current_user_id)
    return success_response(result, "Filtered tickets fetched successfully")
    
@router.patch("/{ticket_id}/assignee/send-mail", response_model=APIResponse[TicketResponse])
def update_assignee_send_mail(ticket_id: int, mail_update: TicketAssigneeMailUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.update_assignee_send_mail(ticket_id, mail_update.user_id, mail_update.send_mail, db)
    return success_response(result, "Assignee mail setting updated successfully")
    
@router.post("", response_model=APIResponse[TicketResponse], status_code=status.HTTP_201_CREATED)
def create_ticket(ticket: TicketCreate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.create_ticket(ticket, db, current_user_id)
    return success_response(result, "Ticket created successfully", 201)

@router.get("", response_model=APIResponse[List[TicketResponse]])
def get_all_tickets(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.get_all_tickets(db,current_user_id)
    return success_response(result, "Tickets fetched successfully")

@router.get("/{ticket_id}", response_model=APIResponse[TicketResponse])
def get_ticket(ticket_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.get_ticket(ticket_id, db)
    return success_response(result, "Ticket fetched successfully")

@router.get("/project/{project_id}", response_model=APIResponse[List[TicketResponse]])
def get_tickets_by_project(project_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.get_tickets_by_project(project_id, db)
    return success_response(result, "Tickets fetched successfully for project")

@router.put("/{ticket_id}", response_model=APIResponse[TicketResponse])
def update_ticket(ticket_id: int, ticket_update: TicketUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.update_ticket(ticket_id, ticket_update, db, current_user_id)
    return success_response(result, "Ticket updated successfully")

@router.patch("/{ticket_id}/status", response_model=APIResponse[TicketResponse])
def update_ticket_status(ticket_id: int, status_update: TicketStatusUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.update_ticket_status(ticket_id, status_update, db, current_user_id)
    return success_response(result, "Ticket status updated successfully")

@router.patch("/{ticket_id}/title", response_model=APIResponse[TicketResponse])
def update_ticket_title(ticket_id: int, title_update: TicketTitleUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.update_ticket_title(ticket_id, title_update, db, current_user_id)
    return success_response(result, "Ticket title updated successfully")

@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketService.delete_ticket(ticket_id, db, current_user_id)
    return success_response(None, "Ticket deleted successfully", 204)

@router.post("/{ticket_id}/close-reopen", response_model=APIResponse[TicketResponse])
def close_or_reopen_ticket(ticket_id: int, body: TicketCloseReopen, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketService.close_or_reopen_ticket(ticket_id, body.status_id, db, current_user_id)
    return success_response(result, "Ticket status updated successfully")
