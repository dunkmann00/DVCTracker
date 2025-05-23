import random
import time
from datetime import datetime

import requests
from flask import current_app, json

from ..errors import SpecialError
from ..util import SpecialTypes
from .base_parser import BaseParser, special_error


class DVCRentalPreconfirmParser(BaseParser):
    def __init__(self, *args):
        super(DVCRentalPreconfirmParser, self).__init__(
            source="dvcrentalstore_preconfirms",
            source_name="DVC Rental Store",
            site_url="https://dvcrentalstore.com/confirmed-reservations/",
            data_url="https://us-east-1-renderer-read.knack.com/v1/scenes/scene_620/views/view_1064/records",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
                "X-Knack-REST-API-Key": "renderer",  # REQUIRED
                "X-Knack-Application-Id": "5b1e9f1bd250af137b419ba5",  # REQUIRED
                "x-knack-new-builder": "true",
                "X-Requested-With": "XMLHttpRequest",
            },
            params={
                "format": "both",
                "page": 1,
                "rows_per_page": current_app.config[
                    "DVCRENTALSTORE_PRECONFIRM_RPP"
                ],
                "sort_field": "field_10",
                "sort_order": "asc",
            },
        )

    def get_specials_page(self):
        # Have to override the superclass because this has to support paging
        # maybe eventually I can remove this, but for now there are too many preconfirms (> 1000)
        content = []
        total_pages = 1
        retries = 0
        print(f"Retrieving Specials from {self.source}")
        while self.params["page"] <= total_pages:
            while retries < 5:
                if retries > 0:
                    time.sleep(random.uniform(0, 2**retries))
                    print(f"Attempting Retry on Specials Request: {retries}")
                url = (
                    self.data_url
                    if self.data_url is not None
                    else self.site_url
                )
                dvc_page = requests.get(
                    url, headers=self.headers, params=self.params
                )
                if dvc_page.status_code in (500, 502, 503, 504):
                    retries += 1
                else:
                    break
            try:
                dvc_json = dvc_page.json()
            except ValueError as e:
                print(f"Error when parsing '{self.source}' response:")
                print(e)
                return None
            content.append(dvc_json)
            total_pages = dvc_json.get("total_pages", 1)
            self.params["page"] += 1
        return content

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
            parsed_special.url = f"https://dvcrentalstore.com/confirmed-reservations/#confirmed-reservations-inventory/view-reservation-details13/{parsed_special.special_id}/"
        return parsed_special

    # Now that DVCRentalStore has unique IDs in their data, we can just set
    # the special_id directly, we don't need to use the SpecialIDGenerator
    @special_error
    def get_special_id(self, special_dict):
        id = special_dict.get("id")
        if id is None:
            raise SpecialError("special_id", "id = None")
        return id

    @special_error
    def get_reservation_id(self, special_dict):
        id = special_dict.get("field_56_raw")
        if id is None:
            raise SpecialError("reservation_id", "field_56_raw = None")
        return str(id)

    @special_error
    def get_price(self, special_dict):
        price = special_dict.get("field_78_raw")
        if price is None:
            raise SpecialError("price", "field_78_raw = None")
        price = price.replace(",", "")
        return int(float(price))

    @special_error
    def get_check_in_date(self, specials_dict):
        date_str = specials_dict.get("field_10_raw", {}).get("iso_timestamp")
        if date_str is None:
            raise SpecialError("check_in", "field_10_raw = None")
        date_str = date_str.strip("Z")
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_check_out_date(self, specials_dict):
        date_str = specials_dict.get("field_11_raw", {}).get("iso_timestamp")
        if date_str is None:
            raise SpecialError("check_out", "field_11_raw = None")
        date_str = date_str.strip("Z")
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_resort(self, specials_dict):
        resort = specials_dict.get("field_57_raw", [])
        if len(resort) > 0:
            resort = resort[0].get("identifier")
        if not resort:
            raise SpecialError("resort", "field_57_raw = None")
        return resort

    @special_error
    def get_room(self, specials_dict):
        room = specials_dict.get("field_145_raw", [])
        if len(room) > 0:
            room = room[0].get("identifier")
        view = specials_dict.get("field_9_raw", [])
        if len(view) > 0:
            view = view[0].get("identifier")
        if not room:
            raise SpecialError("room", "field_145_raw = None")
        room = "Deluxe Studio" if room == "Studio" else room.replace(" ", "-")
        view = f"{view} View " if view else ""
        return f"{view}{room} Villa"

    @staticmethod
    def mention_and_check_out(parsed_special):
        if (
            parsed_special.mention_id is None
            or parsed_special.check_out is None
        ):
            return
        check_out_str = parsed_special.check_out.strftime("%m%d%y")
        return f"{parsed_special.mention_id}:{check_out_str}"

    parse_fields = {
        "price": get_price,
        "check_in": get_check_in_date,
        "check_out": get_check_out_date,
        "reservation_id": get_reservation_id,
        "special_id": get_special_id,
        "resort": get_resort,
        "room": get_room,
    }

    def process_specials_content(self, specials_content_list):
        specials_dict = {}
        for specials_content in specials_content_list:
            specials = specials_content.get("records", {})

            for special in specials:
                parsed_special = self.process_element(special)
                if parsed_special is not None:
                    key = parsed_special.special_id
                    specials_dict[key] = parsed_special

        return specials_dict
