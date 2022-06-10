from flask import current_app
from .helper import log_response
from ... import env_label
from ...models import Email
import requests

def send_email(subject, email_message, addresses, html_message=True):
    if current_app.config['MAILGUN_API_KEY'] is None:
        print('No MAILGUN API Key, not sending email.')
        return
    msg_type = "html" if html_message else "text"

    sub_env = env_label.get(current_app.env)
    sub_env = f"({sub_env}) " if sub_env else ""
    return requests.post(
        f"https://api.mailgun.net/v3/{current_app.config['MAILGUN_DOMAIN_NAME']}/messages",
        auth=("api", current_app.config['MAILGUN_API_KEY']),
        data={"from": f"DVCTracker <mailgun@{current_app.config['MAILGUN_DOMAIN_NAME']}>",
              "to": addresses,
              "subject": sub_env + subject,
              msg_type: email_message})

@log_response("Mailgun", "Update Message Sent", True)
def send_update_email(email_message):
    email_addresses = [email_address.email for email_address in Email.query]
    return send_email("DVCTracker Updates", email_message, email_addresses)

@log_response("Mailgun", "Error Message Sent")
def send_error_email(email_message, html_message=True):
    email_addresses = [email_address.email for email_address in Email.query.filter_by(get_errors=True)]
    return send_email("DVCTracker Error", email_message, email_addresses, html_message)

@log_response("Mailgun", "Error Report Sent")
def send_error_report_email(email_message, html_message=True):
    email_addresses = [email_address.email for email_address in Email.query.filter_by(get_errors=True)]
    return send_email("DVCTracker Error Report", email_message, email_addresses, html_message)
