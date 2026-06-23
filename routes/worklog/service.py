from fastapi import HTTPException
from database import get_db_connection
from datetime import datetime, date, timezone
import calendar

class WorkLogService:
    @staticmethod
    def get_work_logs(login_user_id: int, date_from: str = None, date_to: str = None):
        # 1. Resolve date range
        today = date.today()
        if not date_from:
            date_from = date(today.year, today.month, 1).strftime("%Y-%m-%d")
        if not date_to:
            last_day = calendar.monthrange(today.year, today.month)[1]
            date_to = date(today.year, today.month, last_day).strftime("%Y-%m-%d")

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 2. Get login user's role
                cursor.execute("""
                    SELECT u.role_id, r.name as role_name 
                    FROM users u
                    JOIN roles r ON u.role_id = r.id
                    WHERE u.id = %s
                """, (login_user_id,))
                user_role_info = cursor.fetchone()
                if not user_role_info:
                    raise HTTPException(status_code=404, detail="User not found")
                
                role_id = user_role_info['role_id']
                role_name = user_role_info['role_name']

                # 3. Determine user list based on role
                # role_id = 1 (Administrator), 2 (Developer), 4 (Manager)
                if role_id == 2: # Developer
                    cursor.execute("""
                        SELECT id, first_name, last_name, role_id
                        FROM users
                        WHERE id = %s
                    """, (login_user_id,))
                elif role_id == 5: # Manager
                    cursor.execute("""
                        SELECT id, first_name, last_name, role_id 
                        FROM users 
                        WHERE id = %s OR report_to = %s
                    """, (login_user_id, login_user_id))
                elif role_id == 1: # Administrator
                    cursor.execute("""
                        SELECT id, first_name, last_name, role_id 
                        FROM users
                    """)
                else:
                    raise HTTPException(status_code=403, detail="Role not authorized to view work logs")
                
                target_users = cursor.fetchall()
                if not target_users:
                    return {
                        "role_id": role_id,
                        "role_name": role_name,
                        "users": [],
                        "date_from": date_from,
                        "date_to": date_to
                    }
                
                user_ids = [u['id'] for u in target_users]
                
                # Fetch worked minutes from today_ticket_work
                format_strings = ','.join(['%s'] * len(user_ids))
                cursor.execute(f"""
                    SELECT 
                        user_id,
                        ticket_id,
                        SUM(CAST(hours AS UNSIGNED) * 60 + CAST(minutes AS UNSIGNED)) AS total_worked_minutes
                    FROM today_ticket_work
                    WHERE user_id IN ({format_strings})
                      AND date >= %s AND date <= %s
                    GROUP BY user_id, ticket_id
                """, tuple(user_ids + [date_from, date_to]))
                worked_times = cursor.fetchall()
                
                worked_map = {}
                for wt in worked_times:
                    worked_map[(wt['user_id'], wt['ticket_id'])] = wt['total_worked_minutes']
                
                # Fetch notes from today_ticket_work
                cursor.execute(f"""
                    SELECT 
                        user_id,
                        ticket_id,
                        note
                    FROM today_ticket_work
                    WHERE user_id IN ({format_strings})
                      AND date >= %s AND date <= %s
                      AND note IS NOT NULL AND note != ''
                """, tuple(user_ids + [date_from, date_to]))
                notes_res = cursor.fetchall()
                
                notes_map = {}
                for nr in notes_res:
                    key = (nr['user_id'], nr['ticket_id'])
                    notes_map.setdefault(key, []).append(nr['note'])

                # 4. Fetch logs for all target users within date range
                query = f"""
                    SELECT 
                        tl.id,
                        tl.ticket_id,
                        tl.user_id,
                        CONCAT(u.first_name, ' ', u.last_name) AS user_name,
                        p.name AS project_name,
                        t.ticket_no,
                        t.title AS ticket_name,
                        tl.start_time,
                        tl.end_time,
                        tl.status,
                        tl.note
                    FROM ticket_log tl
                    JOIN users u ON tl.user_id = u.id
                    JOIN tickets t ON tl.ticket_id = t.id
                    LEFT JOIN projects p ON t.project_id = p.id
                    WHERE tl.user_id IN ({format_strings})
                      AND DATE(tl.start_time) >= %s 
                      AND DATE(tl.start_time) <= %s
                      AND tl.status != 1
                    ORDER BY tl.start_time DESC
                """
                params = user_ids + [date_from, date_to]
                cursor.execute(query, tuple(params))
                all_logs = cursor.fetchall()

                # Process logs & calculate duration
                def format_duration(start, end):
                    if not start:
                        return "0 hrs 0 mins", 0
                    actual_end = end if end else datetime.now()
                    
                    if start.tzinfo is not None:
                        start = start.astimezone(timezone.utc).replace(tzinfo=None)
                    if actual_end.tzinfo is not None:
                        actual_end = actual_end.astimezone(timezone.utc).replace(tzinfo=None)
                        
                    delta = actual_end - start
                    total_secs = int(delta.total_seconds())
                    if total_secs < 0:
                        total_secs = 0
                    
                    hours = total_secs // 3600
                    minutes = (total_secs % 3600) // 60
                    return f"{hours} hrs {minutes} mins", total_secs

                # Build dictionary for quick grouping
                users_dict = {}
                for u in target_users:
                    users_dict[u['id']] = {
                        "user_id": u['id'],
                        "user_name": f"{u['first_name']} {u['last_name']}",
                        "role_id": u['role_id'],
                        "tickets": []
                    }

                # Group logs by ticket
                user_tickets = {}
                for log in all_logs:
                    uid = log['user_id']
                    tid = log['ticket_id']
                    
                    dur_str, dur_secs = format_duration(log['start_time'], log['end_time'])
                    
                    key = (uid, tid)
                    if key not in user_tickets:
                        worked_minutes = int(worked_map.get(key, 0) or 0)
                        worked_hours = worked_minutes // 60
                        worked_mins = worked_minutes % 60
                        worked_time_str = f"{worked_hours} hrs {worked_mins} mins"
                        
                        notes_list = notes_map.get(key, [])
                        ticket_notes_str = "; ".join(notes_list) if notes_list else ""
                        
                        user_tickets[key] = {
                            "ticket_id": tid,
                            "ticket_no": log['ticket_no'],
                            "ticket_name": log['ticket_name'],
                            "project_name": log['project_name'] or "N/A",
                            "worked_time": worked_time_str,
                            "worked_seconds": worked_minutes * 60,
                            "total_actual_seconds": 0,
                            "notes": ticket_notes_str,
                            "logs": []
                        }
                    
                    user_tickets[key]["logs"].append({
                        "id": log['id'],
                        "start_time": log['start_time'].strftime("%Y-%m-%d %H:%M:%S") if log['start_time'] else None,
                        "end_time": log['end_time'].strftime("%Y-%m-%d %H:%M:%S") if log['end_time'] else None,
                        "status": log['status'],
                        "note": log['note'],
                        "actual_time": dur_str,
                        "actual_seconds": dur_secs
                    })
                    user_tickets[key]["total_actual_seconds"] += dur_secs

                # Populate tickets list for each user
                for key, ticket_data in user_tickets.items():
                    uid, tid = key
                    tot_secs = ticket_data["total_actual_seconds"]
                    tot_h = tot_secs // 3600
                    tot_m = (tot_secs % 3600) // 60
                    ticket_data["total_actual_time"] = f"{tot_h} hrs {tot_m} mins"
                    
                    if uid in users_dict:
                        users_dict[uid]["tickets"].append(ticket_data)

                # Return list format
                return {
                    "role_id": role_id,
                    "role_name": role_name,
                    "users": list(users_dict.values()),
                    "date_from": date_from,
                    "date_to": date_to
                }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()
