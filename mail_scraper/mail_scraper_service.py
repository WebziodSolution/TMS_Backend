from jinja2 import FileSystemLoader
from jinja2 import Environment
import os
import datetime
import re
import imaplib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import email
from email.header import decode_header
import email.utils
from html.parser import HTMLParser
import pymysql
import logging
logger = logging.getLogger(__name__)

# Database credentials
DB_HOST = "localhost"
DB_USER = "admin"
DB_PASSWORD = "01eMatrix007!" # Please change according to your local DB
DB_NAME = "tms"

# Environment configuration with default fallback values
IMAP_SERVER = "s11777.bom1.stableserver.net"
SMTP_PORT=587
IMAP_PORT = 993
EMAIL_ACCOUNT = "supportdesk@ematrixinfotechpms.com"
EMAIL_PASSWORD = "01eMatrix007!"

# Setup Jinja2 environment
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
try:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
except Exception as e:
    logger.info(f"Error loading template directory: {e}")
    env = None
    
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

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

def is_user_a_manager(cursor, user_id):
    """Returns True if any user reports to this user."""
    cursor.execute("SELECT id FROM users WHERE report_to = %s LIMIT 1", (user_id,))
    return cursor.fetchone() is not None

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

def notify_users(cursor, comment, type_id, conn):
        ticket_id = comment['ticket_id']
        cursor.execute("SELECT title, ticket_no, project_id FROM tickets WHERE id = %s", (ticket_id,))
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
                manager_ids = get_user_hierarchy_info(cursor, dev['assign_to'])
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
                if is_user_a_manager(cursor, u['assign_to']):
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
                if is_user_a_manager(cursor, u['assign_to']):
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
            send_email(r['email'], subject, "email_template.html", context)

def send_email(to_email: str, subject: str, template_name: str, context: dict):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"DeskEmatrixInfoTech <{EMAIL_ACCOUNT}>"
        msg['To'] = to_email
        msg['Reply-To'] = EMAIL_ACCOUNT
        # Inject current year into context
        context = dict(context) if context else {}
        context.setdefault("current_year", datetime.datetime.now().year)

        if env:
            try:
                template = env.get_template(template_name)
                html_body = template.render(context)              
                # msg.attach(MIMEText(html_body, "html"))
                html_body_2 = f"""
                {html_body}
                """
                msg.attach(MIMEText(html_body_2, "html", "utf-8"))
            except Exception as e:
                print("Error rendering template: {e}")
                logger.error(f"Error rendering template: {e}", exc_info=True)
                # Fallback to simple body
                fallback_msg = str(context.get("message", subject)).replace('\r\n', '\n').replace('\n', '\r\n')
                msg.attach(MIMEText(fallback_msg, 'plain'))
        else:
            fallback_msg = str(context.get("message", subject)).replace('\r\n', '\n').replace('\n', '\r\n')
            msg.attach(MIMEText(fallback_msg, 'plain'))

        logger.info(f"Preparing to send email to {to_email} (Subject: {subject})")

        try:
            logger.info("Initializing SMTP connection...")
            if SMTP_PORT == 465:
                logger.info("Using SMTP_SSL for port 465")
                server = smtplib.SMTP_SSL(IMAP_SERVER, SMTP_PORT, timeout=15)
            else:
                logger.info("Using standard SMTP connection")
                server = smtplib.SMTP(IMAP_SERVER, SMTP_PORT, timeout=15)

            # Set debug level to 1 to print SMTP session traffic
            # server.set_debuglevel(1)

            if SMTP_PORT != 465:
                server.ehlo()
                logger.info("Starting TLS...")
                server.starttls()
                server.ehlo()

            logger.info(f"Logging in as {EMAIL_ACCOUNT}...")
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)

            logger.info(f"Sending email payload to {to_email}...")
            server.sendmail(EMAIL_ACCOUNT, to_email, msg.as_string())

            logger.info("Closing SMTP connection...")
            server.quit()

            print(f"Email successfully sent to {to_email}")
            logger.info(f"Email successfully sent to {to_email}")      
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)

