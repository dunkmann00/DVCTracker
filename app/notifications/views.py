from flask import request
from . import notifications
from .. import db
from ..models import PushToken
from ..auth import auth

@notifications.route('/push-tokens', methods=['POST'])
@auth.login_required
def set_push_token():
    push_token_request = request.get_json()
    push_token_str = push_token_request.get('token', None)
    get_errors = push_token_request.get('getErrors', False)
    if push_token_str is not None:
        push_token = PushToken.query.get(push_token_str)
        if push_token is None:
            push_token = PushToken()
        push_token.push_token = push_token_str
        push_token.get_errors = get_errors
        db.session.add(push_token) # commit happens in main.after_app_request
    return ''
