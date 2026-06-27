from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from database import get_db
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import AssignedTicketsService

router = APIRouter(prefix="/assigned-tickets", tags=["Assigned Tickets"])

class AssigneeInput(BaseModel):
    id: int
    send_mail: str = "Y"
    is_client: Optional[bool] = False

class AssignedTicketsUpdate(BaseModel):
    assignees: List[AssigneeInput]

@router.put("/{ticket_id}", response_model=APIResponse[dict])
def update_assigned_tickets(ticket_id: int, body: AssignedTicketsUpdate, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = AssignedTicketsService.update_assigned_tickets(ticket_id, body, db, current_user_id)
    return success_response(result, "Assigned tickets updated successfully")