class HTMLFilter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ['p', 'div', 'br', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
            self.text.append('\n')

    def handle_endtag(self, tag):
        if tag in ['p', 'div', 'tr', 'li']:
            self.text.append('\n')

    def get_text(self):
        return "".join(self.text)

def strip_html(html_content):
    try:
        parser = HTMLFilter()
        parser.feed(html_content)
        return parser.get_text()
    except Exception:
        return re.sub(r'<[^>]+>', '', html_content)

def decode_mime_words(header_text):
    if not header_text:
        return ""
    decoded_fragments = []
    for fragment, encoding in decode_header(header_text):
        if isinstance(fragment, bytes):
            charset = encoding or 'utf-8'
            try:
                decoded_fragments.append(fragment.decode(charset, errors='replace'))
            except Exception:
                decoded_fragments.append(fragment.decode('utf-8', errors='replace'))
        else:
            decoded_fragments.append(str(fragment))
    return "".join(decoded_fragments)

def extract_ticket_number(subject, body=""):
    if subject:
        # Matches Ticket(TMS-04) or Ticket (TMS-04) as given in user prompt examples
        match = re.search(r'Ticket\s*\(\s*([^)]+)\s*\)', subject, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback to general parenthesis matching in subject e.g. (TMS-04)
        match_fallback = re.search(r'\(([A-Za-z0-9_-]+)\)', subject)
        if match_fallback:
            return match_fallback.group(1).strip()

    if body:
        # Fallback check in body text e.g. Ticket No: Vivekanand-03 or Ticket No: 360Pipe-05
        match_body = re.search(r'Ticket\s*No\s*:\s*([A-Za-z0-9_-]+)', body, re.IGNORECASE)
        if match_body:
            return match_body.group(1).strip()

    return None

def is_likely_name(text):
    if not text:
        return False
    lower_text = text.lower().strip(',. ')
    exclusions = {
        "thanks", "thank you", "regards", "sincerely", "best", "yours", "yours sincerely", 
        "best regards", "regard", "hi", "hello", "help", "needed", "task", "ticket", 
        "issue", "comment", "user", "admin", "client", "developer", "manager"
    }
    if lower_text in exclusions:
        return False
    words = text.split()
    if not (1 <= len(words) <= 4):
        return False
    for word in words:
        if not word[0].isupper():
            return False
        clean_word = word.strip(',. ')
        if not clean_word:
            continue
        if not all(c.isalpha() or c in '.-' for c in clean_word):
            return False
    return True

def clean_reply_content(body):
    if not body:
        return ""

    lines = body.splitlines()
    cleaned_lines = []
    
    quote_signature_patterns = [
        r'^_{3,}',                           # _____ (underscores)
        r'^-{3,}',                           # ----- (dashes)
        r'^from:\s*',                        # From: ...
        r'^on\s+.*wrote:\s*$',               # On ... wrote:
        r'^sent:\s*',                        # Sent: ...
        r'^sincerely',                       # Sincerely...
        r'^best regards',                    # Best regards...
        r'^regards',                         # Regards...
        r'^thanks\s*&\s*regards',           # Thanks & Regards...
        r'^thanks\s+and\s+regards',         # Thanks and Regards...
    ]

    for line in lines:
        stripped = line.strip()
        
        # Stop processing if line matches quote or signature marker
        if stripped:
            if any(re.search(pattern, stripped, re.IGNORECASE) for pattern in quote_signature_patterns):
                break

            # Stop if line looks like a name/role signature block right after main reply if common patterns match
            if cleaned_lines and (stripped.lower().startswith("developer") or "ematrix infotech" in stripped.lower()):
                # Find the last non-empty line in cleaned_lines
                idx = len(cleaned_lines) - 1
                while idx >= 0 and not cleaned_lines[idx].strip():
                    idx -= 1
                
                if idx >= 0:
                    last_non_empty = cleaned_lines[idx].strip()
                    if is_likely_name(last_non_empty):
                        # Remove the name and all blank lines after it
                        cleaned_lines = cleaned_lines[:idx]
                
                # Also clean trailing empty lines from the rest of the message
                while cleaned_lines and not cleaned_lines[-1].strip():
                    cleaned_lines.pop()
                break
            
        cleaned_lines.append(line.rstrip())

    # Preserving newlines and spaces
    result = "\n".join(cleaned_lines).strip()
    if not result:
        result = "\n".join(lines).strip()
    return result

def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    html_text = payload.decode(charset, errors='replace')
                    body = strip_html(html_text)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            raw_text = payload.decode(charset, errors='replace')
            if content_type == "text/html":
                body = strip_html(raw_text)
            else:
                body = raw_text
    cleaned_content = clean_reply_content(body)
    return cleaned_content, body

def scrape_emails():
    print(f"Connecting to IMAP server {IMAP_SERVER}...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("INBOX")
    except Exception as e:
        print(f"Error connecting or logging into IMAP server: {e}")
        return []

    # Search for all emails using UID
    status, messages = mail.uid('search', None, "ALL")
    if status != "OK":
        print("No messages found or error searching mailbox.")
        mail.logout()
        return []

    email_uids = messages[0].split()
    print(f"Found total {len(email_uids)} emails in INBOX. Filtering target emails...")

    scraped_data = []

    # Process each email (fetching from latest to oldest)
    for e_uid in reversed(email_uids):
        status, msg_data = mail.uid('fetch', e_uid, "(RFC822)")
        if status != "OK":
            continue

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                raw_subject = msg.get("Subject", "")
                subject = decode_mime_words(raw_subject)

                # Check filter condition: subject includes "New Ticket" or "New Comment"
                subject_lower = subject.lower()
                if "new ticket" in subject_lower or "new comment" in subject_lower:
                    raw_from = msg.get("From", "")
                    from_decoded = decode_mime_words(raw_from)
                    _, sender_email = email.utils.parseaddr(from_decoded)
                    if not sender_email:
                        sender_email = from_decoded

                    content, full_body = extract_body(msg)
                    ticket_no = extract_ticket_number(subject, full_body)

                    scraped_data.append({
                        "email": sender_email,
                        "ticket_no": ticket_no,
                        "content": content,
                        "subject": subject,
                        "uid": e_uid.decode('utf-8') if isinstance(e_uid, bytes) else str(e_uid)
                    })

    mail.logout()
    return scraped_data

# def print_tabular(records):
#     print("\n" + "="*80)
#     print("MAIL SCRAPPER RESULTS")
#     print("="*80 + "\n")
#     if not records:
#         print("No emails matching criteria ('New Ticket' or 'New Comment') were found.")
#         return

#     # Print markdown table header
#     print("| Email | Ticket No | Content |")
#     print("| --- | --- | --- |")
#     for rec in records:
#         email_str = rec['email']
#         ticket_str = rec['ticket_no']
#         # Escape pipe characters in content to avoid breaking markdown table
#         content_str = rec['content'].replace("|", "\\|")
#         print(f"| {email_str} | {ticket_str} | {content_str} |")

if __name__ == "__main__":
    records = scrape_emails()
    if records:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for rec in records:
                email_str = rec['email']
                ticket_str = rec['ticket_no']
                # Escape pipe characters in content to avoid breaking markdown table
                content_str = rec['content'].replace("|", "\\|")
                if ticket_str != None:
                    cursor.execute("SELECT * FROM tickets WHERE ticket_no = %s", (ticket_str,))
                    ticket_data = cursor.fetchone()                  
                    cursor.execute("SELECT * FROM users WHERE email = %s", (email_str,))
                    user_data = cursor.fetchone()

                    if user_data and ticket_data:
                        sql = """
                            INSERT INTO ticket_comments (ticket_id, comment, parent_comment_id, comment_type_id, created_by)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        html_content_str = content_str.replace('\n', '<br>')
                        cursor.execute(sql, (
                            ticket_data['id'], f'<p>{html_content_str}</p>', None, 
                            6, user_data['id']
                        ))
                        conn.commit()
                        comment_id = cursor.lastrowid
                
                        # Fetch the newly created comment
                        comment = get_comment_internal(cursor, comment_id)
                        notify_users(cursor, comment, 6, conn)

        # Remove mails from mailbox which has ticket_no found from subject only
        uids_to_delete = []
        for rec in records:
            if rec.get("uid"):
                uids_to_delete.append(rec["uid"])

        if uids_to_delete:
            print(f"Connecting to IMAP server to delete {len(uids_to_delete)} emails (found ticket_no in subject)...")
            try:
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
                mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                mail.select("INBOX")
                for uid in uids_to_delete:
                    print(f"Deleting email UID {uid}...")
                    mail.uid('store', uid, '+FLAGS', '\\Deleted')
                mail.expunge()
                mail.logout()
                print("Emails successfully deleted and mailbox expunged.")
            except Exception as e:
                print(f"Error deleting emails: {e}")