import os
import sys
import re
import imaplib
import email
from email.header import decode_header
import email.utils
from html.parser import HTMLParser

# Environment configuration with default fallback values
IMAP_SERVER = os.getenv("IMAP_SERVER", os.getenv("SMTP_SERVER", "s11777.bom1.stableserver.net"))
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT", os.getenv("SENDER_EMAIL", "supportdesk@ematrixinfotechpms.com"))
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", os.getenv("SENDER_PASSWORD", "01eMatrix007!"))

class HTMLFilter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

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

    return "N/A"

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
        if not stripped:
            continue
        
        # Stop processing if line matches quote or signature marker
        if any(re.search(pattern, stripped, re.IGNORECASE) for pattern in quote_signature_patterns):
            break

        # Stop if line looks like a name/role signature block right after main reply if common patterns match
        if cleaned_lines and (stripped.lower().startswith("developer") or "ematrix infotech" in stripped.lower()):
            break
            
        cleaned_lines.append(stripped)

    # Fallback to single-line cleaned body if cleaning stripped everything
    result = " ".join(cleaned_lines).strip()
    if not result:
        # Simple cleanup as fallback
        fallback_lines = [l.strip() for l in lines if l.strip()]
        result = " ".join(fallback_lines)
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

    # Search for all emails
    status, messages = mail.search(None, "ALL")
    if status != "OK":
        print("No messages found or error searching mailbox.")
        mail.logout()
        return []

    email_ids = messages[0].split()
    print(f"Found total {len(email_ids)} emails in INBOX. Filtering target emails...")

    scraped_data = []

    # Process each email (fetching from latest to oldest)
    for e_id in reversed(email_ids):
        status, msg_data = mail.fetch(e_id, "(RFC822)")
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
                        "subject": subject
                    })

    mail.logout()
    return scraped_data

def print_tabular(records):
    print("\n" + "="*80)
    print("MAIL SCRAPPER RESULTS")
    print("="*80 + "\n")
    if not records:
        print("No emails matching criteria ('New Ticket' or 'New Comment') were found.")
        return

    # Print markdown table header
    print("| Email | Ticket No | Content |")
    print("| --- | --- | --- |")
    for rec in records:
        email_str = rec['email']
        ticket_str = rec['ticket_no']
        # Escape pipe characters in content to avoid breaking markdown table
        content_str = rec['content'].replace("|", "\\|")
        print(f"| {email_str} | {ticket_str} | {content_str} |")

if __name__ == "__main__":
    records = scrape_emails()
    print_tabular(records)
