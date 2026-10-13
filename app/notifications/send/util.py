from functools import wraps
from typing import Any, Callable


class NotificationResponse:
    Success: "NotificationResponse"
    Fail: "NotificationResponse"

    def __init__(
        self,
        success: bool | None = None,
        msg: str | None = None,
        data: str | None = None,
    ) -> None:
        self.success = success
        self.msg = msg
        self.data = data


NotificationResponse.Success = NotificationResponse(True)
NotificationResponse.Fail = NotificationResponse(False)


def log_response(
    service: str, success_msg: str, raise_on_fail: bool = False
) -> Callable[..., Any]:
    def decorated_function(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorator(*args: Any, **kwargs: Any) -> NotificationResponse:  # noqa: ANN401
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
