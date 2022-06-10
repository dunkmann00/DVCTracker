from flask import Blueprint

notifications = Blueprint('notifications', __name__)

from . import views
from .send import (
    send_update_email,
    send_error_email,
    send_error_report_email,
    send_update_text_message,
    send_error_text_messsage,
    send_update_push_notification,
    send_error_push_notification
)
