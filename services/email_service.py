import smtplib
import os
import re
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader

import logging
logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")
REPLY_TO = os.getenv("REPLY_TO")

# Setup Jinja2 environment
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
try:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
except Exception as e:
    logger.info(f"Error loading template directory: {e}")
    env = None

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, template_name: str, context: dict):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"DeskEmatrixInfoTech <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Reply-To'] = REPLY_TO
        # Inject current year into context
        context = dict(context) if context else {}
        context.setdefault("current_year", datetime.datetime.now().year)

        if env:
            try:
                template = env.get_template(template_name)
                html_body = template.render(context)
                msg.attach(MIMEText(html_body, 'html'))     
            except Exception as e:
                logger.error(f"Error rendering template: {e}", exc_info=True)
                # Fallback to simple body
                fallback_msg = str(context.get("message", subject)).replace('\r\n', '\n').replace('\n', '\r\n')
                msg.attach(MIMEText(fallback_msg, 'plain'))
        else:
            fallback_msg = str(context.get("message", subject)).replace('\r\n', '\n').replace('\n', '\r\n')
            msg.attach(MIMEText(fallback_msg, 'plain'))

        logger.info(f"Preparing to send email to {to_email} (Subject: {subject})")
        logger.info(f"SMTP Configuration - Host: {SMTP_SERVER}, Port: {SMTP_PORT}, Sender: {SENDER_EMAIL}, From: {SENDER_EMAIL}, Reply-To: {REPLY_TO}")

        try:
            logger.info("Initializing SMTP connection...")
            if SMTP_PORT == 465:
                logger.info("Using SMTP_SSL for port 465")
                server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
            else:
                logger.info("Using standard SMTP connection")
                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)

            # Set debug level to 1 to print SMTP session traffic
            # server.set_debuglevel(1)

            if SMTP_PORT != 465:
                server.ehlo()
                logger.info("Starting TLS...")
                server.starttls()
                server.ehlo()

            logger.info(f"Logging in as {SENDER_EMAIL}...")
            server.login(SENDER_EMAIL, SENDER_PASSWORD)

            logger.info(f"Sending email payload to {to_email}...")
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

            logger.info("Closing SMTP connection...")
            server.quit()

            print(f"Email successfully sent to {to_email}")
            logger.info(f"Email successfully sent to {to_email}")      
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)