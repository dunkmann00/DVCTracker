from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, ClassVar, Generator

import sqlalchemy
import tomlkit
from sqlalchemy import Column, Dialect, Numeric, orm, type_coerce
from sqlalchemy.ext.hybrid import HybridExtensionType, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.operators import OperatorType
from werkzeug.datastructures import MultiDict
from werkzeug.utils import cached_property

from app.parsers.base_parser import ParsedSpecial

from . import db
from .security import check_and_update_password_hash, generate_password_hash
from .util import (
    CharacteristicTypes,
    ContactTypes,
    InheritedModelLoader,
    ProxyAttribute,
    SpecialTypes,
    first_index_or_none,
)


@orm.declarative_mixin
class StaticDataMixin:
    static_index: Mapped[int] = mapped_column(nullable=True)
    _static_data_name: str

    @classmethod
    def insert_data_from(cls, path: str) -> None:
        with open(path, mode="r", encoding="utf-8") as f:
            content = f.read()
            data = tomlkit.loads(content)
            default_data = data["defaults"].get(cls._static_data_name, {})
            cls_data = data.get(cls._static_data_name)
            if cls_data:
                primary_key = (
                    getattr(cls, "_primary_key", None)
                    or db.inspect(cls).primary_key[0].key
                )
                db_data = {
                    getattr(row, primary_key): row
                    for row in db.session.scalars(db.select(cls)).all()
                }

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
    def update_db_item_with_static(
        db_item: object, static_item: dict[str, str]
    ) -> None:
        for key, value in static_item.items():
            if value != getattr(db_item, key):
                setattr(db_item, key, value)


class ProxyConversionMixin:
    @classmethod
    def convert_proxy(cls, proxy: ProxyAttribute) -> object:
        orm_attr = getattr(cls, proxy.attr, None)
        if (
            orm_attr is None
        ):  # This can happen if no queries have been performed yet
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


