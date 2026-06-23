from fastapi import HTTPException
from services.file_service import FileService
import os
import shutil

import logging
logger = logging.getLogger(__name__)

class CompanyService:

    @staticmethod
    def get_users_by_company(db):
        with db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.id AS company_id,
                    c.company_name,
                    u.id AS user_id,
                    u.first_name,
                    u.last_name
                FROM companies c
                LEFT JOIN users u ON c.id = u.company_id
                ORDER BY c.id, u.id
            """)
            rows = cursor.fetchall()

        result = []
        current_company = None
        current_company_name = None
        current_users = []

        for row in rows:
            if current_company != row['company_id']:
                # Save previous company
                if current_company is not None:
                    result.append({
                        "id": current_company,
                        "name": current_company_name,
                        "data": current_users
                    })
                # Start new company
                current_company = row['company_id']
                current_company_name = row['company_name']
                # Check if this row has a user
                if row['user_id'] is not None:
                    full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
                    current_users = [{"id": row['user_id'], "name": full_name}]
                else:
                    current_users = []
            else:
                # Same company: add user if exists
                if row['user_id'] is not None:
                    full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
                    current_users.append({"id": row['user_id'], "name": full_name})

        # Append the last company
        if current_company is not None:
            result.append({
                "id": current_company,
                "name": current_company_name,
                "data": current_users
            })

        return result

    @staticmethod
    def get_all(db):
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM companies ORDER BY id DESC")
            return cursor.fetchall()

    @staticmethod
    def get_by_id(company_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
            company = cursor.fetchone()
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            return company

    @staticmethod
    def _check_duplicate_name(name: str, db, exclude_id: int = None):
        with db.cursor() as cursor:
            if exclude_id:
                cursor.execute(
                    "SELECT id FROM companies WHERE company_name = %s AND id != %s",
                    (name, exclude_id)
                )
            else:
                cursor.execute(
                    "SELECT id FROM companies WHERE company_name = %s",
                    (name,)
                )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Company name already exists")

    @staticmethod
    def _save_logo(file, company_id: int, user_id: int):
        """Save logo file and return the relative URL path."""
        if not file:
            return None

        rel_path = f"usercontent/{user_id}/company/{company_id}/logo"
        target_dir = FileService.get_upload_path(rel_path)

        # Clean existing logo directory
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        os.makedirs(target_dir, exist_ok=True)

        file_name = file.filename
        file_path = os.path.join(target_dir, file_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Optimize image
        optimized_path = FileService.optimize_image(file_path)
        if optimized_path != file_path:
            actual_file_name = os.path.basename(optimized_path)
            try:
                os.remove(file_path)
            except Exception as e:
                logger.info(f"Error removing original file: {e}")
            return f"/{rel_path}/{actual_file_name}"

        return f"/{rel_path}/{file_name}"

    @staticmethod
    def _delete_logo_files(company_id: int, db):
        """Delete logo files from disk for a company."""
        with db.cursor() as cursor:
            cursor.execute("SELECT logo, created_by FROM companies WHERE id = %s", (company_id,))
            company = cursor.fetchone()
            if not company or not company.get('logo'):
                return

            logo_url = company['logo']
            clean_url = logo_url.lstrip('/')
            file_path = FileService.get_upload_path(clean_url)

            if os.path.exists(file_path):
                try:
                    logo_dir = os.path.dirname(file_path)
                    if os.path.exists(logo_dir):
                        shutil.rmtree(logo_dir)
                except Exception as e:
                    logger.info(f"Error deleting logo files: {e}")

    @staticmethod
    def create(company_name, email, phone, address, city, state, country, zip_code, logo_file, user_id, db):
        CompanyService._check_duplicate_name(company_name, db)

        with db.cursor() as cursor:
            cursor.execute(
                """INSERT INTO companies 
                   (company_name, email, phone, address, city, state, country, zip, created_by) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (company_name, email, phone, address, city, state, country, zip_code, user_id)
            )
            db.commit()
            company_id = cursor.lastrowid

        # Save logo if provided
        logo_url = None
        if logo_file:
            logo_url = CompanyService._save_logo(logo_file, company_id, user_id)
            with db.cursor() as cursor:
                cursor.execute("UPDATE companies SET logo = %s WHERE id = %s", (logo_url, company_id))
                db.commit()

        return {"id": company_id, "company_name": company_name, "logo": logo_url}

    @staticmethod
    def update(company_id, company_name, email, phone, address, city, state, country, zip_code, logo_file, remove_logo, user_id, db):
        # Verify exists
        CompanyService.get_by_id(company_id, db)
        CompanyService._check_duplicate_name(company_name, db, exclude_id=company_id)

        logo_url = None
        if logo_file:
            logo_url = CompanyService._save_logo(logo_file, company_id, user_id)
        elif remove_logo:
            # Remove existing logo
            CompanyService._delete_logo_files(company_id, db)
            logo_url = ""

        with db.cursor() as cursor:
            if logo_url is not None:
                cursor.execute(
                    """UPDATE companies SET 
                       company_name=%s, email=%s, phone=%s, address=%s, city=%s, state=%s, country=%s, zip=%s, logo=%s
                       WHERE id=%s""",
                    (company_name, email, phone, address, city, state, country, zip_code, logo_url if logo_url else None, company_id)
                )
            else:
                cursor.execute(
                    """UPDATE companies SET 
                       company_name=%s, email=%s, phone=%s, address=%s, city=%s, state=%s, country=%s, zip=%s
                       WHERE id=%s""",
                    (company_name, email, phone, address, city, state, country, zip_code, company_id)
                )
            db.commit()

        return {"id": company_id, "company_name": company_name}

    @staticmethod
    def delete(company_id: int, db):
        CompanyService._delete_logo_files(company_id, db)

        with db.cursor() as cursor:
            cursor.execute("DELETE FROM companies WHERE id = %s", (company_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Company not found")
            db.commit()
