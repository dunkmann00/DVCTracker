from ..models import db, User
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    if username == '' or password == '':
        return None
    user = db.session.scalar(db.select(User).filter_by(username=username).limit(1))
    return user if user is not None and user.verify_password(password) else None