class DefaultEntityMixin:
    class DefaultEntity:
        def __get__(self, instance, owner) -> object:  # noqa: ANN001
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

    __tablename__ = "stored_specials"

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        self.new_error: bool = False
        super().__init__(*args, **kwargs)

    special_id: Mapped[str] = mapped_column(primary_key=True)
    reservation_id: Mapped[str] = mapped_column(db.String(64), nullable=True)
    source: Mapped[str] = mapped_column(db.String(32), nullable=True)
    source_name: Mapped[str] = mapped_column(db.String(32), nullable=True)
    url: Mapped[str] = mapped_column(db.String(150), nullable=True)
    type: Mapped[SpecialTypes] = mapped_column(nullable=True)
    points: Mapped[int] = mapped_column(nullable=True)
    price: Mapped[int] = mapped_column(nullable=True)
    check_in: Mapped[date] = mapped_column(nullable=True)
    check_out: Mapped[date] = mapped_column(nullable=True)
    resort_id: Mapped[str] = mapped_column(
        db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"),
        nullable=True,
    )
    room_id: Mapped[str] = mapped_column(
        db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"),
        nullable=True,
    )
    view_id: Mapped[str] = mapped_column(
        db.ForeignKey("characteristics.characteristic_id", ondelete="SET NULL"),
        nullable=True,
    )
    error: Mapped[bool] = mapped_column(default=False, nullable=True)

    attribute_deps = MultiDict()

    @orm.reconstructor
    def init_on_load(self) -> None:
        self.new_error = False

    @hybrid_property
    def duration(self) -> int | None:
        if self.check_out is None or self.check_in is None:
            return None
        delta = self.check_out - self.check_in
        days = delta.days
        return days

    @duration.inplace.expression  # pyright: ignore[reportArgumentType]
    @classmethod
    def _duration_expression(cls) -> ColumnElement[timedelta]:
        return cls.check_out - cls.check_in

    @hybrid_property
    def price_per_night(self) -> Decimal | None:
        if self.price is None or self.duration is None or self.duration == 0:
            return None

        return Decimal(self.price) / Decimal(self.duration)

    @price_per_night.inplace.expression  # pyright: ignore[reportArgumentType]
    @classmethod
    def _price_per_night_expression(cls) -> ColumnElement[Decimal]:
        return type_coerce(cls.price / cls.duration, Numeric)

    @hybrid_property
    def price_per_point(self) -> Decimal | None:
        if self.price is None or self.points is None or self.points == 0:
            return None
        return Decimal(self.price) / Decimal(self.points)

    @price_per_point.inplace.expression  # pyright: ignore[reportArgumentType]
    @classmethod
    def _price_per_point_expression(cls) -> ColumnElement[Decimal]:
        return type_coerce(cls.price / cls.points, Numeric)

    @property
    def price_increased(self) -> bool | None:
        if (
            not hasattr(self, "old_price")
            or self.old_price is None  # pyright: ignore[reportAttributeAccessIssue]
            or self.price is None
        ):
            return None
        return self.price > self.old_price  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def price_per_night_increased(self) -> bool | None:
        if (
            not hasattr(self, "old_price_per_night")
            or self.old_price_per_night is None  # pyright: ignore[reportAttributeAccessIssue]
            or self.price_per_night is None
        ):
            return None
        return self.price_per_night > self.old_price_per_night  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def price_per_point_increased(self) -> bool | None:
        if (
            not hasattr(self, "old_price_per_point")
            or self.old_price_per_point is None  # pyright: ignore[reportAttributeAccessIssue]
            or self.price_per_point is None
        ):
            return None
        return self.price_per_point > self.old_price_per_point  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def from_parsed_special(
        cls, parsed_special: ParsedSpecial
    ) -> "StoredSpecial":
        new_special = StoredSpecial()
        for key in cls.get_core_keys():
            value = getattr(parsed_special, key, None)
            if isinstance(value, ProxyAttribute):
                value = cls.convert_proxy(value)
            setattr(new_special, key, value)
        return new_special

    def update_with_special(
        self, other: "StoredSpecial | ParsedSpecial"
    ) -> None:
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
            if hasattr(self, old_key) and getattr(self, old_key) == getattr(
                self, key
            ):
                delattr(self, old_key)

    def set_old_key(self, key: str) -> None:
        dependents = self.attribute_deps.getlist(key)
        if dependents:
            for dependent_key in dependents:
                old_dep_key = f"old_{dependent_key}"
                if not hasattr(
                    self, old_dep_key
                ):  # Only update it the first time, before anything else has changed
                    setattr(self, old_dep_key, getattr(self, dependent_key))
        old_key = f"old_{key}"
        setattr(self, old_key, getattr(self, key))

    @orm.validates("error")
    def error_change(self, key: str, error: bool) -> bool:
        """
        Sets 'new_error' to True when the 'error' value is set to True after
        the object is created. If the ORM sets 'error' to True when it loads
        it from the database 'new_error' remains False.
        """
        if not self.error and error:
            self.new_error = True
        return error

    def __eq__(self, other: object) -> bool:
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

    def __repr__(self) -> str:
        return f"<Stored Special: {self.special_id}>"

    @classmethod
    def get_core_keys(cls) -> Generator[str, None, None]:
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
    def get_hybrid_keys(cls) -> Generator[str, None, None]:
        inspector = db.inspect(cls)
        return (
            key
            for key, descriptor in inspector.all_orm_descriptors.items()
            if descriptor.extension_type == HybridExtensionType.HYBRID_PROPERTY
        )

    @classmethod
    def get_attribute_deps(cls, attribute: Column) -> list[str]:
        dependors = attribute.get_children()
        if not dependors:
            return [attribute.key]
        attr_deps = []
        for dependor in dependors:
            attr_deps += cls.get_attribute_deps(dependor)
        return attr_deps

    @classmethod
    def check_attribute_deps(cls) -> None:
        for key in cls.get_hybrid_keys():
            attribute = getattr(cls, key)
            cls.attribute_deps.update(
                dict.fromkeys(cls.get_attribute_deps(attribute), key)
            )


