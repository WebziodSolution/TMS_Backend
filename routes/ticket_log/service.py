import json
from datetime import datetime, timezone
from fastapi import HTTPException
from database import get_db_connection

class TicketLogService:
    @staticmethod
    def create_log(data, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                internal_qa_str = json.dumps(data.internal_qa) if data.internal_qa is not None else None
                
                # Format due_date if provided
                due_date_val = data.due_date
                if due_date_val:
                    if hasattr(due_date_val, 'astimezone'):
                        due_date_val = due_date_val.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        due_date_val = str(due_date_val)[:19].replace('T', ' ')

                sql = """
                    INSERT INTO ticket_log (ticket_id, user_id, status_id, due_date, internal_qa)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (data.ticket_id, user_id, data.status_id, due_date_val, internal_qa_str))
                conn.commit()
                new_id = cursor.lastrowid
                
                return {
                    "id": new_id,
                    "ticket_id": data.ticket_id,
                    "user_id": user_id,
                    "status_id": data.status_id,
                    "due_date": data.due_date,
                    "internal_qa": data.internal_qa
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_all_logs():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, due_date, internal_qa, created_date FROM ticket_log ORDER BY id DESC")
                results = cursor.fetchall()
                for row in results:
                    if row.get('internal_qa'):
                        try:
                            row['internal_qa'] = json.loads(row['internal_qa'])
                        except Exception:
                            row['internal_qa'] = [row['internal_qa']]
                    else:
                        row['internal_qa'] = None
                return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_log_by_id(log_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, due_date, internal_qa, created_date FROM ticket_log WHERE id = %s", (log_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ticket status log not found")
                if row.get('internal_qa'):
                    try:
                        row['internal_qa'] = json.loads(row['internal_qa'])
                    except Exception:
                        row['internal_qa'] = [row['internal_qa']]
                else:
                    row['internal_qa'] = None
                return row
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_logs_by_ticket(ticket_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT tl.id, tl.ticket_id, tl.user_id, tl.status_id, tl.due_date, tl.internal_qa, tl.created_date,
                           CONCAT(u.first_name, ' ', u.last_name) as user_name,
                           s.name as status_name
                    FROM ticket_log tl
                    LEFT JOIN users u ON tl.user_id = u.id
                    LEFT JOIN status s ON tl.status_id = s.id
                    WHERE tl.ticket_id = %s
                    ORDER BY tl.created_date ASC, tl.id ASC
                """
                cursor.execute(sql, (ticket_id,))
                rows = cursor.fetchall()

                current_status_name = None
                current_due_date = None

                processed_list = []
                for row in rows:
                    raw_qa = row.get('internal_qa')
                    parsed_qa = None
                    if raw_qa:
                        try:
                            parsed_qa = json.loads(raw_qa)
                        except Exception:
                            parsed_qa = [raw_qa]

                    new_status_name = row['status_name'] if row['status_id'] else None
                    old_status_name = current_status_name

                    new_due_date = str(row['due_date'])[:10] if row['due_date'] else None
                    old_due_date = str(current_due_date)[:10] if current_due_date else None

                    if row['status_id']:
                        current_status_name = row['status_name']
                    if row['due_date']:
                        current_due_date = row['due_date']

                    user_display = row.get('user_name') if row.get('user_name') and row['user_name'].strip() else f"User {row['user_id']}"

                    created_str = str(row['created_date'])
                    if hasattr(row['created_date'], 'strftime'):
                        created_str = row['created_date'].strftime('%Y-%m-%dT%H:%M:%SZ')
                    elif created_str and 'T' not in created_str:
                        created_str = created_str.replace(' ', 'T') + ('Z' if not created_str.endswith('Z') else '')

                    item = {
                        "id": row['id'],
                        "ticket_id": row['ticket_id'],
                        "user_id": row['user_id'],
                        "user_name": user_display,
                        "status_id": row['status_id'],
                        "new_status_name": new_status_name,
                        "old_status_name": old_status_name,
                        "new_due_date": new_due_date,
                        "old_due_date": old_due_date,
                        "internal_qa": parsed_qa,
                        "created_date": created_str
                    }
                    processed_list.append(item)

                processed_list.reverse()
                return processed_list
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def update_log(log_id: int, data):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, ticket_id, user_id, status_id, due_date, internal_qa FROM ticket_log WHERE id = %s", (log_id,))
                existing = cursor.fetchone()
                if not existing:
                    raise HTTPException(status_code=404, detail="Ticket status log not found")

                ticket_id = data.ticket_id if data.ticket_id is not None else existing['ticket_id']
                status_id = data.status_id if data.status_id is not None else existing['status_id']
                due_date_val = data.due_date if data.due_date is not None else existing['due_date']
                
                if due_date_val and hasattr(due_date_val, 'astimezone'):
                    due_date_str = due_date_val.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                elif due_date_val:
                    due_date_str = str(due_date_val)[:19].replace('T', ' ')
                else:
                    due_date_str = None

                if data.internal_qa is not None:
                    internal_qa_str = json.dumps(data.internal_qa)
                    internal_qa_val = data.internal_qa
                else:
                    internal_qa_str = existing['internal_qa']
                    try:
                        internal_qa_val = json.loads(existing['internal_qa']) if existing['internal_qa'] else None
                    except Exception:
                        internal_qa_val = [existing['internal_qa']] if existing['internal_qa'] else None

                sql = "UPDATE ticket_log SET ticket_id = %s, status_id = %s, due_date = %s, internal_qa = %s WHERE id = %s"
                cursor.execute(sql, (ticket_id, status_id, due_date_str, internal_qa_str, log_id))
                conn.commit()

                return {
                    "id": log_id,
                    "ticket_id": ticket_id,
                    "user_id": existing['user_id'],
                    "status_id": status_id,
                    "due_date": due_date_val,
                    "internal_qa": internal_qa_val
                }
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
                cursor.execute("SELECT id FROM ticket_log WHERE id = %s", (log_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Ticket status log not found")

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
