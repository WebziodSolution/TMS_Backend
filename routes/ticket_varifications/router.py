from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import TicketVarificationService

router = APIRouter(prefix="/ticket_varifications", tags=["Ticket Varifications"])

# -----------------
# SCHEMAS
# -----------------
class TicketVarificationCreate(BaseModel):
    ticket_id: int
    status_id: int
    varification: List[str]

class TicketVarificationUpdate(BaseModel):
    ticket_id: Optional[int] = None
    status_id: Optional[int] = None
    varification: Optional[List[str]] = None

class TicketVarificationResponse(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    status_id: int
    varification: List[str]

# -----------------
# ENDPOINTS
# -----------------
@router.post("", response_model=APIResponse[TicketVarificationResponse], status_code=status.HTTP_201_CREATED)
def create_varification(
    payload: TicketVarificationCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketVarificationService.create_varification(payload, current_user_id)
    return success_response(result, "Ticket verification created successfully", 201)

@router.get("", response_model=APIResponse[List[TicketVarificationResponse]])
def get_all_varifications(
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketVarificationService.get_all_varifications()
    return success_response(result, "Ticket verifications fetched successfully")

@router.get("/ticket/{ticket_id}", response_model=APIResponse[List[TicketVarificationResponse]])
def get_varifications_by_ticket(
    ticket_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketVarificationService.get_varifications_by_ticket(ticket_id)
    return success_response(result, "Ticket verifications fetched successfully")

@router.get("/{id}", response_model=APIResponse[TicketVarificationResponse])
def get_varification(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketVarificationService.get_varification_by_id(id)
    return success_response(result, "Ticket verification fetched successfully")

@router.put("/{id}", response_model=APIResponse[TicketVarificationResponse])
def update_varification(
    id: int,
    payload: TicketVarificationUpdate,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketVarificationService.update_varification(id, payload)
    return success_response(result, "Ticket verification updated successfully")

@router.delete("/{id}")
def delete_varification(
    id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketVarificationService.delete_varification(id)
    return success_response(None, "Ticket verification deleted successfully", 204)
