from fastapi import HTTPException
from services.email_service import EmailService

class AssignedTicketsService:
    @staticmethod
    def update_assigned_tickets(ticket_id: int, body, db, current_user_id: int):
        with db.cursor() as cursor:
            # 1. Verify ticket exists and get details
            cursor.execute("""
                SELECT t.title, t.ticket_no, t.due_date, p.name as project_name
                FROM tickets t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.id = %s
            """, (ticket_id,))
            ticket = cursor.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")
                
            # 2. Get old assignees to find newly added ones
            cursor.execute("SELECT assign_to FROM assigned_tickets WHERE ticket_id = %s", (ticket_id,))
            old_assignees = set([r['assign_to'] for r in cursor.fetchall()])
            
            # 3. New assignees to update
            new_assignee_objs = body.assignees
            new_assignee_ids = set([a.id for a in new_assignee_objs])
            
            # Delete old assignees for this ticket
            cursor.execute("DELETE FROM assigned_tickets WHERE ticket_id = %s", (ticket_id,))
            
            # Insert new assignees
            if new_assignee_objs:
                assignee_vals = [(ticket_id, a.id, current_user_id, a.send_mail, 1 if getattr(a, 'is_client', False) else 0) for a in new_assignee_objs]
                cursor.executemany(
                    "INSERT INTO assigned_tickets (ticket_id, assign_to, created_by, send_mail, is_client) VALUES (%s, %s, %s, %s, %s)",
                    assignee_vals
                )
            
            db.commit()
            
            # 4. Find newly assigned users to email
            newly_assigned_ids = list(new_assignee_ids - old_assignees)
            
            # Send emails like create_ticket
            send_mail_prefs = {a.id: a.send_mail for a in new_assignee_objs}
            newly_assigned_to_notify = [uid for uid in newly_assigned_ids if send_mail_prefs.get(uid, 'Y') == 'Y']
            
            if newly_assigned_to_notify:
                format_strings = ','.join(['%s'] * len(newly_assigned_to_notify))
                cursor.execute(f"SELECT email, first_name FROM users WHERE id IN ({format_strings})", tuple(newly_assigned_to_notify))
                users_to_email = cursor.fetchall()
                
                formatted_date = f"{ticket['due_date'].strftime('%b')} {ticket['due_date'].day}, {ticket['due_date'].year}" if ticket['due_date'] else 'N/A'
                subject = f"New Ticket({ticket['ticket_no']}): {ticket['title']}"
                
                for u in users_to_email:
                    context = {
                        "subject": subject,
                        "message": (
                            f"Hello {u['first_name']},<br><br>"
                            f"A new ticket has been assigned to you: <b>{ticket['title']}</b>.<br><br>"
                            f"<b>Ticket No:</b> {ticket['ticket_no']}<br>"
                            f"<b>Project:</b> {ticket['project_name'] or 'N/A'}<br>"
                            f"<b>Due Date:</b> {formatted_date}"
                        ),
                    }
                    EmailService.send_email(u['email'], subject, "email_template.html", context)
            
            # Fetch the updated list of assignees for response
            cursor.execute("""
                SELECT at.assign_to as id, at.send_mail, at.is_client, CONCAT(u.first_name, ' ', u.last_name) as name
                FROM assigned_tickets at
                JOIN users u ON at.assign_to = u.id
                WHERE at.ticket_id = %s
            """, (ticket_id,))
            updated_assignees = cursor.fetchall()
            return {"ticket_id": ticket_id, "assignees": updated_assignees}
