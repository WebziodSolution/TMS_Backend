from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from core.response import APIResponse, success_response
from .service import StatusService

router = APIRouter(prefix="/status", tags=["status"])

class StatusCreate(BaseModel):
    name: str

class StatusUpdate(BaseModel):
    name: str

class StatusResponse(BaseModel):
    id: int
    name: str

@router.post("", response_model=APIResponse[StatusResponse])
def create_status(status: StatusCreate):
    result = StatusService.create_status(status)
    return success_response(result, "Status created successfully", 201)

@router.get("", response_model=APIResponse[List[StatusResponse]])
def get_all_status():
    result = StatusService.get_all_status()
    return success_response(result, "Status items fetched successfully")

@router.get("/{status_id}", response_model=APIResponse[StatusResponse])
def get_status(status_id: int):
    result = StatusService.get_status(status_id)
    return success_response(result, "Status fetched successfully")

@router.put("/{status_id}", response_model=APIResponse[StatusResponse])
def update_status(status_id: int, status: StatusUpdate):
    result = StatusService.update_status(status_id, status)
    return success_response(result, "Status updated successfully")

@router.delete("/{status_id}")
def delete_status(status_id: int):
    StatusService.delete_status(status_id)
    return success_response(None, "Status deleted successfully", 204)