StoredSpecial.check_attribute_deps()


class Characteristic(StaticDataMixin, db.Model):
    """
    The database base model for all characteristics (Resorts, Rooms, Views)
    """

    __tablename__ = "characteristics"
    characteristic_id: Mapped[str] = mapped_column(
        db.String(100), primary_key=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    category_id: Mapped[str] = mapped_column(
        db.String(100),
        db.ForeignKey("categories.category_id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[CharacteristicTypes] = mapped_column(
        db.Enum(CharacteristicTypes), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.BASE,
        "polymorphic_on": type,
        "with_polymorphic": "*",
    }


class CharacteristicModelLoader(InheritedModelLoader):
    model = Characteristic
    order_by = [Characteristic.type, Characteristic.name]

    def convert_group_key(self, key: CharacteristicTypes) -> str:
        return f"{key.value}s"


class Resort(Characteristic):
    """
    The database model for resorts.
    """

    _static_data_name = "resorts"
    _primary_key = "resort_id"
    specials: Mapped[list[StoredSpecial]] = relationship(
        "StoredSpecial",
        backref=db.backref("resort", lazy="selectin"),
        foreign_keys="StoredSpecial.resort_id",
        lazy="write_only",
        passive_deletes=True,
    )

    @hybrid_property
    def resort_id(self) -> str:
        return self.characteristic_id

    @resort_id.inplace.setter
    def _resort_id_setter(self, value: str) -> None:
        self.characteristic_id = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.RESORT,
        "polymorphic_load": "inline",
    }


class Room(Characteristic):
    """
    The database model for Room types.
    """

    _static_data_name = "rooms"
    _primary_key = "room_id"

    specials: Mapped[list[StoredSpecial]] = relationship(
        "StoredSpecial",
        backref=db.backref("room", lazy="selectin"),
        foreign_keys="StoredSpecial.room_id",
        lazy="write_only",
        passive_deletes=True,
    )

    @hybrid_property
    def room_id(self) -> str:
        return self.characteristic_id

    @room_id.inplace.setter
    def _room_id_setter(self, value: str) -> None:
        self.characteristic_id = value

    @hybrid_property
    def room_index(self) -> int:
        return self.static_index

    @room_index.inplace.setter
    def _room_index_setter(self, value: int) -> None:
        self.static_index = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.ROOM,
        "polymorphic_load": "inline",
    }


class View(Characteristic):
    """
    The databse model for room views.
    """

    _static_data_name = "views"
    _primary_key = "view_id"
    specials: Mapped[list[StoredSpecial]] = relationship(
        "StoredSpecial",
        backref=db.backref("view", lazy="selectin"),
        foreign_keys="StoredSpecial.view_id",
        lazy="write_only",
        passive_deletes=True,
    )

    @hybrid_property
    def view_id(self) -> str:
        return self.characteristic_id

    @view_id.inplace.setter
    def _view_id_setter(self, value: str) -> None:
        self.characteristic_id = value

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.VIEW,
        "polymorphic_load": "inline",
    }


class Category(StaticDataMixin, db.Model):
    """
    The database base model for all categories.
    """

    __tablename__ = "categories"
    category_id: Mapped[str] = mapped_column(db.String(100), primary_key=True)
    name: Mapped[str] = mapped_column(nullable=True)
    type: Mapped[CharacteristicTypes] = mapped_column(nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.BASE,
        "polymorphic_on": type,
        "with_polymorphic": "*",
    }


class CategoryModelLoader(InheritedModelLoader):
    model = Category
    order_by = [Category.type, Category.name]

    def convert_group_key(self, key: CharacteristicTypes) -> str:
        return f"{key.value}s"


