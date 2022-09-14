from ..models import User
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    if username == '' or password == '':
        return None
    user = User.query.filter_by(username=username).first()
    return user if user is not None and user.verify_password(password) else None
