from fastapi import HTTPException, Header
from core.security import SECRET_KEY, ALGORITHM, get_current_user_id
from services.email_service import EmailService
from services.file_service import FileService
import jwt
import os
import shutil

settings_site_url = os.getenv("SITE_URL", "http://localhost:5173")

import logging
logger = logging.getLogger(__name__)


class TicketService:

    @staticmethod
    def get_ticket_internal(cursor, ticket_id):
        sql = """
            SELECT t.*, s.name as status_name, p.name as project_name
            FROM tickets t
            LEFT JOIN status s ON t.status_id = s.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.id = %s
        """
        cursor.execute(sql, (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            return None
            
        cursor.execute("SELECT assign_to, send_mail FROM assigned_tickets WHERE ticket_id=%s", (ticket_id,))
        assignees_rows = cursor.fetchall()
        
        cursor.execute("SELECT id, file_name, file_URL, created_by, created_date FROM tickets_attachments WHERE ticket_id=%s", (ticket_id,))
        attachments = cursor.fetchall()
        
        ticket_dict = dict(ticket)
        # Fetch parent ticket info if exists
        if ticket_dict.get('parent_ticket_id'):
            cursor.execute("SELECT ticket_no, title FROM tickets WHERE id = %s", (ticket_dict['parent_ticket_id'],))
            parent_res = cursor.fetchone()
            if parent_res:
                ticket_dict['parent_ticket_no'] = parent_res['ticket_no']
                ticket_dict['parent_ticket_title'] = parent_res['title']
            else:
                ticket_dict['parent_ticket_no'] = None
                ticket_dict['parent_ticket_title'] = None
        else:
            ticket_dict['parent_ticket_no'] = None
            ticket_dict['parent_ticket_title'] = None

        # Convert as_customer and for_customer from 1/0 to bool
        ticket_dict['as_customer'] = bool(ticket_dict.get('as_customer', False))
        ticket_dict['for_customer'] = bool(ticket_dict.get('for_customer', False))
        if len(assignees_rows) > 0:
            users = []
            for row in assignees_rows:
                assign = row['assign_to']
                send_mail_val = row['send_mail'] or 'Y'
                sql = "SELECT id, first_name, last_name FROM users WHERE id = %s"
                cursor.execute(sql, (int(assign),))
                assignee = cursor.fetchone()
                if assignee:
                    user = {
                        "id": int(assignee['id']),
                        "name": f"{assignee['first_name']} {assignee['last_name']}",
                        "send_mail": send_mail_val
                    }
                    users.append(user)
            ticket_dict['assignees'] = users
        else:
            ticket_dict['assignees'] = []
        ticket_dict['attachments'] = attachments
        
        if ticket_dict['created_by']:
            cursor.execute("SELECT first_name, last_name FROM users WHERE id = %s", (int(ticket_dict['created_by']),))
            created_by = cursor.fetchone()
            ticket_dict['created_by_name'] = f"{created_by['first_name']} {created_by['last_name']}"
        else:
            ticket_dict['created_by_name'] = "Unknown"

        return ticket_dict

    @staticmethod
    def get_filtered_tickets(filter_obj, db, current_user_id):
        """
        filter_obj: a dict or object with optional attributes:
            as_customer (bool), for_customer (bool),
            startDueDate (datetime/str), endDueDate (datetime/str), search (str)
        """
        with db.cursor() as cursor:
            # Check user role to see if they are admin
            cursor.execute("""
                SELECT u.role_id, r.name AS role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
            """, (current_user_id,))
            user_info = cursor.fetchone()
            role_name = user_info['role_name'] if user_info else ""
            is_admin = role_name.lower() in ("administrator", "admin")

            # Base query: only tickets the user can see (creator or assignee), except for admins who see all
            if is_admin:
                query = """
                    SELECT DISTINCT t.id
                    FROM tickets t
                    LEFT JOIN assigned_tickets at ON t.id = at.ticket_id
                    LEFT JOIN ticket_comments tc ON t.id = tc.ticket_id
                    WHERE 1=1
                """
                params = []
            else:
                query = """
                    SELECT DISTINCT t.id
                    FROM tickets t
                    LEFT JOIN assigned_tickets at ON t.id = at.ticket_id
                    LEFT JOIN ticket_comments tc ON t.id = tc.ticket_id
                    WHERE (t.created_by = %s OR at.assign_to = %s)
                """
                params = [current_user_id, current_user_id]

            if filter_obj:
                # Helper to extract values seamlessly from a dict OR an object
                def get_val(key):
                    if isinstance(filter_obj, dict):
                        return filter_obj.get(key)
                    return getattr(filter_obj, key, None)

                as_customer = get_val('as_customer')
                for_customer = get_val('for_customer')
                search = get_val('search')                                          
                ticket_type = get_val('type')                                       

                # Apply boolean filters
                if as_customer not in (None, False):
                    query += " AND t.as_customer = %s"
                    params.append(int(as_customer)) 

                if for_customer not in (None, False):
                    query += " AND t.for_customer = %s"
                    params.append(int(for_customer))

                if ticket_type not in (None, ''):
                    query += " AND t.type = %s"
                    params.append(ticket_type)

                # 1. Extract values from the filter object
                start_date = get_val('startDueDate')
                end_date = get_val('endDueDate')

                # 2. Extract the first element if they arrived wrapped in a tuple or list
                if isinstance(start_date, (tuple, list)): 
                    start_date = start_date[0] if start_date else None
                if isinstance(end_date, (tuple, list)): 
                    end_date = end_date[0] if end_date else None

                # 3. Clean up strings and eliminate empty/falsy wrappers completely
                if isinstance(start_date, str): start_date = start_date.strip()
                if isinstance(end_date, str): end_date = end_date.strip()

                # Force any remaining falsy values (like empty strings) to a hard None
                start_date = start_date if start_date else None
                end_date = end_date if end_date else None

                # 4. Run the chained date range check
                if start_date is not None:
                    query += " AND t.created_date >= %s"
                    params.append(start_date)
                if end_date is not None:
                    query += " AND t.due_date <= %s"
                    params.append(end_date)

                if search:
                    query += " AND (t.title LIKE %s OR t.description LIKE %s OR t.ticket_no LIKE %s OR tc.comment LIKE %s)"
                    search_param = f"%{search}%"
                    params.append(search_param)
                    params.append(search_param)
                    params.append(search_param)
                    params.append(search_param)

            query += " ORDER BY t.id DESC"
            cursor.execute(query, params)
            ticket_records = cursor.fetchall()

            results = []
            for record in ticket_records:
                # Safety check: handles both Dictionary cursors and standard Tuple cursors
                ticket_id = record['id'] if isinstance(record, dict) else record[0]
                results.append(TicketService.get_ticket_internal(cursor, ticket_id))

            return results
        
    @staticmethod
    def create_ticket(ticket, db, current_user_id):
        with db.cursor() as cursor:
            # Generate ticket_no
            words = ticket.project_name.split()
            if len(words) > 1:
                prefix = "".join([word[0] for word in words]).upper()
            else:
                prefix = ticket.project_name
            
            if ticket.owner_id:
                cursor.execute("SELECT id FROM users WHERE id = %s", (ticket.owner_id,))
                owner = cursor.fetchone()
                if not owner:
                    raise HTTPException(status_code=400, detail="Owner user not found")
                current_user_id = owner['id']

            cursor.execute("SELECT COUNT(*) as count FROM tickets WHERE project_id = %s", (ticket.project_id,))
            sn = (cursor.fetchone()['count'] or 0) + 1
            ticket_no = f"{prefix}-{sn:02d}"

            sql = """
                INSERT INTO tickets (parent_ticket_id, ticket_no, project_id, department_id, title, description, priority, due_date, working_hours, as_customer, for_customer, status_id, created_by,type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                ticket.parent_ticket_id, ticket_no, ticket.project_id, ticket.department_id, ticket.title, ticket.description, ticket.priority, ticket.due_date, ticket.working_hours,
                ticket.as_customer, ticket.for_customer, ticket.status_id, current_user_id,ticket.type
            ))
            db.commit()
            ticket_id = cursor.lastrowid
            
            # Collect unique recipients
            recipients = {}  # email -> first_name

            # Handle assignees
            if ticket.assignees:
                assignee_vals = [(ticket_id, assignee.id, current_user_id, assignee.send_mail) for assignee in ticket.assignees]
                cursor.executemany(
                    "INSERT INTO assigned_tickets (ticket_id, assign_to, created_by, send_mail) VALUES (%s, %s, %s, %s)",
                    assignee_vals
                )
                db.commit()
                send_mail_uids = [assignee.id for assignee in ticket.assignees if assignee.send_mail == 'Y']
            else:
                cursor.execute("SELECT id FROM users WHERE role_id = 1")
                assignees = cursor.fetchall()
                assignee_vals = [(ticket_id, uid['id'], current_user_id, 'Y') for uid in assignees]
                cursor.executemany(
                    "INSERT INTO assigned_tickets (ticket_id, assign_to, created_by, send_mail) VALUES (%s, %s, %s, %s)",
                    assignee_vals
                )
                db.commit()
                send_mail_uids = [uid['id'] for uid in assignees]

            # Collect unique recipients for assignees
            if send_mail_uids:
                format_strings = ','.join(['%s'] * len(send_mail_uids))
                cursor.execute(f"SELECT email, first_name FROM users WHERE id IN ({format_strings})", tuple(send_mail_uids))
                for u in cursor.fetchall():
                    recipients[u['email']] = u['first_name']

            # 2. Add Project Client
            cursor.execute("SELECT u.email, u.first_name FROM users u JOIN projects p ON u.id = p.client_id WHERE p.id = %s", (ticket.project_id,))
            client = cursor.fetchone()
            if client:
                recipients[client['email']] = client['first_name']

            # 3. Add all Administrators (role_id = 1)
            cursor.execute("SELECT email, first_name FROM users WHERE role_id = 1")
            for admin in cursor.fetchall():
                recipients[admin['email']] = admin['first_name']

            # Send emails to all unique recipients
            if recipients:
                formatted_date = f"{ticket.due_date.strftime('%b')} {ticket.due_date.day}, {ticket.due_date.year}" if ticket.due_date else 'N/A'
                subject = f"New Ticket: {ticket.title}"
                
                for email, first_name in recipients.items():
                    context = {
                        "subject": subject,
                        "message": (
                            f"Hello {first_name},<br><br>"
                            f"A new ticket <b>{ticket.title}</b> has been assigned to you.<br><br>"
                            f"<b>Ticket No:</b> {ticket_no}<br>"
                            f"<b>Project:</b> {ticket.project_name}<br>"
                            f"<b>Due Date:</b> {formatted_date}<br><br>"
                            f'<a href="{settings_site_url}/dashboard/manage-tickets/view/{ticket_id}" style="display: inline-block; padding: 10px 20px; font-family: sans-serif; font-size: 14px; color: #ffffff; background-color: #0052cc; text-decoration: none; border-radius: 5px; font-weight: bold;">View Ticket</a>'
                        ),
                    }
                    EmailService.send_email(email, subject, "email_template.html", context)
                
            return TicketService.get_ticket_internal(cursor, ticket_id)

    @staticmethod
    def get_all_tickets(db, current_user_id):        
        with db.cursor() as cursor:
            # We use DISTINCT to avoid duplicates if a user assigned a ticket to themselves
            query = """
                SELECT DISTINCT t.id 
                FROM tickets t
                LEFT JOIN assigned_tickets at ON t.id = at.ticket_id
                WHERE t.created_by = %s OR at.assign_to = %s
                ORDER BY t.id DESC
            """
            cursor.execute(query, (current_user_id, current_user_id))
            ticket_records = cursor.fetchall()
            
            results = []
            for record in ticket_records:
                # Reusing your internal helper to fetch full ticket details
                results.append(TicketService.get_ticket_internal(cursor, record['id']))
                
            return results

    @staticmethod
    def get_ticket(ticket_id: int, db):
        with db.cursor() as cursor:
            ticket = TicketService.get_ticket_internal(cursor, ticket_id)
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
            return ticket

    @staticmethod
    def update_ticket(ticket_id: int, ticket_update, db, current_user_id):
        with db.cursor() as cursor:
            # Get user full name for email notification
            cursor.execute("SELECT first_name, last_name FROM users WHERE id=%s", (current_user_id,))
            user = cursor.fetchone()
            user_full_name = f"{user['first_name']} {user['last_name']}"

            cursor.execute("""
                SELECT t.*, s.name as status_name 
                FROM tickets t
                LEFT JOIN status s ON t.status_id = s.id
                WHERE t.id=%s
            """, (ticket_id,))
            old_ticket = cursor.fetchone()
            if not old_ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
                
            cursor.execute("SELECT assign_to FROM assigned_tickets WHERE ticket_id=%s", (ticket_id,))
            old_assignees = set([r['assign_to'] for r in cursor.fetchall()])
            new_assignees = set([assignee.id for assignee in ticket_update.assignees])

            if ticket_update.owner_id:
                cursor.execute("SELECT id FROM users WHERE id = %s", (ticket_update.owner_id,))
                owner = cursor.fetchone()
                if not owner:
                    raise HTTPException(status_code=400, detail="Owner user not found")
                current_user_id = owner['id']
                                
            sql = """
                UPDATE tickets
                SET parent_ticket_id=%s, project_id=%s,department_id=%s, title=%s, description=%s, priority=%s, due_date=%s, working_hours=%s, as_customer=%s, for_customer=%s, status_id=%s,type=%s
                WHERE id=%s
            """
            cursor.execute(sql, (
                ticket_update.parent_ticket_id, ticket_update.project_id, ticket_update.department_id, ticket_update.title, ticket_update.description, ticket_update.priority, ticket_update.due_date, ticket_update.working_hours,
                ticket_update.as_customer, ticket_update.for_customer, ticket_update.status_id,ticket_update.type, ticket_id
            ))
            
            # Update assignees: easiest is delete and recreate
            cursor.execute("DELETE FROM assigned_tickets WHERE ticket_id=%s", (ticket_id,))
            
            if ticket_update.assignees:
                assignee_vals = [(ticket_id, assignee.id, current_user_id, assignee.send_mail) for assignee in ticket_update.assignees]
                cursor.executemany(
                    "INSERT INTO assigned_tickets (ticket_id, assign_to, created_by, send_mail) VALUES (%s, %s, %s, %s)",
                    assignee_vals
                )
                
            db.commit()

            # Email notifications logic
            try:
                due_date_str_old = str(old_ticket['due_date'])[:16] if old_ticket['due_date'] else None
                due_date_str_new = str(ticket_update.due_date)[:16] if ticket_update.due_date else None
                due_date_changed = (due_date_str_old != due_date_str_new)
            except Exception:
                due_date_changed = False
                
            status_changed = (old_ticket['status_id'] != ticket_update.status_id)
            new_status_name = ""
            if status_changed and ticket_update.status_id:
                cursor.execute("SELECT name FROM status WHERE id=%s", (ticket_update.status_id,))
                st_res = cursor.fetchone()
                if st_res:
                    new_status_name = st_res['name']
            
            send_mail_prefs = {assignee.id: assignee.send_mail for assignee in ticket_update.assignees}
            new_assigned_users = list(new_assignees - old_assignees)
            new_assigned_users_emails = []
            
            new_assigned_users_to_notify = [uid for uid in new_assigned_users if send_mail_prefs.get(uid, 'Y') == 'Y']
            
            if new_assigned_users_to_notify:
                format_strings = ','.join(['%s'] * len(new_assigned_users_to_notify))
                cursor.execute(f"SELECT email, first_name FROM users WHERE id IN ({format_strings})", tuple(new_assigned_users_to_notify))
                users_to_email = cursor.fetchall()
                
                # Fetch project name
                cursor.execute("SELECT name FROM projects WHERE id = %s", (ticket_update.project_id,))
                proj_row = cursor.fetchone()
                project_name = proj_row['name'] if proj_row else "N/A"
                
                ticket_no = old_ticket['ticket_no']
                formatted_date = f"{ticket_update.due_date.strftime('%b')} {ticket_update.due_date.day}, {ticket_update.due_date.year}" if ticket_update.due_date else 'N/A'
                subject = f"New Ticket: {ticket_update.title}"
                
                for u in users_to_email:
                    new_assigned_users_emails.append(u['email'])
                    context = {
                        "subject": subject,
                        "message": (
                            f"Hello {u['first_name']},<br><br>"
                            f"A new ticket <b>{ticket_update.title}</b> has been assigned to you by {user_full_name}.<br><br>"
                            f"<b>Ticket No:</b> {ticket_no}<br>"
                            f"<b>Project:</b> {project_name}<br>"
                            f"<b>Due Date:</b> {formatted_date}<br><br>"
                            f'<a href="{settings_site_url}/dashboard/manage-tickets/view/{ticket_id}" style="display: inline-block; padding: 10px 20px; font-family: sans-serif; font-size: 14px; color: #ffffff; background-color: #0052cc; text-decoration: none; border-radius: 5px; font-weight: bold;">View Ticket</a>'
                        ),
                    }
                    EmailService.send_email(u['email'], subject, "email_template.html", context)
                    
            if (due_date_changed or status_changed) and ticket_update.assignees:
                uids_to_notify = [assignee.id for assignee in ticket_update.assignees if assignee.send_mail == 'Y']
                if uids_to_notify:
                    format_strings = ','.join(['%s'] * len(uids_to_notify))
                    cursor.execute(f"SELECT email, first_name FROM users WHERE id IN ({format_strings})", tuple(uids_to_notify))
                    all_users_to_email = cursor.fetchall()
                    
                    for u in all_users_to_email:
                        if u['email'] in new_assigned_users_emails:
                            continue
                            
                        messages_parts = []
                        if due_date_changed:
                            old_date_formatted = f"None"
                            if old_ticket['due_date']:
                                if hasattr(old_ticket['due_date'], 'strftime'):
                                    old_date_formatted = f"{old_ticket['due_date'].strftime('%b')} {old_ticket['due_date'].day}, {old_ticket['due_date'].year}"
                                else:
                                    old_date_formatted = str(old_ticket['due_date'])
                                    
                            new_date_formatted = f"{ticket_update.due_date.strftime('%b')} {ticket_update.due_date.day}, {ticket_update.due_date.year}" if ticket_update.due_date else 'None'
                            messages_parts.append(f"<b>Due Date:</b> <span style='text-decoration: line-through; color: red;'>{old_date_formatted}</span> <span style='color: green;'>{new_date_formatted}</span>")
                        if status_changed:
                            old_status = old_ticket['status_name'] if old_ticket['status_name'] else 'Unassigned'
                            new_status = new_status_name if new_status_name else 'Unassigned'
                            messages_parts.append(f"<b>Status:</b> <span style='text-decoration: line-through; color: red;'>{old_status}</span> <span style='color: green;'>{new_status}</span>")
                        
                        subject = f"Ticket Update: {ticket_update.title}"
                        context = {
                            "subject": subject,
                            "message": f"Hello {u['first_name']},<br><br>The following updates have been made to ticket <b>{ticket_update.title}</b> by {user_full_name}.<br><br>" + "<br><br>".join(messages_parts) + f'<br><br><a href="{settings_site_url}/dashboard/manage-tickets/view/{ticket_id}" style="display: inline-block; padding: 10px 20px; font-family: sans-serif; font-size: 14px; color: #ffffff; background-color: #0052cc; text-decoration: none; border-radius: 5px; font-weight: bold;">View Ticket</a>',
                        }
                        EmailService.send_email(u['email'], subject, "email_template.html", context)

            return TicketService.get_ticket_internal(cursor, ticket_id)

    @staticmethod
    def update_ticket_status(ticket_id: int, status_update, db, current_user_id):
        with db.cursor() as cursor:
            
            # Get user full name for email notification
            cursor.execute("SELECT first_name, last_name FROM users WHERE id=%s", (current_user_id,))
            user = cursor.fetchone()
            user_full_name = f"{user['first_name']} {user['last_name']}"

            # Check if ticket exists
            cursor.execute("SELECT title, status_id FROM tickets WHERE id=%s", (ticket_id,))
            ticket = cursor.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
            
            old_status_id = ticket['status_id']
            new_status_id = status_update.status_id
            
            # Update status
            cursor.execute("UPDATE tickets SET status_id=%s WHERE id=%s", (new_status_id, ticket_id))
            db.commit()

            # Handle notifications if status changed
            if old_status_id != new_status_id:
                # Get status names
                cursor.execute("SELECT name FROM status WHERE id=%s", (old_status_id,))
                old_status_res = cursor.fetchone()
                old_status_name = old_status_res['name'] if old_status_res else "Unassigned"

                cursor.execute("SELECT name FROM status WHERE id=%s", (new_status_id,))
                new_status_res = cursor.fetchone()
                new_status_name = new_status_res['name'] if new_status_res else "Unassigned"

                # Get assignees to notify
                cursor.execute("SELECT assign_to FROM assigned_tickets WHERE ticket_id=%s", (ticket_id,))
                assignees = [r['assign_to'] for r in cursor.fetchall()]

                if assignees:
                    format_strings = ','.join(['%s'] * len(assignees))
                    cursor.execute(f"SELECT email, first_name FROM users WHERE id IN ({format_strings})", tuple(assignees))
                    users_to_email = cursor.fetchall()

                    for u in users_to_email:
                        subject = f"Ticket Status Updated: {ticket['title']}"
                        context = {
                            "subject": subject,
                            "message": (
                                f"Hello {u['first_name']},<br><br>"
                                f"The status of ticket <b>{ticket['title']}</b> has been updated by {user_full_name}.</b><br><br>"
                                f"<b>Status:</b> <span style='text-decoration: line-through; color: red;'>{old_status_name}</span> "
                                f"<span style='color: green;'>{new_status_name}</span><br><br>"
                                f'<a href="{settings_site_url}/dashboard/manage-tickets/view/{ticket_id}" style="display: inline-block; padding: 10px 20px; font-family: sans-serif; font-size: 14px; color: #ffffff; background-color: #0052cc; text-decoration: none; border-radius: 5px; font-weight: bold;">View Ticket</a>'
                            ),
                        }
                        EmailService.send_email(u['email'], subject, "email_template.html", context)

            return TicketService.get_ticket_internal(cursor, ticket_id)

    @staticmethod
    def update_ticket_title(ticket_id: int, title_update, db, current_user_id):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM tickets WHERE id=%s", (ticket_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ticket not found")
            
            cursor.execute("UPDATE tickets SET title=%s WHERE id=%s", (title_update.title, ticket_id))
            db.commit()
            return TicketService.get_ticket_internal(cursor, ticket_id)

    @staticmethod
    def delete_ticket(ticket_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM tickets WHERE id=%s", (ticket_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ticket not found")
                
            cursor.execute("SELECT file_URL FROM tickets_attachments WHERE ticket_id=%s", (ticket_id,))
            attachments = cursor.fetchall()
            
            # Use base dir relative from where tickets_attachments used to be
            ticket_dirs_to_remove = set()
            
            for att in attachments:
                file_url = att['file_URL']
                if file_url:
                    clean_url = file_url.lstrip('/')
                    file_path = FileService.get_upload_path(clean_url)
                    
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            att_dir = os.path.dirname(file_path)
                            if not os.listdir(att_dir):
                                shutil.rmtree(att_dir)
                            
                            attachments_dir = os.path.dirname(att_dir)
                            if os.path.basename(attachments_dir) == 'attachments':
                                ticket_dir = os.path.dirname(attachments_dir)
                                ticket_dirs_to_remove.add(ticket_dir)
                        except Exception as e:
                            logger.info(f"Error deleting file {file_path}: {e}")
            
            # Cleanup parent directories if they are now empty
            for t_dir in ticket_dirs_to_remove:
                if os.path.exists(t_dir):
                    att_dir = os.path.join(t_dir, 'attachments')
                    if os.path.exists(att_dir) and not os.listdir(att_dir):
                        try:
                            shutil.rmtree(att_dir)
                        except: pass
                    if os.path.exists(t_dir) and not os.listdir(t_dir):
                        try:
                            shutil.rmtree(t_dir)
                        except: pass

            # Delete database records
            cursor.execute("DELETE FROM tickets_attachments WHERE ticket_id=%s", (ticket_id,))
            cursor.execute("DELETE FROM assigned_tickets WHERE ticket_id=%s", (ticket_id,))
            cursor.execute("DELETE FROM tickets WHERE id=%s", (ticket_id,))
            db.commit()
            return True

    @staticmethod
    def update_assignee_send_mail(ticket_id: int, user_id: int, send_mail: str, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM tickets WHERE id=%s", (ticket_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ticket not found")
            
            cursor.execute("SELECT id FROM assigned_tickets WHERE ticket_id=%s AND assign_to=%s", (ticket_id, user_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Assignee not found for this ticket")
                
            cursor.execute("UPDATE assigned_tickets SET send_mail=%s WHERE ticket_id=%s AND assign_to=%s", (send_mail, ticket_id, user_id))
            db.commit()
            
            return TicketService.get_ticket_internal(cursor, ticket_id)

    @staticmethod
    def get_tickets_by_project(project_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM tickets WHERE project_id = %s ORDER BY id DESC", (project_id,))
            records = cursor.fetchall()
            results = []
            for record in records:
                ticket_details = TicketService.get_ticket_internal(cursor, record['id'])
                if ticket_details:
                    ticket_details['parent_ticket_no'] = None
                    ticket_details['parent_ticket_title'] = None
                    results.append(ticket_details)
            return results

    @staticmethod
    def close_or_reopen_ticket(ticket_id: int, status_id, db, current_user_id):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM tickets WHERE id=%s", (ticket_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Ticket not found")
            
            target_status_id = status_id
            if target_status_id is None:
                cursor.execute("SELECT id FROM status WHERE name = 'Close' LIMIT 1")
                status_row = cursor.fetchone()
                if not status_row:
                    cursor.execute("SELECT id FROM status WHERE LOWER(name) = 'close' LIMIT 1")
                    status_row = cursor.fetchone()
                if not status_row:
                    raise HTTPException(status_code=400, detail="Status 'Close' not found in database")
                target_status_id = status_row['id']
                
            cursor.execute("UPDATE tickets SET status_id=%s WHERE id=%s", (target_status_id, ticket_id))
            db.commit()
            
            return TicketService.get_ticket_internal(cursor, ticket_id)