from fastapi import HTTPException
from database import get_db_connection

class TodayTicketWorkService:
    @staticmethod
    def upsert_work_log(hours, minutes, date, note, ticket_id, user_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check if record already exists
                cursor.execute(
                    "SELECT id FROM today_ticket_work WHERE date = %s AND ticket_id = %s AND user_id = %s",
                    (date, ticket_id, user_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update
                    record_id = existing['id']
                    cursor.execute(
                        "UPDATE today_ticket_work SET hours = %s, minutes = %s, note = %s WHERE id = %s",
                        (hours, minutes, note, record_id)
                    )
                    conn.commit()
                else:
                    # Create
                    cursor.execute(
                        "INSERT INTO today_ticket_work (hours, minutes, date, note, ticket_id, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                        (hours, minutes, date, note, ticket_id, user_id)
                    )
                    conn.commit()
                    record_id = cursor.lastrowid
                
                # Fetch and return the updated/created record
                cursor.execute(
                    "SELECT id, hours, minutes, date, note, ticket_id, user_id FROM today_ticket_work WHERE id = %s",
                    (record_id,)
                )
                result = cursor.fetchone()
                if result and 'date' in result and result['date']:
                    result['date'] = result['date'].strftime('%Y-%m-%d')
                return result
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_work_logs(user_id, ticket_id, date=None):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if date:
                    cursor.execute(
                        "SELECT id, hours, minutes, date, note, ticket_id, user_id FROM today_ticket_work WHERE user_id = %s AND ticket_id = %s AND date = %s",
                        (user_id, ticket_id, date)
                    )
                else:
                    cursor.execute(
                        "SELECT id, hours, minutes, date, note, ticket_id, user_id FROM today_ticket_work WHERE user_id = %s AND ticket_id = %s ORDER BY date DESC",
                        (user_id, ticket_id)
                    )
                results = cursor.fetchall()
                for r in results:
                    if r.get('date'):
                        r['date'] = r['date'].strftime('%Y-%m-%d')
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_work_log_by_id(log_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, hours, minutes, date, note, ticket_id, user_id FROM today_ticket_work WHERE id = %s",
                    (log_id,)
                )
                result = cursor.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Work log not found")
                if result.get('date'):
                    result['date'] = result['date'].strftime('%Y-%m-%d')
                return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def delete_work_log(log_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM today_ticket_work WHERE id = %s", (log_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Work log not found")
                
                cursor.execute("DELETE FROM today_ticket_work WHERE id = %s", (log_id,))
                conn.commit()
                return True
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()
