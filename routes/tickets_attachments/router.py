from fastapi import HTTPException
from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from database import get_db
from core.response import success_response
from routes.tickets.service import get_current_user_id
from .service import TicketsAttachmentsService

router = APIRouter(prefix="/tickets/{ticket_id}/attachments", tags=["Tickets Attachments"])

@router.post("")
def upload_attachment(
    ticket_id: int, 
    file: UploadFile = File(...), 
    chunkIndex: int = Form(0),
    totalChunks: int = Form(1),
    fileName: str = Form(""),
    totalSize: int = Form(None),
    db=Depends(get_db), 
    current_user_id: int = Depends(get_current_user_id)
):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = TicketsAttachmentsService.upload_attachment(ticket_id, file, chunkIndex, totalChunks, fileName, totalSize, db, current_user_id)
    return success_response(
        {"id": result.get("id"), "file_name": result.get("file_name"), "file_URL": result.get("file_URL"), "status": result.get("status")}, 
        result.get("message")
    )

@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(ticket_id: int, attachment_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketsAttachmentsService.delete_attachment(ticket_id, attachment_id, db, current_user_id)
    return success_response(None, "Attachment deleted successfully", 204)
