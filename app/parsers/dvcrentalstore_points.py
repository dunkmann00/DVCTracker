from flask import json
from datetime import datetime
from .base_parser import BaseParser, SpecialIDGenerator, special_error
from ..models import SpecialTypes
from ..errors import SpecialError, SpecialAttributesMissing


special_id_generator = SpecialIDGenerator()

@special_id_generator.generator_function
def mention_and_check_out(parsed_special):
    if parsed_special.mention_id is None or parsed_special.check_out is None:
        raise SpecialAttributesMissing()
    check_out_str = parsed_special.check_out.strftime("%m%d%y")
    return f'{parsed_special.mention_id}:{check_out_str}'

@special_id_generator.generator_function
def mention(parsed_special):
    if parsed_special.mention_id is None:
        raise SpecialAttributesMissing()
    return parsed_special.mention_id

class DVCRentalPointParser(BaseParser):
    def __init__(self, *args):
        super(DVCRentalPointParser, self).__init__(name='dvcrentalstore_points',
                                                   source='DVC Rental Store',
                                                   site_url='https://dvcrentalstore.com/discounted-points-confirmed-reservations/',
                                                   data_url='https://us-east-1-renderer-read.knack.com/v1/scenes/scene_152/views/view_245/records',
                                                   headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
                                                            'X-Knack-REST-API-Key': 'renderer',                     #REQUIRED
                                                            'X-Knack-Application-Id': '5b1e9f1bd250af137b419ba5',   #REQUIRED
                                                            'x-knack-new-builder': 'true',
                                                            'X-Requested-With': 'XMLHttpRequest'},
                                                   params={'format': 'both',
                                                           'page': 1,
                                                           'rows_per_page': 100,
                                                           'sort_field': 'field_152',
                                                           'sort_order': 'asc'})

    def process_element(self, special_dict):
        """
        Parses Discounted Specials. Info is parsed out of a JSON dictionary.
        """
        parsed_special = self.new_parsed_special(special_id_generator)
        parsed_special.type = SpecialTypes.disc_points
        parsed_special.raw_string = json.dumps(special_dict, indent=' '*4)

        for field, func in self.parse_fields.items():
            setattr(parsed_special, field, func(self, special_dict))
            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())

        return parsed_special

    @special_error
    def get_special_id(self, special_dict):
        id = special_dict.get('id')
        if id is None:
            raise SpecialError('special_id', 'id = None')
        return id

    @special_error
    def get_mention_id(self, special_dict):
        id = special_dict.get('field_203_raw')
        if id is None:
            raise SpecialError('mention_id', 'field_203_raw = None')
        return id

    @special_error
    def get_points(self, special_dict):
        points = special_dict.get('field_154_raw')
        if points is None:
            raise SpecialError('points', 'field_154_raw = None')
        return points

    @special_error
    def get_price(self, special_dict):
        price = special_dict.get('field_193_raw')
        if price is None:
            raise SpecialError('price', 'field_193_raw = None')
        return int(float(price))

    @special_error
    def get_check_out_date(self, specials_dict):
        date_str = specials_dict.get('field_336_raw', {}).get('iso_timestamp')
        if date_str is None:
            raise SpecialError('check_out')
        date_str = date_str.strip('Z')
        return datetime.fromisoformat(date_str).date()

###################

    @special_error
    def get_check_in_date(self, date_str):
        date = self.get_date(date_str)
        if date is None:
            raise SpecialError('check_in', date_str)
        return date

    def get_resort(self, resort_str):
        resort = resort_str.strip('\xa0')
        resort = resort.replace('\xa0',' ')
        resort = resort.replace('\u2019',"'")
        return resort

    def get_room(self, room_str):
        room = room_str.strip('\xa0')
        room = room.replace('\xa0',' ')
        return room

    parse_fields = {'points': get_points,
                    'price': get_price,
                    'check_out': get_check_out_date,
                    'mention_id': get_mention_id,
                    'special_id': get_special_id}

    def process_specials_content(self, specials_content):
        specials = json.loads(specials_content).get('records', {})
        specials_dict = {}

        for special in specials:
            parsed_special = self.process_element(special)
            if parsed_special is not None:
                key = parsed_special.special_id
                specials_dict[key] = parsed_special

        return specials_dict
