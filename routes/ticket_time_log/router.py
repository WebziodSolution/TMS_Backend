from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import TicketLogService

router = APIRouter(prefix="/ticket_time_log", tags=["Ticket Log"])

# -----------------
# SCHEMAS
# -----------------
class TicketLogActionRequest(BaseModel):
    ticket_id: int
    action: str  # "start", "pause", "resume", "complete"
    note: Optional[str] = None

class TicketLogCreate(BaseModel):
    ticket_id: int
    user_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: int
    complete_date: Optional[datetime] = None
    note: Optional[str] = None

class TicketLogUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[int] = None
    complete_date: Optional[datetime] = None
    note: Optional[str] = None

class TicketLogResponse(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: int
    complete_date: Optional[datetime] = None
    note: Optional[str] = None

class ActiveLogsResponse(BaseModel):
    logs: List[TicketLogResponse]
    server_time: datetime

# -----------------
# ENDPOINTS
# -----------------
@router.post("/action", response_model=APIResponse[Optional[TicketLogResponse]])
def execute_action(
    payload: TicketLogActionRequest,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Validation of the action
    if payload.action not in ["start", "pause", "resume", "complete"]:
        raise HTTPException(status_code=400, detail="Invalid action. Allowed: start, pause, resume, complete")
    
    if payload.action == "complete" and not payload.note:
        raise HTTPException(status_code=400, detail="Reason/Note is required for completing work logs")
        
    result = TicketLogService.execute_action(
        ticket_id=payload.ticket_id,
        user_id=current_user_id,
        action=payload.action,
        note=payload.note
    )
    return success_response(result, f"Timer action '{payload.action}' executed successfully")

@router.get("/ticket/{ticket_id}/active", response_model=APIResponse[ActiveLogsResponse])
def get_active_logs(
    ticket_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = TicketLogService.get_active_logs(ticket_id=ticket_id, user_id=current_user_id)
    server_time = datetime.now(timezone.utc)
    return success_response({
        "logs": result,
        "server_time": server_time
    }, "Active/paused logs fetched successfully")

@router.get("/ticket/{ticket_id}/history", response_model=APIResponse[List[TicketLogResponse]])
def get_ticket_history(
    ticket_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = TicketLogService.get_ticket_log_history(ticket_id=ticket_id, user_id=current_user_id)
    return success_response(result, "Ticket log history fetched successfully")

# --- CRUD Endpoints ---

@router.post("", response_model=APIResponse[TicketLogResponse], status_code=status.HTTP_201_CREATED)
def create_log(
    payload: TicketLogCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.create_log(payload)
    return success_response(result, "Ticket log created successfully", 201)

@router.get("/{id}", response_model=APIResponse[TicketLogResponse])
def get_log(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.get_log_by_id(id)
    return success_response(result, "Ticket log fetched successfully")

@router.put("/{id}", response_model=APIResponse[TicketLogResponse])
def update_log(
    id: int,
    payload: TicketLogUpdate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.update_log(id, payload)
    return success_response(result, "Ticket log updated successfully")

@router.delete("/{id}")
def delete_log(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketLogService.delete_log(id)
    return success_response(None, "Ticket log deleted successfully", 204)

@router.get("/check/current_work")
def check_current_work(
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketLogService.check_current_work_status(user_id=current_user_id)
    if result:
        return success_response(result, "Current work fetched successfully",200)
    return success_response(result, "No current work",200)