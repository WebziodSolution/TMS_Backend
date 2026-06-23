from fastapi import APIRouter, Depends
from database import get_db
from schemas.user import UserRegister, SetPasswordReq, UserLogin, VerifyOTPReq
from core.response import success_response
from routes.tickets.service import get_current_user_id
from .service import AuthService

router = APIRouter(tags=["Authentication"])

@router.post("/register")
def register_user(user: UserRegister, db=Depends(get_db)):
    result = AuthService.register_user(user, db)
    return success_response(None, result["message"])

@router.post("/set-password")
def set_password(req: SetPasswordReq, db=Depends(get_db)):
    result = AuthService.set_password(req, db)
    return success_response(None, result["message"])

@router.post("/login")
def login(req: UserLogin, db=Depends(get_db)):
    result = AuthService.login(req, db)
    return success_response(result.get("data"), result.get("message"), result.get("status", 200))

@router.post("/verify-otp")
def verify_otp(req: VerifyOTPReq, db=Depends(get_db)):
    result = AuthService.verify_otp(req, db)
    return success_response(result["data"], result["message"])

@router.post("/forgot-password")
def forgot_password(email: str, db=Depends(get_db)):
    result = AuthService.forgot_password(email, db)
    return success_response(None, result["message"], result["status"])

@router.get("/verify-token")
def verify_token(token: str, db=Depends(get_db)):
    result = AuthService.verify_token(token, db)
    return success_response(result["user"], result["message"])


