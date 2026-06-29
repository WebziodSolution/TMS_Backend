import json
from fastapi import HTTPException
from database import get_db_connection

class TicketVarificationService:
    @staticmethod
    def create_varification(data, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                varification_str = json.dumps(data.varification)
                sql = """
                    INSERT INTO ticket_varifications (ticket_id, user_id, status_id, varification)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (data.ticket_id, user_id, data.status_id, varification_str))
                conn.commit()
                new_id = cursor.lastrowid
                return {
                    "id": new_id,
                    "ticket_id": data.ticket_id,
                    "user_id": user_id,
                    "status_id": data.status_id,
                    "varification": data.varification
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_all_varifications():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, varification FROM ticket_varifications ORDER BY id DESC")
                results = cursor.fetchall()
                for row in results:
                    if row.get('varification'):
                        try:
                            row['varification'] = json.loads(row['varification'])
                        except Exception:
                            row['varification'] = [row['varification']]
                    else:
                        row['varification'] = []
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_varification_by_id(varification_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, varification FROM ticket_varifications WHERE id = %s", (varification_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ticket verification not found")
                if row.get('varification'):
                    try:
                        row['varification'] = json.loads(row['varification'])
                    except Exception:
                        row['varification'] = [row['varification']]
                else:
                    row['varification'] = []
                return row
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_varifications_by_ticket(ticket_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, varification FROM ticket_varifications WHERE ticket_id = %s ORDER BY id DESC", (ticket_id,))
                results = cursor.fetchall()
                for row in results:
                    if row.get('varification'):
                        try:
                            row['varification'] = json.loads(row['varification'])
                        except Exception:
                            row['varification'] = [row['varification']]
                    else:
                        row['varification'] = []
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def update_varification(varification_id: int, data):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, varification FROM ticket_varifications WHERE id = %s", (varification_id,))
                existing = cursor.fetchone()
                if not existing:
                    raise HTTPException(status_code=404, detail="Ticket verification not found")

                ticket_id = data.ticket_id if data.ticket_id is not None else existing['ticket_id']
                status_id = data.status_id if data.status_id is not None else existing['status_id']
                
                if data.varification is not None:
                    varification_str = json.dumps(data.varification)
                    varification_val = data.varification
                else:
                    varification_str = existing['varification']
                    try:
                        varification_val = json.loads(existing['varification'])
                    except Exception:
                        varification_val = [existing['varification']]

                sql = "UPDATE ticket_varifications SET ticket_id = %s, status_id = %s, varification = %s WHERE id = %s"
                cursor.execute(sql, (ticket_id, status_id, varification_str, varification_id))
                conn.commit()

                return {
                    "id": varification_id,
                    "ticket_id": ticket_id,
                    "user_id": existing['user_id'],
                    "status_id": status_id,
                    "varification": varification_val
                }
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def delete_varification(varification_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM ticket_varifications WHERE id = %s", (varification_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Ticket verification not found")

                cursor.execute("DELETE FROM ticket_varifications WHERE id = %s", (varification_id,))
                conn.commit()
                return True
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()
