from core.security import get_current_user_id
from fastapi import HTTPException
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from database import get_db
from core.response import APIResponse, success_response
from .service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments"])

class DepartmentCreate(BaseModel):
    name: str
    parent_department_id : Optional[int] = None

class DepartmentUpdate(BaseModel):
    name: str
    parent_department_id : Optional[int] = None

class DepartmentResponse(BaseModel):
    id: int
    name: str
    parent_department_id : Optional[int] = None

class DepartmentHierarchyItem(BaseModel):
    id: int
    name: str
    data: List['DepartmentHierarchyItem'] = []

DepartmentHierarchyItem.model_rebuild()

@router.post("", response_model=APIResponse[DepartmentResponse], status_code=status.HTTP_201_CREATED)
def create_department(dept: DepartmentCreate, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = DepartmentService.create_department(dept, db)
    return success_response(result, "Department created successfully", 201)

@router.get("/hierarchy", response_model=APIResponse[List[DepartmentHierarchyItem]])
def get_department_hierarchy(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = DepartmentService.get_department_hierarchy(db)
    return success_response(result, "Department hierarchy fetched successfully")

@router.get("", response_model=APIResponse[List[DepartmentResponse]])
def get_all_departments(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = DepartmentService.get_all_departments(db)
    return success_response(result, "Departments fetched successfully")

@router.get("/{dept_id}", response_model=APIResponse[DepartmentResponse])
def get_department(dept_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = DepartmentService.get_department(dept_id, db)
    return success_response(result, "Department fetched successfully")

@router.put("/{dept_id}", response_model=APIResponse[DepartmentResponse])
def update_department(dept_id: int, dept_update: DepartmentUpdate, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = DepartmentService.update_department(dept_id, dept_update, db)
    return success_response(result, "Department updated successfully")

@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    DepartmentService.delete_department(dept_id, db)
    return success_response(None, "Department deleted successfully", 204)
