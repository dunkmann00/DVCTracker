from datetime import datetime
from bs4 import BeautifulSoup
from .base_parser import BaseParser, ParsedSpecial, SpecialIDGenerator, special_error
from ..models import SpecialTypes
from ..errors import SpecialError, SpecialAttributesMissing
import re


special_id_generator = SpecialIDGenerator()

@special_id_generator.generator_function
def mention_and_check_out(parsed_special):
    if parsed_special.mention_id is None or parsed_special.check_out is None:
        raise SpecialAttributesMissing()
    check_out_str = parsed_special.check_out.strftime("%m%d%y")
    return f'{parsed_special.mention_id}:{check_out_str}'

@special_id_generator.generator_function
def mention_and_check_in(parsed_special):
    if parsed_special.mention_id is None or parsed_special.check_in is None:
        raise SpecialAttributesMissing()
    check_in_str = parsed_special.check_in.strftime("%m%d%y")
    return f'{parsed_special.mention_id}:{check_in_str}'

@special_id_generator.generator_function
def mention(parsed_special):
    if parsed_special.mention_id is None:
        raise SpecialAttributesMissing()
    return parsed_special.mention_id

class DVCRentalPointParser(BaseParser):
    def __init__(self, *args):
        super(DVCRentalParser, self).__init__(name='DVC Rental Store',
                                              url='https://dvcrentalstore.com/discounted-points-confirmed-reservations/')

    def process_element(self, special_soup):
        special_soup = self.strain_soup(special_soup)
        special_list = list(special_soup.stripped_strings)

        if 'Discounted Points' in special_list[0]:
            parsed_special = self.parse_discount_points(special_list)
        else:
            parsed_special = self.parse_preconfirm(special_list)

        return parsed_special

    def strain_soup(self, soup):
        """
        Removes tags that break up lines. Now the resulting lines parsed from
        BeautifulSoup will be the true lines that are rendered in the browser.
        """
        for element in soup.find_all(['strong', 'b', 'i', 'span', 'del', 'a']):
            element.unwrap()
        new_soup = BeautifulSoup(str(soup), 'lxml')
        return new_soup

    def parse_preconfirm(self, special_list):
        """
        Parses Preconfirmed specials. The first set of info is parsed by
        iterating and parsing specific lines. The next set is parsed by
        iterating backwards and looking for lines where a specific word is
        located.
        """
        parsed_special = self.new_parsed_special(special_id_generator)
        parsed_special.type = SpecialTypes.preconfirm
        parsed_special.raw_strings = special_list

        for i, line in enumerate(special_list):
            if i == 0:
                continue
            if i == 5:
                break

            if i == 1:
                parsed_special.check_in = self.get_check_in_date(line)
            elif i == 2:
                parsed_special.check_out = self.get_check_out_date(line)
            elif i == 3:
                parsed_special.resort = self.get_resort(line)
            elif i == 4:
                parsed_special.room = self.get_room(line)

            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())

        found_mention = False
        found_price = False
        complete = False
        for line in reversed(special_list):
            if complete:
                break

            if "Mention" in line:
                found_mention = True
                parsed_special.mention_id = self.get_mention_id(line)
            elif found_price:
                parsed_special.price = self.get_price(line)
                complete = True
            elif "Save" in line:
                found_price = True

            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())

        #Need this because no errors will be thrown if we don't find the lines
        if not found_mention:
            parsed_special.errors.append(SpecialError('mention_id'))
        if not found_price:
            parsed_special.errors.append(SpecialError('price'))

        return parsed_special


    def parse_discount_points(self, special_list):
        """
        Parses Discounted Specials. All info is parsed by iterating and
        parsing specific lines.
        """
        parsed_special = self.new_parsed_special(special_id_generator)
        parsed_special.type = SpecialTypes.disc_points
        parsed_special.raw_strings = special_list
        #special_list = [line for line in special.split("\n") if line is not '']

        if len(special_list) < 5:
            if "None" in special_list[-1]:
                return None

        for i, line in enumerate(special_list):
            if i == 0:
                continue
            if i == 5:
                break

            if i == 1:
                parsed_special.points = self.get_points(line)
            elif i == 2:
                parsed_special.price = self.get_price(line)
            elif i == 3:
                parsed_special.check_out = self.get_check_out_date(line)
            elif i == 4:
                parsed_special.mention_id = self.get_mention_id(line)

            if self.current_error is not None:
                parsed_special.errors.append(self.pop_current_error())

        return parsed_special

    @special_error
    def get_mention_id(self, id_str):
        match = re.search("Special\s*([A-Z0-9-]+)",id_str)
        if match is None:
            raise SpecialError('mention_id', id_str)
        id = match.group(1)
        return id

    @special_error
    def get_points(self, points_str):
        points_str = points_str.strip('\xa0')
        points_str = points_str.replace('\xa0',' ')
        match = re.search("Points Available: ([0-9]+)", points_str)
        if match is None:
            raise SpecialError('points', points_str)
        points = match.group(1)
        return int(points)

    @special_error
    def get_price(self, price_str):
        """
        This regex looks for a space followed by the dollar sign, but it is okay
        if the dollar sign isn't there, then looks for a variable amount of numbers,
        a potential comma, followed by a period. There doesn't have to be a period.
        Then after the period there has to be either 0, 1, or 2 zeros. There
        should be 2 but since it won't actually effect the parsing I'll accept if
        there is a typo and only 0 or 1 is there. Then we look for the text
        '/Points', but this doesn't have to be there. We make sure this matches
        the end of the line so weird things won't happen if a random character
        is in the middle and the regex stops short thinking its complete.
        Making sure its the end of the line should make it less suceptable
        to that.
        """
        match = re.search("\s\$?([0-9,]+)\.?[0-9]{0,2}(/Point)?$",price_str)
        if match is None:
            raise SpecialError('price', price_str)
        price = match.group(1)
        price = price.replace(',','')
        return int(price)

    @special_error
    def get_check_in_date(self, date_str):
        date = self.get_date(date_str)
        if date is None:
            raise SpecialError('check_in', date_str)
        return date

    @special_error
    def get_check_out_date(self, date_str):
        date = self.get_date(date_str)
        if date is None:
            raise SpecialError('check_out', date_str)
        return date

    def get_date(self, date_str): #Think about using difflib to try and correct misspellings...
        date = date_str.strip('\xa0')
        date = date.replace('\xa0',' ')
        parsed_date = re.search('(January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{1,2}, [0-9]{4}', date)
        return datetime.strptime(parsed_date.group(), "%B %d, %Y").date() if parsed_date else None

    def get_resort(self, resort_str):
        resort = resort_str.strip('\xa0')
        resort = resort.replace('\xa0',' ')
        resort = resort.replace('\u2019',"'")
        return resort

    def get_room(self, room_str):
        room = room_str.strip('\xa0')
        room = room.replace('\xa0',' ')
        return room

    def process_specials_content(self, specials_content):
        dvc_soup = BeautifulSoup(specials_content, 'lxml')
        specials = dvc_soup.find_all('table', class_='wp-block-advgb-table advgb-table-frontend')
        specials_dict = {}

        for special in specials:
            parsed_special = self.process_element(special)
            if parsed_special is not None:
                key = parsed_special.special_id
                specials_dict[key] = parsed_special

        return specials_dict
