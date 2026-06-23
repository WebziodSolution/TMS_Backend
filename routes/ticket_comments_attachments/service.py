from fastapi import HTTPException
from services.file_service import FileService
import os
import shutil

class TicketCommentAttachmentsService:

    @staticmethod
    def upload_attachment(comment_id: int, file, chunkIndex: int, totalChunks: int, fileName: str, totalSize: int, db, current_user_id: int):
        MAX_FILE_SIZE = 100 * 1024 * 1024 # 100MB
        if totalSize and int(totalSize) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds the 100MB limit")
            
        actual_file_name = fileName if fileName else file.filename
        
        with db.cursor() as cursor:
            # Get ticket_id for the path
            cursor.execute("SELECT ticket_id FROM ticket_comments WHERE id = %s", (comment_id,))
            comment_res = cursor.fetchone()
            if not comment_res:
                raise HTTPException(status_code=404, detail="Comment not found")
            
            ticket_id = comment_res['ticket_id']
            u_id = current_user_id or 0
            
            # Check for existing pending attachment entry or create new one
            cursor.execute(
                "SELECT id FROM ticket_comments_attachments WHERE ticket_comment_id=%s AND file_name=%s ORDER BY id DESC LIMIT 1",
                (comment_id, actual_file_name)
            )
            existing = cursor.fetchone()
            
            if existing and chunkIndex > 0:
                attachment_id = existing['id']
            else:
                cursor.execute(
                    "INSERT INTO ticket_comments_attachments (ticket_comment_id, file_name, file_url, created_by) VALUES (%s, %s, %s, %s)",
                    (comment_id, actual_file_name, "", current_user_id)
                )
                db.commit()
                attachment_id = cursor.lastrowid
            
            rel_path = f"usercontent/{u_id}/ticket/{ticket_id}/attachments/comments/{comment_id}/{attachment_id}"
            target_dir = FileService.get_upload_path(rel_path)
            
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, actual_file_name)
            
            mode = "ab" if chunkIndex > 0 else "wb"
            with open(file_path, mode) as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            file_url = f"/{rel_path}/{actual_file_name}"
            
            if chunkIndex == totalChunks - 1:
                # Last chunk
                optimized_path = FileService.optimize_image(file_path)
                if optimized_path != file_path:
                    actual_file_name = os.path.basename(optimized_path)
                    file_url = f"/{rel_path}/{actual_file_name}"
                    try: os.remove(file_path)
                    except: pass

                cursor.execute("UPDATE ticket_comments_attachments SET file_url=%s, file_name=%s WHERE id=%s", (file_url, actual_file_name, attachment_id))
                db.commit()
                from datetime import datetime
                return {"id": attachment_id, "file_name": actual_file_name, "file_url": file_url, "created_date": datetime.now(), "status": "completed", "message": "File uploaded successfully"}
                
            return {"id": attachment_id, "file_name": actual_file_name, "status": "chunk_uploaded", "message": "Chunk uploaded"}

    @staticmethod
    def delete_attachment(comment_id: int, attachment_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT file_url FROM ticket_comments_attachments WHERE id=%s AND ticket_comment_id=%s", (attachment_id, comment_id))
            attachment = cursor.fetchone()
            
            if not attachment:
                raise HTTPException(status_code=404, detail="Attachment not found")
            
            file_url = attachment['file_url']
            
            cursor.execute("DELETE FROM ticket_comments_attachments WHERE id=%s", (attachment_id,))
            db.commit()
            
            if file_url:
                clean_url = file_url.lstrip('/')
                file_path = FileService.get_upload_path(clean_url)
                
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        # Remove the attachment directory itself if empty
                        att_dir = os.path.dirname(file_path)
                        if os.path.exists(att_dir) and not os.listdir(att_dir):
                            shutil.rmtree(att_dir)
                    except: pass
