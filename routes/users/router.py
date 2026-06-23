from fastapi import HTTPException
from core.security import get_current_user_id
from fastapi import APIRouter, Depends, status, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from database import get_db
from core.response import APIResponse, success_response
from .service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

# -----------------
# SCHEMAS
# -----------------
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role_id: int
    password: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    is_sms_active: Optional[bool] = False
    is_active: Optional[bool] = True
    report_to: Optional[int] = None
    company_id: Optional[int] = None
    work_hours: Optional[float] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None
    password: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    is_sms_active: Optional[bool] = None
    is_active: Optional[bool] = None
    report_to: Optional[int] = None
    company_id: Optional[int] = None
    work_hours: Optional[float] = None

class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    role_id: int
    is_active: bool
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    zip: Optional[str]
    phone: Optional[str]
    is_sms_active: bool
    report_to: Optional[int] = None
    company_id: Optional[int] = None
    work_hours: Optional[float] = None

class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str


# Recursive model for hierarchy
class UserHierarchyItem(BaseModel):
    id: int
    name: str
    data: List['UserHierarchyItem'] = []

# Resolve forward reference
UserHierarchyItem.model_rebuild()
# -----------------
# ENDPOINTS
# -----------------

@router.get("/hierarchy", response_model=APIResponse[List[UserHierarchyItem]])
def get_user_hierarchy(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_user_hierarchy(db)
    return success_response(result, "User hierarchy fetched successfully")

@router.get("", response_model=APIResponse[List[UserResponse]])
def get_all_users(company_id: Optional[int] = Query(None), db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_all_users(db, company_id)
    return success_response(result, "Users fetched successfully")

@router.get("/filter", response_model=APIResponse[List[UserResponse]])
def filter_users(role_ids: Optional[List[int]] = Query(None), db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.filter_users(db, role_ids)
    return success_response(result, "Users filtered successfully")

@router.get("/customers", response_model=APIResponse[List[UserResponse]])
def get_customers(company_id: Optional[int] = Query(None), db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_customers(db, company_id)
    return success_response(result, "Customers fetched successfully")

@router.get("/get/all/admins", response_model=APIResponse[List[UserResponse]])
def get_admins(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_admins(db)
    return success_response(result, "Admins fetched successfully")

@router.get("/non-customers", response_model=APIResponse[List[UserResponse]])
def get_non_customers(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_non_customers(db)
    return success_response(result, "Non-customer users fetched successfully")

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
def get_user(user_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.get_user(user_id, db)
    return success_response(result, "User fetched successfully")

@router.post("", response_model=APIResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.create_user(user, db)
    return success_response(result, "User created successfully", 201)

@router.put("/{user_id}", response_model=APIResponse[UserResponse])
def update_user(user_id: int, user_update: UserUpdate, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.update_user(user_id, user_update, db)
    return success_response(result, "User updated successfully")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    UserService.delete_user(user_id, db)
    return success_response(None, "User deleted successfully", 204)

@router.post("/{user_id}/send-credentials", response_model=APIResponse[bool])
def send_login_credentials(user_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.send_login_credentials(user_id, db)
    return success_response(result, "Credentials email sent successfully")

@router.post("/change-password", response_model=APIResponse[bool])
def change_password(req: ChangePasswordReq, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = UserService.change_password(current_user_id, req.current_password, req.new_password, db)
    if result["status"] != 200:
        return success_response(None, result["message"], result["status"])
    return success_response(True, "Password changed successfully")

