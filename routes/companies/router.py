from fastapi import HTTPException
from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from typing import Optional
from database import get_db
from core.response import success_response
from routes.tickets.service import get_current_user_id
from .service import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])

@router.get("/getAllUsers")
def get_companies_with_users(
    db=Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = CompanyService.get_users_by_company(db)
    return success_response(result, "Companies with users fetched successfully")

@router.get("")
def get_all_companies(db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = CompanyService.get_all(db)
    return success_response(result, "Companies fetched successfully")


@router.get("/{company_id}")
def get_company(company_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = CompanyService.get_by_id(company_id, db)
    return success_response(result, "Company fetched successfully")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(
    company_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    zip: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    db=Depends(get_db),
   current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = CompanyService.create(
        company_name, email, phone, address, city, state, country, zip,
        logo, current_user_id, db
    )
    return success_response(result, "Company created successfully", 201)


@router.put("/{company_id}")
def update_company(
    company_id: int,
    company_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    zip: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    remove_logo: Optional[str] = Form(None),
    db=Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    should_remove = remove_logo == "true"
    result = CompanyService.update(
        company_id, company_name, email, phone, address, city, state, country, zip,
        logo, should_remove, current_user_id, db
    )
    return success_response(result, "Company updated successfully")


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db=Depends(get_db),current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    CompanyService.delete(company_id, db)