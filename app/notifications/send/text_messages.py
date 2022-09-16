from flask import current_app
from .util import log_response, NotificationResponse
from ...models import Phone
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

def send_text_message(message, phone_numbers):
    if current_app.config['TWILIO_SID'] is None:
        print('No Twilio SID, not sending txt.')
        return

    msg_env = current_app.config.get("ENV_LABEL")
    msg_env = f"({msg_env}) " if msg_env else ""
    account_sid = current_app.config['TWILIO_SID']
    auth_token = current_app.config['TWILIO_TOKEN']
    client = Client(account_sid, auth_token)

    err_messages = []
    for phone_number in phone_numbers:
        try:
            message_result = client.messages.create(
                messaging_service_sid=current_app.config['TWILIO_MSG_SRVC'],
                body = "- \n\n" + msg_env + message,
                to = phone_number
            )
        except TwilioRestException as err:
            err_messages.append(str(err))

    response = NotificationResponse()
    response.success = len(err_messages) == 0
    if not response.success:
        response.msg = "\n".join(err_messages)

    return response

@log_response("Twilio", "Update Text Sent")
def send_update_text_message(user, message=None):
    phone_numbers = [phone.phone_number for phone in user.phones]
    if len(phone_numbers) == 0:
        print(f"No phone numbers associated with {user}. Not sending update text message.")
        return NotificationResponse.Success
    message = message or "Hey this is DVC Tracker!\nA special you are interested in was either just added or updated. Check your emails for more info!"
    return send_text_message(message, phone_numbers)

@log_response("Twilio", "Error Text Sent")
def send_error_text_messsage():
    phone_numbers = [phone.phone_number for phone in Phone.query.filter_by(get_errors=True)]
    if len(phone_numbers) == 0:
        print(f"No phone numbers requested error messages. Not sending error text message.")
        return NotificationResponse.Success
    msg = "Hey this is DVC Tracker!\nThere seems to be a problem checking for updates and/or sending emails. Check your emails for more info!"
    return send_text_message(msg, phone_numbers)
