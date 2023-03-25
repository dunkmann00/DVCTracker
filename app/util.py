from . import db
from collections import namedtuple
from enum import Enum
from itertools import groupby
from datetime import timedelta

ProxyAttribute = namedtuple('ProxyAttribute', ['id', 'attr'])

class SpecialTypes(Enum):
    """
    Specifies the two kinds of Specials: discounted points & preconfirms.
    """
    DISC_POINTS = "disc_points"
    PRECONFIRM  = "preconfirm"

    def __html__(self): # For Jinja2/MarkupSafe
        return self.value


class CharacteristicTypes(Enum):
    """
    Specifies the different kinds of Characteristic types
    """
    BASE   = "base"
    RESORT = "resort"
    ROOM   = "room"
    VIEW   = "view"

class ContactTypes(Enum):
    """
    Specifies the different kinds of Contact types.
    """
    BASE  = "base"
    EMAIL = "email"
    PHONE = "phone"
    APN   = "apn"


class InheritedModelLoader:
    model = None
    order_by = None

    def __init__(self, model=None, order_by=None):
        if model is not None:
            self.model = model

        if order_by is not None:
            self.order_by = order_by

        if self.order_by is not None:
            self.discriminator = self.order_by[0]

        if self.model is not None and self.order_by is not None:
            self._load()
        else:
            msgs = []
            if self.model is None:
                msgs.append("Must provide a value for 'model'.")
            if self.order_by is None:
                msgs.append("Must provide a value for 'order_by'.")
            raise RuntimeError(" ".join(msgs))

    def convert_group_key(self, key):
        return f"{key}s"

    def _load(self):
        all_results = db.session.scalars(db.select(self.model).order_by(*self.order_by))
        for key, group in groupby(all_results, key=lambda x : getattr(x, self.discriminator.name)):
            results = list(group)
            setattr(self, self.convert_group_key(key), results)

def test_old_values(special, increase):
    Special = type(special) # This avoids having to import StoredSpecial, which causes a CircularImport Error
                            # Since this is just for testing I don't think this is a big deal
    resort_proxy = ProxyAttribute("resort_ccv", "resort")
    room_proxy = ProxyAttribute("room_two", "room")
    view_proxy = ProxyAttribute("view_standard", "view")

    test_special = Special(
        resort=Special.convert_proxy(resort_proxy),
        room=Special.convert_proxy(room_proxy),
        view=Special.convert_proxy(view_proxy)
    )

    if special.check_in:
        test_special.check_in = special.check_in - timedelta(1)
    if special.check_out:
        test_special.check_out = special.check_out + timedelta(1)

    test_special.reservation_id = 98765

    if special.price:
        price_change = -500 if increase else 500
        test_special.price = special.price + price_change
    if special.points:
        test_special.points = special.points

    test_special.update_with_special(special)

    return test_special

def first_index_or_none(iterable, predicate):
    return next((index for index, item in enumerate(iterable) if predicate(item)), None)
