from werkzeug.utils import cached_property
from werkzeug.datastructures import MultiDict
from datetime import datetime
from . import db
from .util import SpecialTypes, CharacteristicTypes, ProxyAttribute, InheritedModelLoader
from sqlalchemy import orm, inspect, ForeignKeyConstraint
from sqlalchemy.ext.hybrid import hybrid_property, HYBRID_PROPERTY
from .security import pwd_context
from datetime import date
import tomlkit, os

@orm.declarative_mixin
class StaticDataMixin():
    @classmethod
    def insert_data_from(cls, path):
        with open(path, mode="r", encoding="utf-8") as f:
            content = f.read()
            data = tomlkit.loads(content)
            default_data = data["defaults"].get(cls._static_data_name, {})
            cls_data = data.get(cls._static_data_name)
            if cls_data:
                # Clear the table so we can recreate all the rows
                # If anything changed it will get captured when recreated
                cls.query.delete()

                items = [cls(**(default_data | item)) for item in cls_data]
                db.session.add_all(items)
                db.session.commit()
            else:
                print(f"No static data found for '{cls._static_data_name}'")

class ProxyConversionMixin():
    @classmethod
    def convert_proxy(cls, proxy):
        orm_attr = getattr(cls, proxy.attr, None)
        if orm_attr is None: # This can happen if no queries have been performed yet
            orm.configure_mappers()
            orm_attr = getattr(cls, proxy.attr)
        model = getattr(cls, proxy.attr).mapper.class_
        entity = model.query.get(proxy.id)
        if entity is None:
            raise RuntimeError(
                f"Proxy object '{proxy}' could not be successfully converted.\n"
                f"Check if '{proxy.id}' needs to be added into 'static_data.toml'"
            )
        return entity


class StoredSpecial(ProxyConversionMixin, db.Model):
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
    type = db.Column(db.Enum(SpecialTypes))
    points = db.Column(db.Integer)
    price = db.Column(db.Integer)
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date)
    resort_id = db.Column(db.String, db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"))
    room_id = db.Column(db.String, db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"))
    view_id = db.Column(db.String, db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"))
    error = db.Column(db.Boolean, default=False)

    attribute_deps = MultiDict()

    @orm.reconstructor
    def init_on_load(self):
        self.new_error = False

    @hybrid_property
    def duration(self):
        if self.check_out is None or self.check_in is None:
            return None
        delta = self.check_out - self.check_in
        days = delta.days
        return days

    @duration.expression
    def duration(cls):
        if cls.check_out is None or cls.check_in is None:
            return None
        delta = cls.check_out - cls.check_in
        return delta

    @hybrid_property
    def price_per_night(self):
        if self.price is None or self.duration is None or self.duration == 0:
            return None
        return self.price/self.duration

    @classmethod
    def from_parsed_special(cls, parsed_special):
        new_special = StoredSpecial()
        for key in cls.get_core_keys():
            value = getattr(parsed_special, key, None)
            if isinstance(value, ProxyAttribute):
                value = cls.convert_proxy(value)
            setattr(new_special, key, value)
        return new_special


    def update_with_special(self, other):
        """
        Updates any values that are not equal from other to self. Other can be
        either a StoredSpecial or a ParsedSpecial. The old value will be stored
        as a variable with the prefix 'old_' added (i.e. points -> old_points).
        """
        for key in self.get_core_keys():
            stored_value = getattr(self, key)
            new_value = getattr(other, key)
            if isinstance(new_value, ProxyAttribute):
                new_value = self.convert_proxy(new_value)
            if new_value != stored_value:
                self.set_old_key(key)
                setattr(self, key, new_value)

    def set_old_key(self, key):
        dependents = self.attribute_deps.getlist(key)
        if dependents:
            for dependent_key in dependents:
                old_dep_key = f"old_{dependent_key}"
                if not hasattr(self, old_dep_key): # Only update it the first time, before anything else has changed
                    setattr(self, old_dep_key, getattr(self, dependent_key))
        old_key = f"old_{key}"
        setattr(self, old_key, getattr(self, key))


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
        for col in self.get_core_keys():
            value = getattr(self, col)
            other_value = getattr(other, col)
            if isinstance(other_value, ProxyAttribute):
                other_value = self.convert_proxy(other_value)
            if value != other_value:
                return False
        return True

    def __repr__(self):
        return f'<Stored Special: {self.special_id}>'

    @classmethod
    def get_core_keys(cls):
        """
        Yields the keys for all the attributes of this Model needed to compare
        against another special.

        We want this to only yield columns that are not foreign keys and also
        relationships.
        """
        inspector = inspect(cls)
        for column in inspector.c:
            if not column.foreign_keys:
                yield column.key
        for relationship in inspector.relationships:
            yield relationship.key

    @classmethod
    def get_hybrid_keys(cls):
        inspector = inspect(cls)
        return (key for key, descriptor in inspector.all_orm_descriptors.items() if descriptor.extension_type == HYBRID_PROPERTY)

    @classmethod
    def get_attribute_deps(cls, attribute):
        dependors = attribute.get_children()
        if not dependors:
            return [attribute.key]
        attr_deps = []
        for dependor in dependors:
            attr_deps += cls.get_attribute_deps(dependor)
        return attr_deps

    @classmethod
    def check_attribute_deps(cls):
        for key in cls.get_hybrid_keys():
            attribute = getattr(cls, key)
            cls.attribute_deps.update(dict.fromkeys(cls.get_attribute_deps(attribute), key))

StoredSpecial.check_attribute_deps()

class Characteristic(StaticDataMixin, db.Model):
    """
    The database base model for all characteristics (Resorts, Rooms, Views)
    """
    __tablename__ = "characteristics"
    characteristic_id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String, nullable=False)
    category_id = db.Column(db.String(100), db.ForeignKey("categories.category_id", ondelete="SET NULL"))
    type = db.Column(db.Enum(CharacteristicTypes), nullable=False)

    # index = db.Column(db.Integer)

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.BASE,
        "polymorphic_on": type,
        "with_polymorphic": "*"
    }

class CharacteristicModelLoader(InheritedModelLoader):
    model = Characteristic
    order_by = [Characteristic.type, Characteristic.name]

    def convert_group_key(self, key):
        return f"{key.value}s"

class Resort(Characteristic):
    """
    The database model for resorts.
    """
    _static_data_name = "resorts"
    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("resort", lazy="joined"),
        foreign_keys="StoredSpecial.resort_id",
        lazy="dynamic"
    )

    @hybrid_property
    def resort_id(self):
        return self.characteristic_id

    @resort_id.setter
    def resort_id(self, value):
        self.characteristic_id = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.RESORT,
        "polymorphic_load": "inline"
    }

