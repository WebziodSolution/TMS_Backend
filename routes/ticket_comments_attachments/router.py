from fastapi import HTTPException
from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from database import get_db
from core.response import success_response
from routes.tickets.service import get_current_user_id
from .service import TicketCommentAttachmentsService

router = APIRouter(prefix="/ticket_comments/{comment_id}/attachments", tags=["Ticket Comment Attachments"])

@router.post("")
def upload_comment_attachment(
    comment_id: int, 
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
    result = TicketCommentAttachmentsService.upload_attachment(comment_id, file, chunkIndex, totalChunks, fileName, totalSize, db, current_user_id)
    return success_response(
        {"id": result.get("id"), "file_name": result.get("file_name"), "file_url": result.get("file_url"), "created_date": result.get("created_date"),"created_by": result.get("created_by"),"status": result.get("status")}, 
        result.get("message")
    )

@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment_attachment(comment_id: int, attachment_id: int, db=Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    TicketCommentAttachmentsService.delete_attachment(comment_id, attachment_id, db, current_user_id)
    return success_response(None, "Attachment deleted successfully", 204)
