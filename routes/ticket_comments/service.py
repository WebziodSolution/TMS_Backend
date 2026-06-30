from fastapi import HTTPException
from services.email_service import EmailService
from services.file_service import FileService
import os
import shutil

class TicketCommentService:

    @staticmethod
    def get_user_hierarchy_info(cursor, user_id):
        """Returns a list of manager IDs up the chain for a user."""
        managers = []
        current_id = user_id
        while True:
            cursor.execute("SELECT report_to FROM users WHERE id = %s", (current_id,))
            res = cursor.fetchone()
            if res and res['report_to']:
                managers.append(res['report_to'])
                current_id = res['report_to']
            else:
                break
        return managers

    @staticmethod
    def is_user_a_manager(cursor, user_id):
        """Returns True if any user reports to this user."""
        cursor.execute("SELECT id FROM users WHERE report_to = %s LIMIT 1", (user_id,))
        return cursor.fetchone() is not None

    @staticmethod
    def get_comment_internal(cursor, comment_id):
        sql = """
            SELECT c.*, t.name as comment_type_name, 
                   CONCAT(u.first_name, ' ', u.last_name) as created_by_name
            FROM ticket_comments c
            LEFT JOIN ticket_comments_type t ON c.comment_type_id = t.id
            LEFT JOIN users u ON c.created_by = u.id
            WHERE c.id = %s
        """
        cursor.execute(sql, (comment_id,))
        comment = cursor.fetchone()
        if not comment:
            return None
        
        # Fetch attachments
        cursor.execute("SELECT * FROM ticket_comments_attachments WHERE ticket_comment_id = %s", (comment_id,))
        comment['attachments'] = cursor.fetchall()
        return comment

    @staticmethod
    def get_comments_by_ticket(ticket_id, db, current_user_id):
        with db.cursor() as cursor:
            # 1. Fetch current user role and info
            cursor.execute("SELECT role_id FROM users WHERE id = %s", (current_user_id,))
            user_info = cursor.fetchone()
            user_role_id = user_info['role_id'] if user_info else None
            is_admin = (user_role_id == 1)
            
            # Identify if user is a manager in the system (has subordinates)
            user_is_manager = TicketCommentService.is_user_a_manager(cursor, current_user_id)
            
            # Get users who report to this user (direct or indirect? Let's stick to assigned context later)
            
            # 2. Get all comments for ticket
            cursor.execute("SELECT id FROM ticket_comments WHERE ticket_id = %s ORDER BY created_date_time ASC", (ticket_id,))
            comment_ids = [r['id'] for r in cursor.fetchall()]
            
            # 3. Get assignees roles for this ticket to help with visibility logic
            cursor.execute("SELECT assign_to, role_id FROM assigned_tickets at JOIN users u ON at.assign_to = u.id WHERE at.ticket_id = %s", (ticket_id,))
            assigned_users = cursor.fetchall()
            assigned_roles_map = {au['assign_to']: au['role_id'] for au in assigned_users}
            
            # Check if user is assigned
            is_assigned = current_user_id in assigned_roles_map or is_admin
            
            results = []
            all_comments_by_id = {}
            
            for cid in comment_ids:
                comment = TicketCommentService.get_comment_internal(cursor, cid)
                if not comment: continue
                
                type_id = comment['comment_type_id']
                creator_id = comment['created_by']
                
                visible = False
                
                if is_admin or creator_id == current_user_id:
                    visible = True
                elif type_id == 1: # Open
                    visible = True
                elif type_id == 2: # Private for Developer
                    # Visible to assigned Developers + their managers
                    if assigned_roles_map.get(current_user_id) == 2:
                        visible = True
                    else:
                        # Check if any assigned developer reports to this user (directly or indirectly)
                        assigned_devs = [uid for uid, rid in assigned_roles_map.items() if rid == 2]
                        for dev_id in assigned_devs:
                            managers = TicketCommentService.get_user_hierarchy_info(cursor, dev_id)
                            if current_user_id in managers:
                                visible = True
                                break
                elif type_id == 3: # Private for Customer
                    if assigned_roles_map.get(current_user_id) == 3:
                        visible = True
                elif type_id == 4: # Private for manager
                    if assigned_roles_map.get(current_user_id) == 5:
                        visible = True
                    elif user_is_manager and current_user_id in assigned_roles_map:
                        # User is a manager in hierarchy and is assigned to ticket
                        visible = True
                elif type_id == 5: # Admin only
                    if is_admin:
                        visible = True
                elif type_id == 6: # Private for Developer , Manager and Admins
                    if assigned_roles_map.get(current_user_id) == 2 or assigned_roles_map.get(current_user_id) == 5 or is_admin:
                        visible = True
                
                if visible:
                    comment['replies'] = []
                    all_comments_by_id[comment['id']] = comment
                    if comment['parent_comment_id'] and comment['parent_comment_id'] in all_comments_by_id:
                        all_comments_by_id[comment['parent_comment_id']]['replies'].append(comment)
                    else:
                        results.append(comment)
            
            return results

    @staticmethod
    def create_comment(comment_data, db, current_user_id):
        with db.cursor() as cursor:
            sql = """
                INSERT INTO ticket_comments (ticket_id, comment, parent_comment_id, comment_type_id, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                comment_data.ticket_id, comment_data.comment, comment_data.parent_comment_id, 
                comment_data.comment_type_id, current_user_id
            ))
            db.commit()
            comment_id = cursor.lastrowid
            
            # Fetch the newly created comment
            comment = TicketCommentService.get_comment_internal(cursor, comment_id)
            
            # Send Notifications
            TicketCommentService.notify_users(cursor, comment, comment_data.comment_type_id, db)
            
            return comment

    @staticmethod
    def notify_users(cursor, comment, type_id, db):
        ticket_id = comment['ticket_id']
        # Get ticket title
        cursor.execute("SELECT title, ticket_no,project_id FROM tickets WHERE id = %s", (ticket_id,))
        ticket_res = cursor.fetchone()
        ticket_title = ticket_res['title'] if ticket_res else "Ticket"
        ticket_no = ticket_res['ticket_no']
        project_id = ticket_res['project_id'] if ticket_res else None
        
        client_user = None
        if project_id:
            cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            project_res = cursor.fetchone()
            if project_res:
                user_id = project_res['client_id']
                if user_id:
                    cursor.execute("SELECT id, role_id, email, first_name FROM users WHERE id = %s", (user_id,))
                    client_user = cursor.fetchone()

        # Get all assigned users
        cursor.execute("SELECT assign_to, role_id, email, first_name FROM assigned_tickets at JOIN users u ON at.assign_to = u.id WHERE at.ticket_id = %s AND (at.send_mail = 'Y' OR at.send_mail IS NULL)", (ticket_id,))
        assigned_users = cursor.fetchall()
        
        # Determine notification recipients
        recipients = []
        
        if type_id == 1: # Open
            recipients.extend(assigned_users)
            if client_user:
                recipients.append(client_user)
        elif type_id == 2: # Private for Developer
            devs = [u for u in assigned_users if u['role_id'] == 2]
            recipients.extend(devs)
            # Add their managers
            for dev in devs:
                manager_ids = TicketCommentService.get_user_hierarchy_info(cursor, dev['assign_to'])
                if manager_ids:
                    format_strings = ','.join(['%s'] * len(manager_ids))
                    cursor.execute(f"SELECT id as assign_to, role_id, email, first_name FROM users WHERE id IN ({format_strings})", tuple(manager_ids))
                    recipients.extend(cursor.fetchall())
        elif type_id == 3: # Private for Customer
            recipients.extend([u for u in assigned_users if u['role_id'] == 3])
            if client_user:
                recipients.append(client_user)
        elif type_id == 4: # Private for manager
            # Users with 'Manager' role assigned to ticket
            managers_by_role = [u for u in assigned_users if u['role_id'] == 5]
            recipients.extend(managers_by_role)
            # Assigned users who have subordinates
            for u in assigned_users:
                if TicketCommentService.is_user_a_manager(cursor, u['assign_to']):
                    recipients.append(u)
        elif type_id == 5: # Admin only
            # Notify all administrators? Usually yes, but let's stick to assigned ones if they exist, or all if broad.
            # Usually Admin only means all admins see it.
            admin_by_role = [u for u in assigned_users if u['role_id'] == 1]
            recipients.extend(admin_by_role)
        elif type_id == 6: # Private for Developer , Manager and Admins
            devs = [u for u in assigned_users if u['role_id'] == 2]
            recipients.extend(devs)
            managers_by_role = [u for u in assigned_users if u['role_id'] == 5]
            recipients.extend(managers_by_role)
            admin_by_role = [u for u in assigned_users if u['role_id'] == 1]
            recipients.extend(admin_by_role)
            
            # Assigned users who have subordinates
            for u in assigned_users:
                if TicketCommentService.is_user_a_manager(cursor, u['assign_to']):
                    recipients.append(u)
        
        # Unique recipients by email
        seen_emails = set()
        unique_recipients = []
        for r in recipients:
            if r['email'] not in seen_emails:
                seen_emails.add(r['email'])
                unique_recipients.append(r)
        
        # Send emails
        for r in unique_recipients:
            subject = f"New Comment on Ticket({ticket_no}): {ticket_title}"
            created_by = comment.get('created_by_name') or "Unknown User"
            message = f"Hello {r['first_name']}<br><br>A new comment has been added to ticket <b>{ticket_title}</b> by <b>{created_by}</b><br><br><i>{comment['comment']}</i>"
            context = {"subject": subject, "message": message}
            EmailService.send_email(r['email'], subject, "email_template.html", context)

    @staticmethod
    def update_comment(id, comment_update, db, current_user_id):
        with db.cursor() as cursor:
            cursor.execute("SELECT created_by FROM ticket_comments WHERE id = %s", (id,))
            comment = cursor.fetchone()
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            if comment['created_by'] != current_user_id:
                raise HTTPException(status_code=403, detail="Not authorized to edit this comment")
                
            sql = "UPDATE ticket_comments SET comment = %s"
            params = [comment_update.comment]
            
            if comment_update.comment_type_id:
                sql += ", comment_type_id = %s"
                params.append(comment_update.comment_type_id)
            
            sql += " WHERE id = %s"
            params.append(id)
            
            cursor.execute(sql, tuple(params))
            db.commit()
            return TicketCommentService.get_comment_internal(cursor, id)

    @staticmethod
    def delete_comment(id, db, current_user_id):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, created_by FROM ticket_comments WHERE id = %s", (id,))
            comment = cursor.fetchone()
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            
            # Check if admin or creator
            cursor.execute("SELECT role_id FROM users WHERE id = %s", (current_user_id,))
            user_role = cursor.fetchone()
            if not user_role or (user_role['role_id'] != 1 and comment['created_by'] != current_user_id):
                raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

            # Recursive delete of attachments
            # First, find all attachments for this comment and its replies
            def get_all_comment_ids(cid):
                cursor.execute("SELECT id FROM ticket_comments WHERE parent_comment_id = %s", (cid,))
                child_ids = [r['id'] for r in cursor.fetchall()]
                ids = [cid]
                for child in child_ids:
                    ids.extend(get_all_comment_ids(child))
                return ids
            
            all_ids = get_all_comment_ids(id)
            
            for cid in all_ids:
                cursor.execute("SELECT file_url FROM ticket_comments_attachments WHERE ticket_comment_id = %s", (cid,))
                atts = cursor.fetchall()
                for att in atts:
                    if att['file_url']:
                        clean_url = att['file_url'].lstrip('/')
                        file_path = FileService.get_upload_path(clean_url)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                # Cleanup dir
                                att_dir = os.path.dirname(file_path)
                                if os.path.exists(att_dir) and not os.listdir(att_dir):
                                    shutil.rmtree(att_dir)
                            except: pass

            cursor.execute("DELETE FROM ticket_comments WHERE id = %s", (id,))
            db.commit()
            return True
