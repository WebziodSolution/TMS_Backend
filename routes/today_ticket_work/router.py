from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import TodayTicketWorkService

router = APIRouter(prefix="/today_ticket_work", tags=["Today Ticket Work"])

# -----------------
# SCHEMAS
# -----------------
class TodayTicketWorkCreate(BaseModel):
    ticket_id: int
    date: str
    hours: Optional[str] = None
    minutes: Optional[str] = None
    note: Optional[str] = None

class TodayTicketWorkResponse(BaseModel):
    id: int
    hours: Optional[str] = None
    minutes: Optional[str] = None
    date: str
    note: Optional[str] = None
    ticket_id: int
    user_id: int

# -----------------
# ENDPOINTS
# -----------------

@router.post("", response_model=APIResponse[TodayTicketWorkResponse])
def upsert_work_log(
    payload: TodayTicketWorkCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = TodayTicketWorkService.upsert_work_log(
        hours=payload.hours,
        minutes=payload.minutes,
        date=payload.date,
        note=payload.note,
        ticket_id=payload.ticket_id,
        user_id=current_user_id
    )
    return success_response(result, "Work log saved successfully")

@router.get("/user/{user_id}/ticket/{ticket_id}", response_model=APIResponse[List[TodayTicketWorkResponse]])
def get_work_logs(
    user_id: int,
    ticket_id: int,
    date: Optional[str] = None,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    result = TodayTicketWorkService.get_work_logs(user_id=user_id, ticket_id=ticket_id, date=date)
    return success_response(result, "Work logs fetched successfully")

@router.get("/{id}", response_model=APIResponse[TodayTicketWorkResponse])
def get_work_log_by_id(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    result = TodayTicketWorkService.get_work_log_by_id(id)
    return success_response(result, "Work log fetched successfully")

@router.delete("/{id}")
def delete_work_log(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    TodayTicketWorkService.delete_work_log(id)
    return success_response(None, "Work log deleted successfully", 204)
