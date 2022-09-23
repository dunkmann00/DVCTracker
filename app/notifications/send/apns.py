from flask import current_app
from .util import log_response, NotificationResponse
from ...models import APN
from apns2.client import APNsClient, Notification
from apns2.payload import Payload
from apns2.credentials import TokenCredentials

def create_notifications(push_tokens, message, custom=None):
    return (create_notification(push_token, message, custom) for push_token in push_tokens)


def create_notification(push_token, message, custom=None):
    msg_env = current_app.config.get("ENV_LABEL")
    message = f"({msg_env}) {message}" if msg_env else message
    payload = Payload(alert=message, sound='default', custom=custom)
    return Notification(token=push_token, payload=payload)


def send_notifications(notifications):
    if current_app.config['APNS_KEY_ID'] is None:
        print("No APNS_KEY_ID, not sending push notification.")
        return

    topic = current_app.config['APNS_TOPIC']
    token_credentials = TokenCredentials(
        auth_key_path=None,
        auth_key_id=current_app.config['APNS_KEY_ID'],
        team_id=current_app.config['APNS_TEAM_ID'],
        auth_key_base64=current_app.config['APNS_AUTH_KEY'],
        token_lifetime=60
    )
    client = APNsClient(
        credentials=token_credentials,
        use_sandbox=True,
        use_alternative_port=False
    )
    results = client.send_notification_batch(notifications, topic)
    errors = [f"Token: {token} did not send.\nError: {errors[token]}" for token in results
                if results[token] != 'Success']

    response = NotificationResponse()
    response.success = len(errors) == 0
    if not response.success:
        response.msg = "\n".join(errors)

    return response

def send_push_notification(message, push_tokens, custom=None):
    notifications = create_notifications(push_tokens, message, custom)
    return send_notifications(notifications)

@log_response('APNS', 'Update Push Notification Sent')
def send_update_push_notification(user, message=None, message_id=None):
    push_tokens = [apn.push_token for apn in user.apns]
    if len(push_tokens) == 0:
        print(f"No push tokens associated with {user}. Not sending push notification.")
        return NotificationResponse.Success
    message = message or "Hey this is DVC Tracker!\nA special you are interested in was either just added or updated. Check your emails for more info!"
    custom = message_id and {"messageID": message_id}
    return send_push_notification(message, push_tokens, custom)

@log_response('APNS', 'Error Push Notification Sent')
def send_error_push_notification(message_id=None):
    push_tokens = [apn.push_token for apn in APN.query.filter_by(get_errors=True)]
    if len(push_tokens) == 0:
        print(f"No push tokens requested error messages. Not sending error push notification.")
        return NotificationResponse.Success
    message = "Hey this is DVC Tracker!\nThere seems to be a problem checking for updates and/or sending emails. Check your emails for more info!"
    custom = message_id and {"messageID": message_id}
    return send_push_notification(message, push_tokens, custom)
