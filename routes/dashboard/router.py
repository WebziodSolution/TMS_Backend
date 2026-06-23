from fastapi import APIRouter, Depends
from database import get_db
from routes.tickets.service import get_current_user_id
from core.response import success_response
from .service import DashboardService

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard")
def get_dashboard_data(db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    result = DashboardService.get_dashboard_data(current_user_id, db)
    return success_response(result, "Dashboard data fetched successfully")
