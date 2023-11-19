from flask import current_app
from premailer import Premailer
from .util import log_response, NotificationResponse
from ...models import Email, db
import requests

inliner = Premailer(
    base_path="app/static/",
    allow_loading_external_files=True,
    strip_important=False,
    disable_validation=True
)

def send_email(subject, email_message, email_addresses, html_message=True):
    if current_app.config['MAILGUN_API_KEY'] is None:
        print('No MAILGUN API Key, not sending email.')
        return NotificationResponse(success=True)
    msg_type = "html" if html_message else "text"

    if html_message:
        email_message = inliner.transform(email_message)

    sub_env = current_app.config.get("ENV_LABEL")
    sub_env = f"({sub_env}) " if sub_env else ""
    response = requests.post(
        f"https://api.mailgun.net/v3/{current_app.config['MAILGUN_DOMAIN_NAME']}/messages",
        auth=("api", current_app.config['MAILGUN_API_KEY']),
        data={"from": f"DVC Tracker <mailgun@{current_app.config['MAILGUN_DOMAIN_NAME']}>",
              "to": email_addresses,
              "subject": sub_env + subject,
              msg_type: email_message}
    )

    notification_response = NotificationResponse()
    notification_response.success = response.status_code == requests.codes.ok
    if not notification_response.success:
        notification_response.msg = f"{response.status_code} {response.reason}"

    if notification_response.success:
        notification_response.data = response.json().get("id")

    return notification_response

@log_response("Mailgun", "Update Message Complete", True)
def send_update_email(email_message, user):
    email_addresses = [email.email_address for email in user.emails]
    if len(email_addresses) == 0:
        print(f"No email addresses associated with {user}. Not sending update email.")
        return NotificationResponse.Success
    return send_email("DVC Tracker Updates", email_message, email_addresses)

@log_response("Mailgun", "Error Message Complete")
def send_error_email(email_message, html_message=True):
    email_addresses = db.session.scalars(db.select(Email.email_address).filter_by(get_errors=True)).all()
    if len(email_addresses) == 0:
        print(f"No email addresses requested error messages. Not sending error email.")
        return NotificationResponse.Success
    return send_email("DVC Tracker Error", email_message, email_addresses, html_message)

@log_response("Mailgun", "Error Report Complete")
def send_error_report_email(email_message, html_message=True):
    email_addresses = db.session.scalars(db.select(Email.email_address).filter_by(get_errors=True)).all()
    if len(email_addresses) == 0:
        print(f"No email addresses requested error messages. Not sending error report email.")
        return NotificationResponse.Success
    return send_email("DVC Tracker Error Report", email_message, email_addresses, html_message)
