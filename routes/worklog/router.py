from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from .service import WorkLogService

router = APIRouter(prefix="/worklog", tags=["Work Log"])

@router.get("", response_model=APIResponse)
def get_work_logs(
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = WorkLogService.get_work_logs(
        login_user_id=current_user_id,
        date_from=date_from,
        date_to=date_to
    )
    return success_response(result, "Work logs fetched successfully")
