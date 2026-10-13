import os
import types
from collections import namedtuple
from datetime import date
from functools import cached_property
from typing import Any, Callable, Sequence

from werkzeug.datastructures import MultiDict

from app.models import Resort, StoredSpecial

from .util import SpecialTypes

Range = namedtuple("Range", ["start", "end"])


class DecoratorDict(dict):
    def mapped_func(
        self,
        key: str | SpecialTypes,
        valid_types: Sequence[SpecialTypes] | str | SpecialTypes | None = None,
    ) -> Callable[..., Any]:
        if valid_types is None:
            valid_types = (SpecialTypes.PRECONFIRM, SpecialTypes.DISC_POINTS)
        elif not isinstance(valid_types, (list, tuple)):
            valid_types = (valid_types,)  # pyright: ignore[reportAssignmentType]
        _valid_types = self.get("_valid_types", MultiDict())
        _valid_types.update({valid_type: key for valid_type in valid_types})  # pyright: ignore[reportOptionalIterable, reportGeneralTypeIssues]
        self["_valid_types"] = _valid_types

        def decorated_function(func: Callable[..., Any]) -> Callable[..., Any]:
            self[key] = func
            return func

        return decorated_function


class ImportantCriteria:
    criteria_map = DecoratorDict()

    def __init__(
        self, criteria: dict[str | SpecialTypes, Any] | None = None
    ) -> None:
        if criteria is None:
            criteria = {}
        self.criteria = criteria

    def __call__(self, special: StoredSpecial) -> bool:
        return self.is_important_special(special)

    @property
    def important_only(self) -> bool:
        return self.criteria.get("important_only", False)

    """
    The first time we access this we bind all of the 'criteria_map' functions
    and return a dict with the keys and bound functions. Because we are caching
    it we do not need to bind the functions each time and since its still a dict
    we get constant time access.
    """

    @cached_property
    def check_criteria(self) -> dict[str, Any]:
        return {
            key: types.MethodType(func, self)
            for key, func in self.criteria_map.items()
            if not key.startswith("_")
        }

    @classmethod
    def valid_criteria_for_type(cls, special_type: SpecialTypes) -> list[str]:
        return cls.criteria_map["_valid_types"].getlist(special_type)

    def is_important_special(self, special: StoredSpecial) -> bool:
        if not self.criteria:
            return False

        for criteria in self.criteria.get(special.type, []):
            important = False
            for criterion in criteria:
                important = self.check_criteria[criterion](
                    special, criteria[criterion]
                )
                if not important:
                    break
            if important:
                return True
        return False

    @criteria_map.mapped_func("date")
    def is_important_date(
        self, special: StoredSpecial, imp_date: dict[str, date]
    ) -> bool:
        check_out = special.check_out
        if check_out is None or "end" not in imp_date:
            return False
        if special.type == SpecialTypes.PRECONFIRM:
            check_in = special.check_in
            if check_in is None or "start" not in imp_date:
                return False
            r1 = Range(start=check_in, end=check_out)
            r2 = Range(start=imp_date["start"], end=imp_date["end"])
            latest_start = max(r1.start, r2.start)
            earliest_end = min(r1.end, r2.end)
            overlap = (earliest_end - latest_start).days + 1
            return overlap > 0
        else:
            return check_out >= imp_date["end"]

    @criteria_map.mapped_func("length_of_stay", SpecialTypes.PRECONFIRM)
    def is_important_length_of_stay(
        self, special: StoredSpecial, value: int
    ) -> bool:
        if special.duration is None:
            return False
        return special.duration >= value

    @criteria_map.mapped_func("price", SpecialTypes.PRECONFIRM)
    def is_important_price(self, special: StoredSpecial, value: int) -> bool:
        if special.price is None:
            return False
        return special.price <= value

    @criteria_map.mapped_func("price_per_night", SpecialTypes.PRECONFIRM)
    def is_important_price_per_night(
        self, special: StoredSpecial, value: int
    ) -> bool:
        if special.price_per_night is None:
            return False
        return special.price_per_night <= value

    @criteria_map.mapped_func("price_per_point")
    def is_important_price_per_point(
        self, special: StoredSpecial, value: int
    ) -> bool:
        # In the model, only Preconfirmed reservations use the 'price_per_point'
        # attribute. For discounted points the price per point is stored in
        # 'points'.
        if special.type == SpecialTypes.PRECONFIRM:
            if special.price_per_point is None:
                return False
            return special.price_per_point <= value
        return self.is_important_price(special, value)

    @criteria_map.mapped_func("points", SpecialTypes.DISC_POINTS)
    def is_important_points(self, special: StoredSpecial, value: int) -> bool:
        if special.points is None:
            return False
        return special.points >= value

    @criteria_map.mapped_func("resorts", SpecialTypes.PRECONFIRM)
    def is_important_resort(
        self, special: StoredSpecial, resorts: list[str]
    ) -> bool:
        if special.resort is None:  # pyright: ignore[reportAttributeAccessIssue]
            return False
        return special.resort_id in resorts

    @criteria_map.mapped_func("rooms", SpecialTypes.PRECONFIRM)
    def is_important_room(
        self, special: StoredSpecial, rooms: list[str]
    ) -> bool:
        if special.room is None:  # pyright: ignore[reportAttributeAccessIssue]
            return False
        return special.room_id in rooms

    @criteria_map.mapped_func("views", SpecialTypes.PRECONFIRM)
    def is_important_view(
        self, special: StoredSpecial, views: list[str]
    ) -> bool:
        if special.view is None:  # pyright: ignore[reportAttributeAccessIssue]
            return False
        return special.view_id in views
