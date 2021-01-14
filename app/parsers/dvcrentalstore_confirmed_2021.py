from flask import json, current_app
from datetime import datetime
from bs4 import BeautifulSoup
from .base_parser import BaseParser, special_error
from ..models import SpecialTypes
from ..errors import SpecialError

class DVCRentalStoreConfirmed2021(BaseParser):
    def __init__(self, *args):
        super(DVCRentalStoreConfirmed2021, self).__init__(source='dvcrentalstore_confirmed_2021',
                                                          source_name='DVC Rental Store',
                                                          site_url='https://dvcrentalstore.com/guests/reservations/',
                                                          headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'}
                                                          )

    def get_specials_list(self, specials_content):
        dvc_soup = BeautifulSoup(specials_content, 'lxml')
        all_reservations_line = dvc_soup.find(id='dvcrs-reservations-reactjs-js-before')
        reservations_tuple = all_reservations_line.string.partition("=")
        specials = []
        if reservations_tuple[2] != '':
            reservations_str = reservations_tuple[2].strip().strip(';')
            specials = json.loads(reservations_str)
        return specials

    def process_element(self, special_dict):
        """
        Parses Preconfirmed specials. Info is parsed out of a JSON dictionary.
        """
        parsed_special = self.new_parsed_special()
        parsed_special.type = SpecialTypes.preconfirm
        parsed_special.raw_string = json.dumps(special_dict, indent=' '*4)

        for field, func in self.parse_fields.items():
            setattr(parsed_special, field, func(self, special_dict))
            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())
        if parsed_special.special_id is None:
            # Try one more time to set the special_id
            parsed_special.special_id = self.mention_and_check_out(parsed_special)
        else: # If it is set correctly, update the url to point to the new page for each preconfirm
            parsed_special.url += f"{parsed_special.special_id}/"
        return parsed_special

    @special_error
    def get_special_id(self, special_dict):
        id = special_dict.get('id')
        if id is None:
            raise SpecialError('special_id', 'id = None')
        return id

    @special_error
    def get_reservation_id(self, special_dict):
        id = special_dict.get('reservation_number')
        if id is None:
            raise SpecialError('reservation_id', 'reservation_number = None')
        return str(id)

    @special_error
    def get_price(self, special_dict):
        price = special_dict.get('price')
        if price is None:
            raise SpecialError('price', 'price = None')
        return int(float(price))

    @special_error
    def get_check_in_date(self, specials_dict):
        date_str = specials_dict.get('raw_check_in')
        if date_str is None:
            raise SpecialError('check_in', 'raw_check_in = None')
        date_str = date_str.strip('Z')
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_check_out_date(self, specials_dict):
        date_str = specials_dict.get('raw_check_out')
        if date_str is None:
            raise SpecialError('check_out', 'raw_check_out = None')
        date_str = date_str.strip('Z')
        return datetime.fromisoformat(date_str).date()

    @special_error
    def get_resort(self, specials_dict):
        resort = specials_dict.get('resort')
        if resort is None:
            raise SpecialError('resort', 'resort = None')
        return resort

    @special_error
    def get_room(self, specials_dict):
        room = specials_dict.get('room_type')
        view = specials_dict.get('room_view')
        if not room:
            raise SpecialError('room', 'room_type = None')
        room = 'Deluxe Studio' if room == 'Studio' else room.replace(' ', '-')
        view = f'{view} View ' if view else ''
        return f'{view}{room} Villa'

    @staticmethod
    def mention_and_check_out(parsed_special):
        if parsed_special.reservation_id is None or parsed_special.check_out is None:
            return
        check_out_str = parsed_special.check_out.strftime("%m%d%y")
        return f'{parsed_special.reservation_id}:{check_out_str}'

    parse_fields = {'price': get_price,
                    'check_in': get_check_in_date,
                    'check_out': get_check_out_date,
                    'reservation_id': get_reservation_id,
                    'special_id': get_special_id,
                    'resort': get_resort,
                    'room': get_room}

    def process_specials_content(self, specials_content):
        specials = self.get_specials_list(specials_content)
        specials_dict = {}
        for special in specials:
            parsed_special = self.process_element(special)
            if parsed_special is not None:
                key = parsed_special.special_id
                specials_dict[key] = parsed_special
        return specials_dict
