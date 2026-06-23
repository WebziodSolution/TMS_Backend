from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from core.response import APIResponse, success_response
from core.security import get_current_user_id
from database import get_db_connection
from .service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/daily", response_model=APIResponse)
def get_daily_report(
    date: str,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = ReportsService.get_daily_report(date, current_user_id)
    return success_response(result, "Daily report fetched successfully")

@router.get("/monthly", response_model=APIResponse)
def get_monthly_report(
    start_date: str,
    end_date: str,
    group_by: str = "ticket",
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")     

    result = ReportsService.get_monthly_report(start_date, end_date, group_by)
    return success_response(result, "Monthly report fetched successfully")

@router.get("/monthly/export")
def export_monthly_report(
    start_date: str,
    end_date: str,
    group_by: str = "ticket",
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")     

    excel_stream = ReportsService.export_monthly_report_excel(start_date, end_date, group_by)
    filename = f"monthly_report_{group_by}_{start_date}_to_{end_date}.xlsx"
    
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/daily/export")
def export_daily_report(
    date: str,
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")     

    excel_stream = ReportsService.export_daily_report_excel(date, current_user_id)
    filename = f"daily_report_{date}.xlsx"
    
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

