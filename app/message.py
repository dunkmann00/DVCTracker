from flask import current_app
from functools import wraps
from . import env_label
from .models import Email, PhoneNumber
import requests, os

def log_response(service, success_msg, raise_on_fail=False):
    def decorated_function(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            response = f(*args, **kwargs)
            if response and response.status_code == requests.codes.ok:
                if success_msg:
                    print(success_msg)
            else:
                msg = f'{service}: {response.status_code} {response.reason}'
                print(msg)
                if raise_on_fail:
                    raise Exception(msg)
            return response
        return decorator
    return decorated_function


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
    email_addresses = [email_address.email for email_address in Email.query.all()]
    return send_email("DVCTracker Updates", email_message, email_addresses)

@log_response("Mailgun", "Error Message Sent")
def send_error_email(email_message, html_message=True):
    email_addresses = [email_address.email for email_address in Email.query.filter_by(get_errors=True).all()]
    return send_email("DVCTracker Error", email_message, email_addresses, html_message)

@log_response("Mailgun", "Error Report Sent")
def send_error_report_email(email_message, html_message=True):
    email_addresses = [email_address.email for email_address in Email.query.filter_by(get_errors=True).all()]
    return send_email("DVCTracker Error Report", email_message, email_addresses, html_message)



def send_text_message(message, numbers):
    if os.environ.get("TILL_URL") is None:
        print('No TILL URL, not sending txt.')
        return

    msg_env = env_label.get(current_app.env)
    msg_env = f"({msg_env}) " if msg_env else ""
    return requests.post(os.environ.get("TILL_URL"), json={
               "phone": numbers,
               "text": msg_env + message
           })

@log_response("Till", "Update Text Sent")
def send_update_text_message():
    phone_numbers = [phone_number.phone_number for phone_number in PhoneNumber.query.all()]
    msg = "Hey this is DVCTracker!\nA special you are interested in was either just added or updated. Check your emails for more info!"
    return send_text_message(msg, phone_numbers)

@log_response("Till", "Error Text Sent")
def send_error_text_messsage():
    phone_numbers = [phone_number.phone_number for phone_number in PhoneNumber.query.filter_by(get_errors=True).all()]
    msg = "Hey this is DVCTracker!\nThere seems to be a problem checking for updates and/or sending emails. Check your emails for more info!"
    return send_text_message(msg, phone_numbers)
