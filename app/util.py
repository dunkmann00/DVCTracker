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
        query = self.model.query.order_by(*self.order_by)
        for key, group in groupby(query, key=lambda x : getattr(x, self.discriminator.name)):
            results = list(group)
            setattr(self, self.convert_group_key(key), results)

def test_old_values(special, increase):
    special.old_resort = {'name': 'Copper Creek'}
    special.old_room = {'name': '2-Bedroom'}
    special.old_view = {'name': 'Standard View'}
    if special.check_in:
        special.old_check_in = special.check_in - timedelta(1)
    if special.check_out:
        special.old_check_out = special.check_out + timedelta(1)
    if special.check_in and special.check_out:
        delta = special.old_check_out - special.old_check_in
        special.old_duration = delta.days
    special.old_reservation_id = 98765

    if special.price:
        price_change = -500 if increase else 500
        special.old_price = special.price + price_change
        if special.price_per_night:
            special.old_price_per_night = special.old_price / (special.old_duration or 1)
        if special.price_per_point:
            special.old_price_per_point = special.old_price / (special.points or 1)
