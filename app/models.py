from datetime import datetime
from . import db
from sqlalchemy import orm
from sqlalchemy.inspection import inspect
from .security import pwd_context

class SpecialTypes():
    """
    Specifies the two kinds of Specials: discounted points & preconfirms.
    """
    disc_points = "disc_points"
    preconfirm = "preconfirm"


class StoredSpecial(db.Model):
    """
    The database model for Specials. This object is very similar to the
    ParsedSpecial object which represents the Specials as they are parsed from
    html. This object represents the specials as they are stored in the
    database.
    """
    __tablename__ = 'stored_specials'

    def __init__(self):
        self.new_error = False

    special_id = db.Column(db.String(), primary_key=True)
    reservation_id = db.Column(db.String(64))
    source = db.Column(db.String(32))
    source_name = db.Column(db.String(32))
    url = db.Column(db.String(150))
    type = db.Column(db.String(15))
    points = db.Column(db.Integer)
    price = db.Column(db.Integer)
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date)
    resort = db.Column(db.String(100))
    room = db.Column(db.String(100))
    error = db.Column(db.Boolean, default=False)

    @orm.reconstructor
    def init_on_load(self):
        self.new_error = False

    @property
    def duration(self):
        if self.check_out is None or self.check_in is None:
            return None
        delta = self.check_out - self.check_in
        days = delta.days
        return days

    @property
    def price_per_night(self):
        if self.price is None or self.duration is None or self.duration == 0:
            return None
        return self.price/self.duration

    @classmethod
    def from_parsed_special(cls, parsed_special):
        new_special = StoredSpecial()
        for col in cls.get_columns():
            value = getattr(parsed_special, col, None)
            setattr(new_special, col, value)
        return new_special


    def update_with_special(self, other):
        """
        Updates any values that are not equal from other to self. Other can be
        either a StoredSpecial or a ParsedSpecial. The old value will be stored
        as a variable with the prefix 'old_' added (i.e. points -> old_points).
        """
        old_price_per_night = self.price_per_night
        old_duration = self.duration
        for col in self.get_columns():
            stored_value = getattr(self, col)
            new_value = getattr(other, col)
            if new_value != stored_value:
                setattr(self, f"old_{col}", stored_value)
                setattr(self, col, new_value)
                if 'check' in col:
                    self.old_duration = old_duration
                    self.old_price_per_night = old_price_per_night
                elif 'price' == col:
                    self.old_price_per_night = old_price_per_night

    @orm.validates('error')
    def error_change(self, key, error):
        """
        Sets 'new_error' to True when the 'error' value is set to True after
        the object is created. If the ORM sets 'error' to True when it loads
        it from the database 'new_error' remains False.
        """
        if not self.error and error:
            self.new_error = True
        return error

    def __eq__(self, other):
        """
        Checks for equality by comparing all columns of the StoredSpecial to
        another object. While the type is not checked for equality the other
        object must also contain the same attributes as does a StoredSpecial.
        In this way, a ParsedSpecial can be compared and can be equal if all
        attributes are the same.
        """
        for col in self.get_columns():
            value = getattr(self, col)
            other_value = getattr(other, col)
            if value != other_value:
                return False
        return True

    def __repr__(self):
        return f'<Stored Special: {self.special_id}>'

    @classmethod
    def get_columns(cls):
        """
        Yields the names for all the columns of this Model.
        """
        inspector = inspect(cls)
        for col in inspector.c:
            yield col.name


class Status(db.Model):
    """
    The database model for the status of the app. DVCTracker will create one
    of these automatically. If an error is thrown that is not caught by any
    specific special, healthy will get set to False.
    """
    status_id = db.Column(db.Integer, primary_key=True)
    healthy = db.Column(db.Boolean)

    def __repr__(self):
        return '<Healthy: ' + 'Yes' if self.healthy else 'No'

class ParserStatus(db.Model):
    """
    The model for the status of a Parser. Parsers don't need to have a Status
    but if there are no specials found from a parser a status will be created
    and will have its healthy attribute set to False. The empty_okay attribute
    can be set to True in order to process the parser with noo specials. The
    idea for providing this option is to avoid all the specials from being
    deleted when something wrong happens with the site they are from. If they
    all disappear and reappear it results in unnecessary notifications being
    sent.
    """
    parser_status_id = db.Column(db.Integer, primary_key=True)
    parser_source = db.Column(db.String(32), unique=True)
    healthy = db.Column(db.Boolean)
    empty_okay = db.Column(db.Boolean, default=False)

class Email(db.Model):
    """
    The email addresses that updates should be sent to. If get_errors is set
    to True, the address will also receive error messages. The email addresses
    aren't checked in any way so it is up to you to make sure they are valid
    and correct.
    """
    __tablename__ = 'emails'

    email = db.Column(db.String(80), primary_key=True)
    get_errors = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Email: {self.email}>'

class PhoneNumber(db.Model):
    """
    The phone numbers that important update messages should get sent to. If
    get_errors is set to True, the number will also receive error messages. The
    phone numbers aren't checked in any way so it is up to you to make sure they
    are valid and correct.
    """
    __tablename__ = 'phone_numbers'

    phone_number = db.Column(db.String(11), primary_key=True)
    get_errors = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Phone Number: {self.phone_number}>'

class PushToken(db.Model):
    """
    The Apple Push Tokens that updates should be sent to.
    """
    __tablename__ = 'push_tokens'

    push_token = db.Column(db.String(), primary_key=True)
    get_errors = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime(), default=datetime.utcnow)

    def ping(self):
        self.last_updated = datetime.utcnow()

    @staticmethod
    def on_set_push_token(target, value, oldvalue, initiator):
        target.ping()

db.event.listen(PushToken.push_token, 'set', PushToken.on_set_push_token)

class User(db.Model):
    """
    The User account that is used to protect certain endpoints
    """
    __tablename__ = 'users'
    username = db.Column(db.String(), primary_key=True)
    password_hash = db.Column(db.String())
    important_criteria = db.Column(db.JSON)
    last_accessed = db.Column(db.DateTime(), default=datetime.utcnow)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        valid, new_hash = pwd_context.verify_and_update(password,
                                                        self.password_hash)
        if valid and new_hash is not None:
            self.password_hash = new_hash
            db.session.commit()
        return valid

    def ping(self):
        self.last_accessed = datetime.utcnow()
