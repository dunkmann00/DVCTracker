from werkzeug.utils import cached_property
from werkzeug.datastructures import MultiDict
from datetime import datetime
from . import db
from .util import (
    SpecialTypes,
    CharacteristicTypes,
    ContactTypes,
    ProxyAttribute,
    InheritedModelLoader,
    first_index_or_none
)
from sqlalchemy import orm
from sqlalchemy.ext.hybrid import hybrid_property, HybridExtensionType
from .security import generate_password_hash, check_and_update_password_hash
from datetime import date
import tomlkit

@orm.declarative_mixin
class StaticDataMixin():

    static_index = db.Column(db.Integer)

    @classmethod
    def insert_data_from(cls, path):
        with open(path, mode="r", encoding="utf-8") as f:
            content = f.read()
            data = tomlkit.loads(content)
            default_data = data["defaults"].get(cls._static_data_name, {})
            cls_data = data.get(cls._static_data_name)
            if cls_data:
                primary_key = getattr(cls, "_primary_key", None) or db.inspect(cls).primary_key[0].key
                db_data = {getattr(row, primary_key):row for row in db.session.scalars(db.select(cls)).all()}

                for i, static_item in enumerate(cls_data):
                    db_item = db_data.pop(static_item[primary_key], None)
                    static_item["static_index"] = i
                    if db_item:
                        cls.update_db_item_with_static(db_item, static_item)
                    else:
                        db.session.add(cls(**(default_data | static_item)))

                for old_item in db_data.values():
                    db.session.delete(old_item)

                db.session.commit()
            else:
                print(f"No static data found for '{cls._static_data_name}'")

    @staticmethod
    def update_db_item_with_static(db_item, static_item):
        for key, value in static_item.items():
            if value != getattr(db_item, key):
                setattr(db_item, key, value)

class ProxyConversionMixin():
    @classmethod
    def convert_proxy(cls, proxy):
        orm_attr = getattr(cls, proxy.attr, None)
        if orm_attr is None: # This can happen if no queries have been performed yet
            orm.configure_mappers()
            orm_attr = getattr(cls, proxy.attr)
        model = orm_attr.mapper.class_
        with db.session.no_autoflush:
            entity = db.session.get(model, proxy.id)
        if entity is None:
            raise RuntimeError(
                f"Proxy object '{proxy}' could not be successfully converted.\n"
                f"Check if '{proxy.id}' needs to be added into 'static_data.toml'"
            )
        return entity

class DefaultEntityMixin():
    class DefaultEntity():
        def __get__(self, instance, owner):
            with db.session.no_autoflush:
                entity = db.session.get(owner, owner.default_id)
            if not entity:
                entity = owner()
                owner_pk = db.inspect(owner).primary_key[0]
                setattr(entity, owner_pk.key, owner.default_id)
                db.session.add(entity)
            return entity

    default_id = 0
    default = DefaultEntity()

class StoredSpecial(ProxyConversionMixin, db.Model):
    """
    The database model for Specials. This object is very similar to the
    ParsedSpecial object which represents the Specials as they are parsed from
    html. This object represents the specials as they are stored in the
    database.
    """
    __tablename__ = 'stored_specials'

    def __init__(self, *args, **kwargs):
        self.new_error = False
        super().__init__(*args, **kwargs)

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
        return cls.check_out - cls.check_in

    @hybrid_property
    def price_per_night(self):
        if self.price is None or self.duration is None or self.duration == 0:
            return None
        return self.price/self.duration

    @hybrid_property
    def price_per_point(self):
        if self.price is None or self.points is None or self.points == 0:
            return None
        return self.price/self.points

    @property
    def price_increased(self):
        if not hasattr(self, "old_price") or self.old_price is None or self.price is None:
            return None
        return self.price > self.old_price

    @property
    def price_per_night_increased(self):
        if not hasattr(self, "old_price_per_night") or self.old_price_per_night is None or self.price_per_night is None:
            return None
        return self.price_per_night > self.old_price_per_night

    @property
    def price_per_point_increased(self):
        if not hasattr(self, "old_price_per_point") or self.old_price_per_point is None or self.price_per_point is None:
            return None
        return self.price_per_point > self.old_price_per_point

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

        # Check if every old_key is necessary. If multiple things change we may
        # store an old key unnecessarily.
        for key in self.get_hybrid_keys():
            old_key = f"old_{key}"
            if hasattr(self, old_key) and getattr(self, old_key) == getattr(self, key):
                delattr(self, old_key)

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
        inspector = db.inspect(cls)
        for column in inspector.c:
            if not column.foreign_keys:
                yield column.key
        for relationship in inspector.relationships:
            yield relationship.key

    @classmethod
    def get_hybrid_keys(cls):
        inspector = db.inspect(cls)
        return (key for key, descriptor in inspector.all_orm_descriptors.items() if descriptor.extension_type == HybridExtensionType.HYBRID_PROPERTY)

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
    _primary_key = "resort_id"
    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("resort", lazy="selectin"),
        foreign_keys="StoredSpecial.resort_id",
        lazy="write_only",
        passive_deletes=True
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
    _primary_key = "room_id"

    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("room", lazy="selectin"),
        foreign_keys="StoredSpecial.room_id",
        lazy="write_only",
        passive_deletes=True
    )

    @hybrid_property
    def room_id(self):
        return self.characteristic_id

    @room_id.setter
    def room_id(self, value):
        self.characteristic_id = value

    @hybrid_property
    def room_index(self):
        return self.static_index

    @room_index.setter
    def room_index(self, value):
        self.static_index = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.ROOM,
        "polymorphic_load": "inline"
    }

