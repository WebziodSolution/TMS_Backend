from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import TicketLogService

router = APIRouter(prefix="/ticket_log", tags=["Ticket Log"])

# -----------------
# SCHEMAS
# -----------------
class TicketLogCreate(BaseModel):
    ticket_id: int
    status_id: Optional[int] = None
    due_date: Optional[datetime] = None
    internal_qa: Optional[List[str]] = None

class TicketLogUpdate(BaseModel):
    ticket_id: Optional[int] = None
    status_id: Optional[int] = None
    due_date: Optional[datetime] = None
    internal_qa: Optional[List[str]] = None

class TicketLogResponse(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    user_name: Optional[str] = None
    status_id: Optional[int] = None
    new_status_name: Optional[str] = None
    old_status_name: Optional[str] = None
    new_due_date: Optional[str] = None
    old_due_date: Optional[str] = None
    internal_qa: Optional[List[str]] = None
    created_date: Optional[str] = None

# -----------------
# ENDPOINTS
# -----------------
@router.post("", response_model=APIResponse[TicketLogResponse], status_code=status.HTTP_201_CREATED)
def create_log(
    payload: TicketLogCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.create_log(payload, current_user_id)
    return success_response(result, "Ticket status log created successfully", 201)

@router.get("", response_model=APIResponse[List[TicketLogResponse]])
def get_all_logs(
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.get_all_logs()
    return success_response(result, "Ticket status logs fetched successfully")

@router.get("/ticket/{ticket_id}", response_model=APIResponse[List[TicketLogResponse]])
def get_logs_by_ticket(
    ticket_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.get_logs_by_ticket(ticket_id)
    return success_response(result, "Ticket status logs fetched successfully")

@router.get("/{id}", response_model=APIResponse[TicketLogResponse])
def get_log(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.get_log_by_id(id)
    return success_response(result, "Ticket status log fetched successfully")

@router.put("/{id}", response_model=APIResponse[TicketLogResponse])
def update_log(
    id: int,
    payload: TicketLogUpdate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.update_log(id, payload)
    return success_response(result, "Ticket status log updated successfully")

@router.delete("/{id}")
def delete_log(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketLogService.delete_log(id)
    return success_response(None, "Ticket status log deleted successfully", 204)