class ResortCategory(Category):
    """
    The database model for resort categories.
    """

    _static_data_name = "resort_categories"

    resorts: Mapped[list[Resort]] = relationship(
        "Resort",
        order_by="Resort.name",
        backref=db.backref("category", lazy="select"),
        lazy="selectin",
        passive_deletes=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.RESORT,
        "polymorphic_load": "inline",
    }


class RoomCategory(Category):
    """
    The database model for Room categories.
    """

    _static_data_name = "room_categories"

    rooms: Mapped[list[Room]] = relationship(
        "Room",
        order_by="Room.static_index",
        backref=db.backref("category", lazy="select"),
        lazy="selectin",
        passive_deletes=True,
    )

    @property
    def room_index(self) -> int:
        return (
            self.rooms[0].room_index
            if self.rooms is not None and len(self.rooms) > 0
            else -1
        )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.ROOM,
        "polymorphic_load": "inline",
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
        passive_deletes=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": CharacteristicTypes.VIEW,
        "polymorphic_load": "inline",
    }


class Status(DefaultEntityMixin, db.Model):
    """
    The database model for the status of the app. DVC Tracker will create one
    of these automatically. If an error is thrown that is not caught by any
    specific special, healthy will get set to False. Status also keeps track of
    the last time that the specials were updated.
    """

    status_id: Mapped[int] = mapped_column(primary_key=True)
    healthy: Mapped[bool] = mapped_column(default=True, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda x: datetime.now(timezone.utc),
        nullable=True,
    )

    def update(self) -> None:
        self.last_updated = datetime.now(timezone.utc)

    def __repr__(self) -> str:
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

    parser_status_id: Mapped[int] = mapped_column(primary_key=True)
    parser_source: Mapped[str] = mapped_column(
        db.String(32), unique=True, nullable=True
    )
    healthy: Mapped[bool] = mapped_column(nullable=True)
    empty_okay: Mapped[bool] = mapped_column(default=False, nullable=True)


class Contact(db.Model):
    """
    The database base model for all contacts. If get_errors is set to True, the
    contact will also receive error messages.
    """

    __tablename__ = "contacts"
    contact_id: Mapped[int] = mapped_column(primary_key=True)
    contact: Mapped[str] = mapped_column(nullable=True)
    get_errors: Mapped[bool] = mapped_column(default=False, nullable=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey(
            "users.user_id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )
    last_updated: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda x: datetime.now(timezone.utc),
        nullable=True,
    )
    contact_type: Mapped[ContactTypes] = mapped_column(nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.BASE,
        "polymorphic_on": contact_type,
        "with_polymorphic": "*",
    }

    def ping(self) -> None:
        self.last_updated = datetime.now(timezone.utc)

    @staticmethod
    def on_set_contact(target: "Contact", value, oldvalue, initiator) -> None:  # noqa: ANN001
        target.ping()


db.event.listen(Contact.contact, "set", Contact.on_set_contact, propagate=True)


class Email(Contact):
    """
    The email addresses that updates should be sent to. The email addresses
    aren't checked in any way so it is up to you to make sure they are valid
    and correct.
    """

    @hybrid_property
    def email_address(self) -> str:
        return self.contact

    @email_address.inplace.setter
    def _email_address_setter(self, value: str) -> None:
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.EMAIL,
        "polymorphic_load": "inline",
    }

    def __repr__(self) -> str:
        return f"<Email: {self.email_address}>"


class Phone(Contact):
    """
    The phone numbers that important update messages should get sent to. The
    phone numbers aren't checked in any way so it is up to you to make sure they
    are valid and correct.
    """

    @hybrid_property
    def phone_number(self) -> str:
        return self.contact

    @phone_number.inplace.setter
    def _phone_number_setter(self, value: str) -> None:
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.PHONE,
        "polymorphic_load": "inline",
    }

    def __repr__(self) -> str:
        return f"<Phone Number: {self.phone_number}>"


