from fastapi import HTTPException
from database import get_db_connection

class StatusService:
    @staticmethod
    def create_status(status):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM status WHERE name = %s", (status.name,))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Status with this name already exists")
                
                cursor.execute("INSERT INTO status (name) VALUES (%s)", (status.name,))
                conn.commit()
                new_id = cursor.lastrowid
                return {"id": new_id, "name": status.name}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_all_status():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM status ORDER BY id DESC")
                return cursor.fetchall()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_status(status_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM status WHERE id = %s", (status_id,))
                result = cursor.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Status not found")
                return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def update_status(status_id: int, status):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM status WHERE id = %s", (status_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Status not found")
                
                cursor.execute("SELECT id FROM status WHERE name = %s AND id != %s", (status.name, status_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Another status with this name already exists")
                
                cursor.execute("UPDATE status SET name = %s WHERE id = %s", (status.name, status_id))
                conn.commit()
                return {"id": status_id, "name": status.name}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def delete_status(status_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM status WHERE id = %s", (status_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Status not found")
                
                cursor.execute("DELETE FROM status WHERE id = %s", (status_id,))
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()
