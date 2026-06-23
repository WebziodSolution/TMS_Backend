from core.security import get_current_user_id
from fastapi import HTTPException
from fastapi import APIRouter, Depends, status, Request
from database import get_db
from core.response import success_response
from .service import RoleService

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.get("")
def get_all_roles(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = RoleService.get_all_roles(db)
    return success_response(result, "Roles fetched successfully")


@router.get("/actions/all")
def get_all_actions(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = RoleService.get_all_actions(db)
    return success_response(result, "Actions fetched successfully")


@router.get("/permissions/{role_id}")
def get_permissions_matrix(role_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = RoleService.get_permissions_matrix(role_id, db)
    return success_response(result, "Permissions fetched successfully")


@router.get("/{role_id}")
def get_role_by_id(role_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = RoleService.get_role_by_id(role_id, db)
    return success_response(result, "Role fetched successfully")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(request: Request, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    result = RoleService.create_role(data, db)
    return success_response(result, "Role created successfully", 201)


@router.put("/{role_id}")
async def update_role(role_id: int, request: Request, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    result = RoleService.update_role(role_id, data, db)
    return success_response(result, "Role updated successfully")


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    RoleService.delete_role(role_id, db)
    return success_response(None, "Role deleted successfully", 204)
