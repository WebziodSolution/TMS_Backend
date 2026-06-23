from fastapi import Depends
from core.security import get_current_user_id
from fastapi import HTTPException
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from core.response import APIResponse, success_response
from .service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str
    client_id: int
    project_type: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: str
    client_id: int
    project_type: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    client_id: int
    project_type: Optional[str] = None
    client_name: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    ticket_count: int
    ticket_titles: List[str]

@router.post("", response_model=APIResponse[ProjectResponse])
def create_project(project: ProjectCreate,current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = ProjectService.create_project(project)
    return success_response(result, "Project created successfully", 201)

@router.get("", response_model=APIResponse[List[ProjectResponse]])
def get_all_projects(current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = ProjectService.get_all_projects()
    return success_response(result, "Projects fetched successfully")

@router.get("/{project_id}", response_model=APIResponse[ProjectResponse])
def get_project(project_id: int,current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = ProjectService.get_project(project_id)
    return success_response(result, "Project fetched successfully")

@router.put("/{project_id}", response_model=APIResponse[ProjectResponse])
def update_project(project_id: int, project: ProjectUpdate,current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = ProjectService.update_project(project_id, project)
    return success_response(result, "Project updated successfully")

@router.delete("/{project_id}")
def delete_project(project_id: int,current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ProjectService.delete_project(project_id)
    return success_response(None, "Project deleted successfully")