class APN(Contact):
    """
    The Apple Push Tokens that updates should be sent to.
    """

    @hybrid_property
    def push_token(self) -> str:
        return self.contact

    @push_token.inplace.setter
    def _push_token_setter(self, value: str) -> None:
        self.contact = value

    __mapper_args__ = {
        "polymorphic_identity": ContactTypes.APN,
        "polymorphic_load": "inline",
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
        def replace_key(
            some_dict: dict[str | SpecialTypes, Any],
            key: str | SpecialTypes,
            new_key: str | SpecialTypes,
        ) -> None:
            value = some_dict.pop(key, None)
            if value is not None:
                some_dict[new_key] = value

        def coerce_compared_value(self, op: OperatorType, value: Any) -> Any:  # noqa: ANN401
            return self.impl.coerce_compared_value(op, value)

        def process_bind_param(self, value: Any, dialect: Dialect) -> Any:  # noqa: ANN401
            if not isinstance(value, dict):
                return value

            for type in SpecialTypes:
                self.replace_key(value, type, type.value)
            return value

        def process_result_value(self, value: Any, dialect: Dialect) -> Any:  # noqa: ANN401
            if not isinstance(value, dict):
                return value

            for type in SpecialTypes:
                self.replace_key(value, type.value, type)
                for criteria in value.get(type, []):
                    check_in_date = criteria.get("date", {}).get("start")
                    check_out_date = criteria.get("date", {}).get("end")
                    if check_in_date:
                        criteria["date"]["start"] = date.fromisoformat(
                            check_in_date
                        )
                    if check_out_date:
                        criteria["date"]["end"] = date.fromisoformat(
                            check_out_date
                        )
            return value

    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(nullable=True)
    important_criteria: Mapped[dict[str, Any]] = mapped_column(
        ImportantCriteriaType, nullable=True
    )
    last_accessed: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda x: datetime.now(timezone.utc),
        nullable=True,
    )

    emails: Mapped[list[Email]] = relationship(
        "Email",
        order_by="Email.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin",
    )
    phones: Mapped[list[Phone]] = relationship(
        "Phone",
        order_by="Phone.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin",
    )
    apns: Mapped[list[APN]] = relationship(
        "APN",
        order_by="APN.contact_id",
        backref=db.backref("user", lazy="select"),
        lazy="selectin",
    )

    @property
    def password(self) -> str:
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        valid, new_hash = check_and_update_password_hash(
            self.password_hash, password
        )
        if valid and new_hash is not None:
            self.password_hash = new_hash
            db.session.commit()
        return valid

    def get_contacts_for(
        self, contact_type: ContactTypes
    ) -> list[Email] | list[Phone] | list[APN] | None:
        if contact_type is ContactTypes.EMAIL:
            return self.emails
        elif contact_type is ContactTypes.PHONE:
            return self.phones
        elif contact_type is ContactTypes.APN:
            return self.apns
        else:
            return None

    @classmethod
    def contact_class_for(
        cls, contact_type: ContactTypes
    ) -> type[Email] | type[Phone] | type[APN] | None:
        return cls.get_contacts_for(cls, contact_type).property.mapper.class_  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue, reportOptionalMemberAccess]

    def get_contact(
        self, contact_id: str, contact_type: ContactTypes
    ) -> Contact | None:
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
        if (
            contact
            and contact.user == self
            and contact.contact_type == contact_type
        ):
            return contact
        return None

    def is_valid_contact_id(
        self, contact_id: str, contact_type: ContactTypes
    ) -> bool:
        return self.get_contact(contact_id, contact_type) is not None

    def is_new_contact(
        self, contact_value: Contact, contact_type: ContactTypes
    ) -> int | None:
        # For now this will work in such a way where a contact can be reused
        # across different accounts
        return (
            first_index_or_none(
                self.get_contacts_for(contact_type),  # pyright: ignore[reportArgumentType]
                lambda x: x.contact == contact_value,
            )
            is None
        )

    def ping(self) -> None:
        self.last_accessed = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<User: {self.username}>"
