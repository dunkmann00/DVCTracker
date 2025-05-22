from functools import wraps


class NotificationResponse:
    def __init__(self, success=None, msg=None, data=None):
        self.success = success
        self.msg = msg
        self.data = data


NotificationResponse.Success = NotificationResponse(True)
NotificationResponse.Fail = NotificationResponse(False)


def log_response(service, success_msg, raise_on_fail=False):
    def decorated_function(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            response = f(*args, **kwargs)
            if response.success:
                if success_msg:
                    print(f"{service}: {success_msg}")
            else:
                if response.msg:
                    msg = f"{service}: {response.msg}"
                else:
                    msg = (
                        f"{service}: There was a problem with the notification."
                    )
                print(msg)
                if raise_on_fail:
                    raise Exception(msg)
            return response

        return decorator

    return decorated_function
