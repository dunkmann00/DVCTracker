from collections import namedtuple
from datetime import timedelta
from enum import Enum
from itertools import groupby
from typing import Any, Callable, Iterable, NamedTuple, cast

from . import db


class ProxyAttribute(NamedTuple):
    id: str
    attr: str


class SpecialTypes(Enum):
    """
    Specifies the two kinds of Specials: discounted points & preconfirms.
    """

    DISC_POINTS = "disc_points"
    PRECONFIRM = "preconfirm"

    def __html__(self) -> str:  # For Jinja2/MarkupSafe
        return self.value


class CharacteristicTypes(Enum):
    """
    Specifies the different kinds of Characteristic types
    """

    BASE = "base"
    RESORT = "resort"
    ROOM = "room"
    VIEW = "view"


class ContactTypes(Enum):
    """
    Specifies the different kinds of Contact types.
    """

    BASE = "base"
    EMAIL = "email"
    PHONE = "phone"
    APN = "apn"


class InheritedModelLoader:
    model = None
    order_by = None

    def __init__(
        self, model: object | None = None, order_by: list[Any] | None = None
    ) -> None:
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

    def convert_group_key(self, key: CharacteristicTypes) -> str:
        return f"{key}s"

    def _load(self) -> None:
        if self.order_by is None:
            return

        all_results = db.session.scalars(
            db.select(self.model).order_by(*self.order_by)
        )
        for key, group in groupby(
            all_results, key=lambda x: getattr(x, self.discriminator.name)
        ):
            results = list(group)
            setattr(self, self.convert_group_key(key), results)


def test_old_values(special: Any, increase: bool) -> Any:  # noqa: ANN401
    # This avoids having to import StoredSpecial, which causes a CircularImport Error
    # Since this is just for testing I don't think this is a big deal
    from app.models import StoredSpecial

    stored_special = cast(StoredSpecial, special)

    resort_proxy = ProxyAttribute("resort_ccv", "resort")
    room_proxy = ProxyAttribute("room_two", "room")
    view_proxy = ProxyAttribute("view_standard", "view")

    test_special = StoredSpecial(
        resort=StoredSpecial.convert_proxy(resort_proxy),
        room=StoredSpecial.convert_proxy(room_proxy),
        view=StoredSpecial.convert_proxy(view_proxy),
    )

    if stored_special.check_in:
        test_special.check_in = stored_special.check_in - timedelta(1)
    if stored_special.check_out:
        test_special.check_out = stored_special.check_out + timedelta(1)

    test_special.reservation_id = "98765"

    if stored_special.price:
        price_change = -500 if increase else 500
        test_special.price = stored_special.price + price_change
    if stored_special.points:
        test_special.points = stored_special.points

    test_special.update_with_special(stored_special)

    return test_special


def first_index_or_none(
    iterable: Iterable[Any], predicate: Callable[[Any], int]
) -> int | None:
    return next(
        (index for index, item in enumerate(iterable) if predicate(item)), None
    )
