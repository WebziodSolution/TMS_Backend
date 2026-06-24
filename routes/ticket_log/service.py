from fastapi import HTTPException
from database import get_db_connection
from datetime import datetime, timezone

def make_utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc)

def to_db_datetime(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

class TicketLogService:
    @staticmethod
    def _fetch_record(cursor, record_id):
        cursor.execute(
            "SELECT id, ticket_id, user_id, start_time, end_time, status, complete_date, note FROM ticket_log WHERE id = %s",
            (record_id,)
        )
        row = cursor.fetchone()
        if row:
            row['start_time'] = make_utc(row.get('start_time'))
            row['end_time'] = make_utc(row.get('end_time'))
            row['complete_date'] = make_utc(row.get('complete_date'))
        return row

    @staticmethod
    def execute_action(ticket_id: int, user_id: int, action: str, note: str = None):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
                
                if action in ["start", "resume"]:
                    # Create a new log entry
                    cursor.execute(
                        "INSERT INTO ticket_log (ticket_id, user_id, start_time, status) VALUES (%s, %s, %s, %s)",
                        (ticket_id, user_id, now_dt, 1)
                    )
                    conn.commit()
                    record_id = cursor.lastrowid

                    cursor.execute("UPDATE users SET is_working = 1 WHERE id = %s", (user_id,))
                    conn.commit()
                    
                    return TicketLogService._fetch_record(cursor, record_id)
                    
                elif action == "pause":
                    # Find the active running log
                    cursor.execute(
                        "SELECT id FROM ticket_log WHERE ticket_id = %s AND user_id = %s AND status = 1 ORDER BY id DESC LIMIT 1",
                        (ticket_id, user_id)
                    )
                    active = cursor.fetchone()
                    if not active:
                        raise HTTPException(status_code=400, detail="No active running timer found to pause.")
                    
                    # Update active log
                    cursor.execute(
                        "UPDATE ticket_log SET end_time = %s, status = 2, note = %s WHERE id = %s",
                        (now_dt, note, active['id'])
                    )
                    conn.commit()

                    cursor.execute("UPDATE users SET is_working = 0 WHERE id = %s", (user_id,))
                    conn.commit()
                    
                    return TicketLogService._fetch_record(cursor, active['id'])
                    
                elif action == "complete":
                    # Find any active logs (status 1 or 2)
                    cursor.execute(
                        "SELECT id, status FROM ticket_log WHERE ticket_id = %s AND user_id = %s AND status IN (1, 2)",
                        (ticket_id, user_id)
                    )
                    logs = cursor.fetchall()
                    if not logs:
                        raise HTTPException(status_code=400, detail="No active or paused timer logs to complete.")
                    
                    # Update status=1 (running) to set end_time as well
                    cursor.execute(
                        "UPDATE ticket_log SET end_time = %s, status = 0, complete_date = %s, note = %s WHERE ticket_id = %s AND user_id = %s AND status = 1",
                        (now_dt, now_dt, note, ticket_id, user_id)
                    )
                    # Update status=2 (paused) logs to complete
                    cursor.execute(
                        "UPDATE ticket_log SET status = 0, complete_date = %s, note = %s WHERE ticket_id = %s AND user_id = %s AND status = 2",
                        (now_dt, note, ticket_id, user_id)
                    )
                    conn.commit()
                    
                    cursor.execute("UPDATE users SET is_working = 0 WHERE id = %s", (user_id,))
                    conn.commit()
                    # Return the latest modified record
                    latest_id = logs[-1]['id'] if logs else None
                    if latest_id:
                        return TicketLogService._fetch_record(cursor, latest_id)
                    return None
                    
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_active_logs(ticket_id: int, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, ticket_id, user_id, start_time, end_time, status, complete_date, note FROM ticket_log WHERE ticket_id = %s AND user_id = %s AND status IN (1, 2) ORDER BY id ASC",
                    (ticket_id, user_id)
                )
                results = cursor.fetchall()
                for row in results:
                    row['start_time'] = make_utc(row.get('start_time'))
                    row['end_time'] = make_utc(row.get('end_time'))
                    row['complete_date'] = make_utc(row.get('complete_date'))
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_ticket_log_history(ticket_id: int, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, ticket_id, user_id, start_time, end_time, status, complete_date, note FROM ticket_log WHERE status != 1 AND ticket_id = %s AND user_id = %s ORDER BY id DESC",
                    (ticket_id, user_id)
                )
                results = cursor.fetchall()
                for row in results:
                    row['start_time'] = make_utc(row.get('start_time'))
                    row['end_time'] = make_utc(row.get('end_time'))
                    row['complete_date'] = make_utc(row.get('complete_date'))
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    # --- CRUD operations ---

    @staticmethod
    def create_log(payload):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ticket_log (ticket_id, user_id, start_time, end_time, status, complete_date, note) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (payload.ticket_id, payload.user_id, 
                     to_db_datetime(payload.start_time), 
                     to_db_datetime(payload.end_time), 
                     payload.status, 
                     to_db_datetime(payload.complete_date), 
                     payload.note)
                )
                conn.commit()
                record_id = cursor.lastrowid
                return TicketLogService._fetch_record(cursor, record_id)
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_log_by_id(log_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                record = TicketLogService._fetch_record(cursor, log_id)
                if not record:
                    raise HTTPException(status_code=404, detail="Ticket log not found")
                return record
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def update_log(log_id: int, payload):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check existence
                record = TicketLogService._fetch_record(cursor, log_id)
                if not record:
                    raise HTTPException(status_code=404, detail="Ticket log not found")
                
                # Build update query dynamically
                update_fields = []
                params = []
                
                for field, val in payload.dict(exclude_unset=True).items():
                    update_fields.append(f"{field} = %s")
                    if field in ['start_time', 'end_time', 'complete_date']:
                        params.append(to_db_datetime(val))
                    else:
                        params.append(val)
                
                if update_fields:
                    params.append(log_id)
                    query = f"UPDATE ticket_log SET {', '.join(update_fields)} WHERE id = %s"
                    cursor.execute(query, tuple(params))
                    conn.commit()
                
                return TicketLogService._fetch_record(cursor, log_id)
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def delete_log(log_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                record = TicketLogService._fetch_record(cursor, log_id)
                if not record:
                    raise HTTPException(status_code=404, detail="Ticket log not found")
                cursor.execute("DELETE FROM ticket_log WHERE id = %s", (log_id,))
                conn.commit()
                return True
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def check_current_work_status(user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT ticket_id FROM ticket_log WHERE user_id = %s AND status IN (1) ORDER BY id DESC LIMIT 1",
                    (user_id,)
                )
                results = cursor.fetchone()
                if not results:
                    return False
                return True
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()