class View(Characteristic):
    """
    The databse model for room views.
    """
    _static_data_name = "views"
    _primary_key = "view_id"
    specials = db.relationship(
        "StoredSpecial",
        backref=db.backref("view", lazy="selectin"),
        foreign_keys="StoredSpecial.view_id",
        lazy="write_only",
        passive_deletes=True
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
        lazy="selectin",
        passive_deletes=True
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
        order_by="Room.static_index",
        backref=db.backref("category", lazy="select"),
        lazy="selectin",
        passive_deletes=True
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
        lazy="selectin",
        passive_deletes=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.VIEW,
        "polymorphic_load": "inline"
    }

class Status(DefaultEntityMixin, db.Model):
    """
    The database model for the status of the app. DVC Tracker will create one
    of these automatically. If an error is thrown that is not caught by any
    specific special, healthy will get set to False. Status also keeps track of
    the last time that the specials were updated.
    """
    status_id = db.Column(db.Integer, primary_key=True)
    healthy = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime(), default=datetime.utcnow)

    def update(self):
        self.last_updated = datetime.utcnow()

    def __repr__(self):
        return f"<Status - Healthy: {'Yes' if self.healthy else 'No'}>"

class ParserStatus(db.Model):
    """
    The model for the status of a Parser. Parsers don't need to have a Status
    but if there are no specials found from a parser a status will be created
    and will have its healthy attribute set to False. The empty_okay attribute
    can be set to True in order to process the parser with no specials. The
    idea for providing this option is to avoid all the specials from being
    deleted when something wrong happens with the site they are from. If they
    all disappear and reappear it results in unnecessary notifications being
    sent.
    """
    parser_status_id = db.Column(db.Integer, primary_key=True)
    parser_source = db.Column(db.String(32), unique=True)
    healthy = db.Column(db.Boolean)
    empty_okay = db.Column(db.Boolean, default=False)

class Contact(db.Model):
    """
    The database base model for all contacts. If get_errors is set to True, the
    contact will also receive error messages.
    """
    __tablename__ = "contacts"
    contact_id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String())
    get_errors = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"))
    last_updated = db.Column(db.DateTime(), default=datetime.utcnow)
    contact_type = db.Column(db.Enum(ContactTypes), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.BASE,
        "polymorphic_on": contact_type,
        "with_polymorphic": "*"
    }

    def ping(self):
        self.last_updated = datetime.utcnow()

    @staticmethod
    def on_set_contact(target, value, oldvalue, initiator):
        target.ping()

db.event.listen(Contact.contact, 'set', Contact.on_set_contact, propagate=True)

class Email(Contact):
    """
    The email addresses that updates should be sent to. The email addresses
    aren't checked in any way so it is up to you to make sure they are valid
    and correct.
    """

    @hybrid_property
    def email_address(self):
        return self.contact

    @email_address.setter
    def email_address(self, value):
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.EMAIL,
        "polymorphic_load": "inline"
    }

    def __repr__(self):
        return f'<Email: {self.email_address}>'

class Phone(Contact):
    """
    The phone numbers that important update messages should get sent to. The
    phone numbers aren't checked in any way so it is up to you to make sure they
    are valid and correct.
    """

    @hybrid_property
    def phone_number(self):
        return self.contact

    @phone_number.setter
    def phone_number(self, value):
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.PHONE,
        "polymorphic_load": "inline"
    }

    def __repr__(self):
        return f'<Phone Number: {self.phone_number}>'

class APN(Contact):
    """
    The Apple Push Tokens that updates should be sent to.
    """

    @hybrid_property
    def push_token(self):
        return self.contact

    @push_token.setter
    def push_token(self, value):
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.APN,
        "polymorphic_load": "inline"
    }

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
            if not isinstance(value, dict):
                return value

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
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(), unique=True)
    password_hash = db.Column(db.String())
    important_criteria = db.Column(ImportantCriteriaType)
    last_accessed = db.Column(db.DateTime(), default=datetime.utcnow)

    emails = db.relationship(
        "Email",
        order_by="Email.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin"
    )
    phones = db.relationship(
        "Phone",
        order_by="Phone.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin"
    )
    apns = db.relationship(
        "APN",
        order_by="APN.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin"
    )

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        valid, new_hash = check_and_update_password_hash(self.password_hash, password)
        if valid and new_hash is not None:
            self.password_hash = new_hash
            db.session.commit()
        return valid

    def get_contacts_for(self, contact_type):
        if contact_type is ContactTypes.EMAIL:
            return self.emails
        elif contact_type is ContactTypes.PHONE:
            return self.phones
        elif contact_type is ContactTypes.APN:
            return self.apns
        else:
            return None

    @classmethod
    def contact_class_for(cls, contact_type):
        return cls.get_contacts_for(cls, contact_type).property.mapper.class_

    def get_contact(self, contact_id, contact_type):
        if contact_id is None:
            return None
        # Doing it this way avoids another potential db query. The key should
        # already be in the identity map, if it isn't it means it isn't a
        # contact that belongs to this user, and therefore is not valid
        key = db.session.identity_key(Contact, contact_id)
        contact = db.session.identity_map.get(key)

        # Shouldn't need the 'contact.user == self' check, because only the
        # user's contacts should be loaded into the identity map, but putting it
        # here anyway as an extra precaution
        if contact and contact.user == self and contact.contact_type == contact_type:
            return contact
        return None

    def is_valid_contact_id(self, contact_id, contact_type):
        return self.get_contact(contact_id, contact_type) is not None

    def is_new_contact(self, contact_value, contact_type):
        # For now this will work in such a way where a contact can be reused
        # across different accounts
        return first_index_or_none(self.get_contacts_for(contact_type), lambda x: x.contact == contact_value) is None

    def ping(self):
        self.last_accessed = datetime.utcnow()

    def __repr__(self):
        return f'<User: {self.username}>'
