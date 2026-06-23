from fastapi import APIRouter, Depends
from database import get_db
from core.response import success_response
from .service import SystemService

router = APIRouter(tags=["Navigation"])

@router.get("/api/navigation")
def get_navigation_menu(user_email: str, db=Depends(get_db)):
    result = SystemService.get_navigation_menu(user_email, db)
    return success_response({"menu": result}, "Navigation menu fetched successfully")