class Room(Characteristic):
    """
    The database model for Room types.
    """
    _static_data_name = "rooms"
    _index_count = 0

    def __init__(self, **kwargs):
        if "room_index" not in kwargs:
            kwargs["room_index"] = self.next_index()
        super().__init__(**kwargs)

    room_index = db.Column(db.Integer)

    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("room", lazy="joined"),
        foreign_keys="StoredSpecial.room_id",
        lazy="dynamic"
    )

    @hybrid_property
    def room_id(self):
        return self.characteristic_id

    @room_id.setter
    def room_id(self, value):
        self.characteristic_id = value

    @classmethod
    def next_index(cls):
        index = cls._index_count
        cls._index_count += 1
        return index

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.ROOM,
        "polymorphic_load": "inline"
    }

class View(Characteristic):
    """
    The databse model for room views.
    """
    _static_data_name = "views"
    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("view", lazy="joined"),
        foreign_keys="StoredSpecial.view_id",
        lazy="dynamic"
    )

    @hybrid_property
    def view_id(self):
        return self.characteristic_id

    @view_id.setter
    def view_id(self, value):
        self.characteristic_id = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.VIEW,
        "polymorphic_load": "inline"
    }


class Category(StaticDataMixin, db.Model):
    """
    The database base model for all categories.
    """
    __tablename__ = "categories"
    category_id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String)
    type = db.Column(db.Enum(CharacteristicTypes), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.BASE,
        "polymorphic_on": type,
        "with_polymorphic": "*"
    }


class CategoryModelLoader(InheritedModelLoader):
    model = Category
    order_by = [Category.type, Category.name]

    def convert_group_key(self, key):
        return f"{key.value}s"

class ResortCategory(Category):
    """
    The database model for resort categories.
    """
    _static_data_name = "resort_categories"

    resorts = db.relationship(
        "Resort",
        order_by="Resort.name",
        backref=db.backref("category", lazy="select"),
        lazy="joined"
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.RESORT,
        "polymorphic_load": "inline"
    }

class RoomCategory(Category):
    """
    The database model for Room categories.
    """
    _static_data_name = "room_categories"

    rooms = db.relationship(
        "Room",
        order_by="Room.room_index",
        backref=db.backref("category", lazy="select"),
        lazy="joined"
    )

    @property
    def room_index(self):
        return self.rooms[0].room_index if self.rooms is not None and len(self.rooms) > 0 else -1

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.ROOM,
        "polymorphic_load": "inline"
    }

class ViewCategory(Category):
    """
    The databse model for room view categories.
    """
    _static_data_name = "view_categories"

    views = db.relationship(
        "View",
        order_by="View.name",
        backref=db.backref("category", lazy="select"),
        lazy="joined"
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.VIEW,
        "polymorphic_load": "inline"
    }

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

    class ImportantCriteriaType(db.TypeDecorator):
        """
        When we pull the JSON from the db, change the date strings into python
        date objects and the type string keys into SpecialTypes objects.
        """
        impl = db.JSON

        cache_ok = True

        @staticmethod
        def replace_key(some_dict, key, new_key):
            value = some_dict.pop(key, None)
            if value is not None:
                some_dict[new_key] = value

        def coerce_compared_value(self, op, value):
            return self.impl.coerce_compared_value(op, value)

        def process_bind_param(self, value, dialect):
            for type in SpecialTypes:
                self.replace_key(value, type, type.value)
            return value

        def process_result_value(self, value, dialect):
            if not isinstance(value, dict):
                return value

            for type in SpecialTypes:
                self.replace_key(value, type.value, type)
                for criteria in value.get(type, []):
                    check_in_date = criteria.get('date', {}).get('start')
                    check_out_date = criteria.get('date', {}).get('end')
                    if check_in_date:
                        criteria['date']['start'] = date.fromisoformat(check_in_date)
                    if check_out_date:
                        criteria['date']['end'] = date.fromisoformat(check_out_date)
            return value

    __tablename__ = 'users'
    username = db.Column(db.String(), primary_key=True)
    password_hash = db.Column(db.String())
    important_criteria = db.Column(ImportantCriteriaType)
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
