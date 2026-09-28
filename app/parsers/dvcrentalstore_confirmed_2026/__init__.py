import importlib.resources as resources
from datetime import datetime
from functools import cached_property

import tomlkit
from flask import current_app, json

from ...errors import SpecialError
from ...util import ProxyAttribute, SpecialTypes
from ..base_parser import BaseParser, special_error


class DVCRentalStoreConfirmed2026(BaseParser):
    def __init__(self, *args):
        super(DVCRentalStoreConfirmed2026, self).__init__(
            source="dvcrentalstore_confirmed_2026",
            source_name="DVC Rental Store",
            site_url="https://dvcrentalstore.com/guests/reservations/",
            data_url="https://api.keyholdervacations.com/v2/dvc/rental/confirmed-reservations",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) Gecko/20100101 Firefox/153.0"
            },
        )

    @cached_property
    def parser_map(self):
        parser_map_path = (
            resources.files("app.parsers.dvcrentalstore_confirmed_2026")
            / "parser_map.toml"
        )
        content = parser_map_path.read_text(encoding="utf-8")
        data = tomlkit.loads(content)
        if not data:
            raise RuntimeError("Parser map was not loaded properly.")
        return data

    def get_specials_list(self, specials_content):
        specials_json = json.loads(specials_content)

        status = specials_json.get("statusCode", -1)

        if status != 200:
            raise RuntimeError(
                f"Could not retrieve specials successfully (Error {status})"
            )

        return specials_json["data"]

    def process_element(self, special_dict):
        """
        Parses Preconfirmed specials. Info is parsed out of a JSON dictionary.
        """
        parsed_special = self.new_parsed_special()
        parsed_special.type = SpecialTypes.PRECONFIRM
        parsed_special.raw_string = json.dumps(special_dict, indent=" " * 4)

        for field, func in self.parse_fields.items():
            setattr(parsed_special, field, func(self, special_dict))
            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())
        if parsed_special.special_id is None:
            # Try one more time to set the special_id
            parsed_special.special_id = self.mention_and_check_out(
                parsed_special
            )
        else:  # If it is set correctly, update the url to point to the new page for each preconfirm
            parsed_special.url += f"{parsed_special.special_id}/"

        return parsed_special

    def get_map_value(self, map_data, special_dict, special_key=None):
        if special_key is None:
            special_key = map_data["key"]

        special_value = special_dict[special_key]
        map_value = map_data["values"].get(special_value)

        if map_value is None:
            return None

        if not isinstance(map_value, str):
            map_value = self.get_map_value(
                map_data, special_dict, map_value["key"]
            )

        return map_value

    def get_map_field(self, field, special_dict):
        map_data = self.parser_map[field]
        value = self.get_map_value(map_data, special_dict)
        return value

    @special_error
    def get_special_id(self, special_dict):
        id = special_dict.get("id")
        if id is None:
            raise SpecialError("special_id", "id = None")
        return id

    @special_error
    def get_reservation_id(self, special_dict):
        id = special_dict.get("reservationNumber")
        if id is None:
            raise SpecialError("reservation_id", "reservationNumber = None")
        return str(id)

    @special_error
    def get_price(self, special_dict):
        price = special_dict.get("price")
        if price is None:
            raise SpecialError("price", "price = None")
        return int(float(price))

    @special_error
    def get_points(self, special_dict):
        points = special_dict.get("points")
        if points is None:
            raise SpecialError("points", "points = None")
        return int(points)

    @special_error
    def get_check_in_date(self, special_dict):
        date_str = special_dict.get("checkIn")
        if date_str is None:
            raise SpecialError("check_in", "checkIn = None")
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_check_out_date(self, special_dict):
        date_str = special_dict.get("checkOut")
        if date_str is None:
            raise SpecialError("check_out", "checkOut = None")
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_resort(self, special_dict):
        resort = self.get_map_field("resorts", special_dict)
        if resort is None:
            raise SpecialError("resort", "Resort could not be mapped.")
        return ProxyAttribute(id=resort, attr="resort")

    @special_error
    def get_room(self, special_dict):
        room = self.get_map_field("rooms", special_dict)
        if not room:
            raise SpecialError("room", "Room could not be mapped.")
        return ProxyAttribute(id=room, attr="room")

    @special_error
    def get_view(self, special_dict):
        view = self.get_map_field("views", special_dict)
        if not view:
            raise SpecialError("view", "View could not be mapped.")
        return ProxyAttribute(id=view, attr="view")

    @staticmethod
    def mention_and_check_out(parsed_special):
        if (
            parsed_special.reservation_id is None
            or parsed_special.check_out is None
        ):
            return
        check_out_str = parsed_special.check_out.strftime("%m%d%y")
        return f"{parsed_special.reservation_id}:{check_out_str}"

    parse_fields = {
        "price": get_price,
        "points": get_points,
        "check_in": get_check_in_date,
        "check_out": get_check_out_date,
        "reservation_id": get_reservation_id,
        "special_id": get_special_id,
        "resort": get_resort,
        "room": get_room,
        "view": get_view,
    }

    def process_specials_content(self, specials_content):
        specials = self.get_specials_list(specials_content)
        specials_dict = {}
        for special in specials:
            parsed_special = self.process_element(special)
            if parsed_special is not None:
                key = parsed_special.special_id
                specials_dict[key] = parsed_special
        return specials_dict
