from flask import current_app
from .helper import log_response
from ... import env_label
from ...models import PushToken
from apns2.client import APNsClient, Notification
from apns2.payload import Payload
from apns2.credentials import TokenCredentials

def create_notifications(push_tokens, message):
    return (create_notification(push_token, message) for push_token in push_tokens)


def create_notification(push_token, message):
    payload = Payload(alert=message, sound='default')
    return Notification(token=push_token.push_token, payload=payload)


def send_notifications(notifications):
    if current_app.config['APNS_KEY_ID'] is None:
        print("No APNS_KEY_ID, not sending push notification.")
        return

    topic = current_app.config['APNS_TOPIC']
    token_credentials = TokenCredentials(
        auth_key_path=None,
        auth_key_id=current_app.config['APNS_KEY_ID'],
        team_id=current_app.config['TEAM_ID'],
        auth_key_base64=current_app.config['APNS_AUTH_KEY'],
        token_lifetime=60
    )
    client = APNsClient(
        credentials=token_credentials,
        use_sandbox=True,
        use_alternative_port=False
    )
    results = client.send_notification_batch(notifications, topic)
    return {result_key:results[result_key] for result_key in results
                if results[result_key] != 'Success'}

@log_response('APNS', 'Update Push Notification Sent')
def send_update_push_notification():
    push_tokens = PushToken.query.all()
    msg = "Hey this is DVCTracker!\nA special you are interested in was either just added or updated. Check your emails for more info!"
    notifications = create_notifications(push_tokens, msg)
    return send_notifications(notifications)

@log_response('APNS', 'Error Push Notification Sent')
def send_error_push_notification():
    push_tokens = PushToken.query.filter_by(get_errors=True).all()
    msg = "Hey this is DVCTracker!\nThere seems to be a problem checking for updates and/or sending emails. Check your emails for more info!"
    notifications = create_notifications(push_tokens, msg)
    return send_notifications(notifications)
