from fastapi import HTTPException
import logging
from datetime import timezone

logger = logging.getLogger(__name__)

def make_utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc)

class DashboardService:
    @staticmethod
    def get_dashboard_data(current_user_id: int, db):
        if not current_user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        with db.cursor() as cursor:
            # 1. Get all assigned tickets for current user, joined with metadata
            query = """
                SELECT t.id, t.ticket_no, t.title, t.due_date, t.created_date, t.created_by,
                       p.name AS project_name, d.name AS department_name, s.name AS status_name,
                       CONCAT(u.first_name, ' ', u.last_name) AS created_by_name
                FROM assigned_tickets at
                JOIN tickets t ON at.ticket_id = t.id
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN departments d ON t.department_id = d.id
                LEFT JOIN status s ON t.status_id = s.id
                LEFT JOIN users u ON t.created_by = u.id
                WHERE at.assign_to = %s
            """
            cursor.execute(query, (current_user_id,))
            assigned_tickets = cursor.fetchall()

            unanswered_tickets = []
            for ticket in assigned_tickets:
                # 3. Find the last comment for the ticket
                comment_query = """
                    SELECT created_by, created_date_time
                    FROM ticket_comments
                    WHERE ticket_id = %s
                    ORDER BY created_date_time DESC, id DESC
                    LIMIT 1
                """
                cursor.execute(comment_query, (ticket['id'],))
                last_comment = cursor.fetchone()

                # If no comments, or the last comment creator was not the current user
                if not last_comment or last_comment['created_by'] != current_user_id:
                    unanswered_tickets.append({
                        "id": ticket['id'],
                        "ticket_no": ticket['ticket_no'],
                        "project_name": ticket['project_name'] or "N/A",
                        "department_name": ticket['department_name'] or "N/A",
                        "title": ticket['title'],
                        "status_name": ticket['status_name'] or "N/A",
                        "created_by_name": ticket['created_by_name'] or "Unknown",
                        "last_post_date": make_utc(last_comment['created_date_time']) if last_comment else None,
                        "due_date": ticket['due_date']
                    })

            # Sort unanswered tickets by ID desc (most recent first)
            unanswered_tickets.sort(key=lambda x: x['id'], reverse=True)

            # --- Role-Based Active Work Timers Section ---
            # Get current user's role
            cursor.execute("""
                SELECT u.role_id, r.name AS role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
            """, (current_user_id,))
            user_info = cursor.fetchone()
            role_name = user_info['role_name'] if user_info else ""
            
            active_timers = []
            role_lower = role_name.lower() if role_name else ""
            
            from datetime import datetime
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if role_lower in ("administrator", "admin"):
                timer_query = """
                    SELECT 
                        tl.id AS log_id,
                        tl.ticket_id,
                        tl.user_id,
                        tl.start_time,
                        tl.status,
                        t.title AS ticket_name,
                        t.ticket_no,
                        p.name AS project_name,
                        CONCAT(u.first_name, ' ', u.last_name) AS user_name
                    FROM ticket_log tl
                    JOIN tickets t ON tl.ticket_id = t.id
                    LEFT JOIN projects p ON t.project_id = p.id
                    JOIN users u ON tl.user_id = u.id
                    WHERE tl.status = 1
                """
                cursor.execute(timer_query)
            elif role_lower == "manager":
                timer_query = """
                    SELECT 
                        tl.id AS log_id,
                        tl.ticket_id,
                        tl.user_id,
                        tl.start_time,
                        tl.status,
                        t.title AS ticket_name,
                        t.ticket_no,
                        p.name AS project_name,
                        CONCAT(u.first_name, ' ', u.last_name) AS user_name
                    FROM ticket_log tl
                    JOIN tickets t ON tl.ticket_id = t.id
                    LEFT JOIN projects p ON t.project_id = p.id
                    JOIN users u ON tl.user_id = u.id
                    WHERE tl.status = 1 AND (u.report_to = %s OR u.id = %s)
                """
                cursor.execute(timer_query, (current_user_id, current_user_id))
            else:
                # Any other role (including Developer) shows their own timers
                timer_query = """
                    SELECT 
                        tl.id AS log_id,
                        tl.ticket_id,
                        tl.user_id,
                        tl.start_time,
                        tl.status,
                        t.title AS ticket_name,
                        t.ticket_no,
                        p.name AS project_name,
                        CONCAT(u.first_name, ' ', u.last_name) AS user_name
                    FROM ticket_log tl
                    JOIN tickets t ON tl.ticket_id = t.id
                    LEFT JOIN projects p ON t.project_id = p.id
                    JOIN users u ON tl.user_id = u.id
                    JOIN assigned_tickets at ON t.id = at.ticket_id AND at.assign_to = tl.user_id
                    WHERE tl.status = 1 AND tl.user_id = %s
                """
                cursor.execute(timer_query, (current_user_id,))
            
            raw_timers = cursor.fetchall()
            
            for item in raw_timers:
                # Query all logs for this user + ticket to sum duration
                cursor.execute("""
                    SELECT start_time, end_time, status 
                    FROM ticket_log 
                    WHERE user_id = %s AND ticket_id = %s
                """, (item['user_id'], item['ticket_id']))
                logs = cursor.fetchall()
                
                total_seconds = 0.0
                accumulated_seconds = 0.0
                
                for log in logs:
                    start = log['start_time']
                    end = log['end_time']
                    
                    if log['status'] == 1:
                        if start:
                            duration_sec = (now - start).total_seconds()
                            total_seconds += duration_sec
                    else:
                        if start and end:
                            duration_sec = (end - start).total_seconds()
                            total_seconds += duration_sec
                            accumulated_seconds += duration_sec
                            
                tot_h = int(total_seconds // 3600)
                tot_m = int((total_seconds % 3600) // 60)
                tot_s = int(total_seconds % 60)
                total_hours_formatted = f"{tot_h:02d}:{tot_m:02d}:{tot_s:02d}"
                
                active_timers.append({
                    "log_id": item['log_id'],
                    "ticket_id": item['ticket_id'],
                    "ticket_no": item['ticket_no'],
                    "ticket_name": item['ticket_name'],
                    "project_name": item['project_name'] or "N/A",
                    "user_id": item['user_id'],
                    "user_name": item['user_name'],
                    "start_time": make_utc(item['start_time']),
                    "status": item['status'],
                    "total_seconds": total_seconds,
                    "accumulated_seconds": accumulated_seconds,
                    "total_hours_formatted": total_hours_formatted
                })

            # Query developers who are currently not working (status=0 and no status=1 logs)
            idle_developers = []
            if role_lower in ("administrator", "admin", "manager"):
                if role_lower in ("administrator", "admin"):
                    idle_query = """
                        SELECT 
                            u.id AS user_id,
                            CONCAT(u.first_name, ' ', u.last_name) AS user_name                           
                        FROM users u
                        WHERE u.is_working = 0
                        AND u.role_id != 3
                        AND u.id != %s
                    """
                    cursor.execute(idle_query, (current_user_id,))
                elif role_lower == "manager":
                    idle_query = """
                        SELECT 
                            u.id AS user_id,
                            CONCAT(u.first_name, ' ', u.last_name) AS user_name                    
                        FROM users u
                        WHERE u.is_working = 0 AND u.report_to = %s AND u.role_id != 3 AND u.id != %s
                    """
                    cursor.execute(idle_query, (current_user_id, current_user_id))
                
                raw_idle = cursor.fetchall()
                for item in raw_idle:
                    idle_developers.append({
                        "user_id": item['user_id'],
                        "user_name": item['user_name'],
                    })

            # Watchlist Kanban Board Section (Admin / Manager only)
            watchlist = []
            if role_lower in ("administrator", "admin", "manager"):
                # 1) Get all watchlist projects for current user
                cursor.execute("""
                    SELECT p.id AS project_id, p.name AS project_name
                    FROM user_watchlist uw
                    JOIN projects p ON uw.project_id = p.id
                    WHERE uw.user_id = %s
                    ORDER BY uw.id DESC
                """, (current_user_id,))
                watched_projects = cursor.fetchall()
                
                for proj in watched_projects:
                    # 2) For each project, get all tickets
                    cursor.execute("""
                        SELECT t.id AS ticket_id, t.title AS ticket_name, t.ticket_no, t.type, s.name AS status
                        FROM tickets t
                        LEFT JOIN status s ON t.status_id = s.id
                        WHERE t.project_id = %s
                    """, (proj['project_id'],))
                    proj_tickets = cursor.fetchall()
                    
                    filtered_tickets = []
                    for ticket in proj_tickets:
                        # 3) Get users currently working on the ticket (status = 1 in ticket_log)
                        cursor.execute("""
                            SELECT tl.user_id, CONCAT(u.first_name, ' ', u.last_name) AS user_name
                            FROM ticket_log tl
                            JOIN users u ON tl.user_id = u.id
                            WHERE tl.ticket_id = %s AND tl.status = 1
                        """, (ticket['ticket_id'],))
                        working_users = cursor.fetchall()
                        
                        ticket_users = [{"user_id": u['user_id'], "user_name": u['user_name']} for u in working_users]
                        
                        has_active_users = len(ticket_users) > 0
                        is_in_progress = ticket['status'] is not None and ticket['status'].lower() == 'in progress'
                        
                        # Only show tickets that are currently being worked on OR are "In Progress"
                        if has_active_users or is_in_progress:
                            # Sorting helper: active working tickets first (score 0), then In Progress (score 1)
                            filtered_tickets.append({
                                "ticket_id": ticket['ticket_id'],
                                "ticket_name": ticket['ticket_name'],
                                "ticket_no": ticket['ticket_no'],
                                "type": ticket['type'] or "",
                                "status": ticket['status'] or "",
                                "users": ticket_users,
                                "priority_score": 0 if has_active_users else 1
                            })
                    
                    # Sort so that tickets with active users come first
                    filtered_tickets.sort(key=lambda x: x['priority_score'])
                    for t in filtered_tickets:
                        t.pop('priority_score', None)
                        
                    watchlist.append({
                        "project_id": proj['project_id'],
                        "project_name": proj['project_name'],
                        "tickets": filtered_tickets
                    })

        from datetime import datetime
        return {           
            "unanswered_tickets": unanswered_tickets,
            "active_timers": active_timers,
            "idle_developers": idle_developers,
            "watchlist": watchlist,
            "server_time": datetime.now(timezone.utc)
        }

