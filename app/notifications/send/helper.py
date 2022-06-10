from functools import wraps

def log_response(service, success_msg, raise_on_fail=False):
    def decorated_function(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            response = f(*args, **kwargs)
            if response and response.status_code == requests.codes.ok:
                if success_msg:
                    print(f'{service}: {success_msg}')
            elif response:
                msg = f'{service}: {response.status_code} {response.reason}'
                print(msg)
                if raise_on_fail:
                    raise Exception(msg)
            return response
        return decorator
    return decorated_function
