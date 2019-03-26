import requests
from lxml import html
import re
from datetime import datetime
import sys
import time
import random


SPECIAL_TYPE = "special_type"
DISC_POINTS = "disc_points"
PRECONFIRM = "preconfirm"

POINTS = "points"
PRICE = "price"
CHECK_IN = "check_in"
CHECK_OUT = "check_out"
RESORT = "resort"
ROOM = "room"
ID = "id"

class SpecialError(Exception):
    """
    Exception raised when there is an error while parsing a special.
    """
    def __init__(self, attribute, special_text):
        self.attribute = attribute
        self.special_text = special_text

    def __str__(self):
        return f"Error caused by: {self.attribute}\n\n{self.special_text}"

def process_element(element):
    item_dict = {}
    try:
        special_heading = element.xpath("div[1]")[0].text_content()
    except:
        raise SpecialError(f"Heading {sys.exc_info()[0]}", element.text_content())

    if 'Discounted Points' in special_heading:
        discount_str = element.text_content()
        item_dict = parse_discount_points(discount_str)
    else:
        preconfirm_str = element.text_content()
        item_dict = parse_preconfirm(preconfirm_str)

    return item_dict

def parse_preconfirm(special):
    item_dict = {}
    item_dict[SPECIAL_TYPE] = PRECONFIRM
    special_list = [line for line in special.split("\n") if line is not '']
    cur_attribute = ""
    try:
        for i, line in enumerate(special_list):
            if i == 0:
                continue
            if i == 1:
                cur_attribute = CHECK_IN
                item_dict[cur_attribute] = clean_date(line)
            elif i == 2:
                cur_attribute = CHECK_OUT
                item_dict[cur_attribute] = clean_date(line)
            elif i == 3:
                cur_attribute = RESORT
                item_dict[cur_attribute] = clean_resort(line)
            elif i == 4:
                cur_attribute = ROOM
                item_dict[cur_attribute] = clean_room(line)
                break

        price_search = False
        for line in reversed(special_list):
            if "Mention" in line:
                cur_attribute = ID
                item_dict[cur_attribute] = get_id(line)
            elif price_search:
                cur_attribute = PRICE
                item_dict[cur_attribute] = get_price(line)
                break
            elif "Save" in line:
                price_search = True
    except:
        raise SpecialError(cur_attribute, special)

    return item_dict


def parse_discount_points(special):
    item_dict = {}
    item_dict[SPECIAL_TYPE] = DISC_POINTS
    special_list = [line for line in special.split("\n") if line is not '']

    if len(special_list) < 5:
        if "None" in special_list[-1]:
            return None
        else:
            raise SpecialError("Incorrect Line Count", special)

    cur_attribute = ""
    try:
        for i, line in enumerate(special_list):
            if i == 0:
                continue
            if i == 1:
                cur_attribute = POINTS
                item_dict[cur_attribute] = find_points(line)
            elif i == 2:
                cur_attribute = PRICE
                item_dict[cur_attribute] = get_price(line)
            elif i == 3:
                cur_attribute = CHECK_OUT
                item_dict[cur_attribute] = clean_date(line)
            elif i == 4:
                cur_attribute = ID
                item_dict[cur_attribute] = get_id(line)
                break
    except:
        raise SpecialError(cur_attribute, special)

    return item_dict


def find_points(points_str):
    points_str = points_str.strip('\xa0')
    points_str = points_str.replace('\xa0',' ')
    points = re.search("Points Available: ([0-9]+)", points_str).group(1)
    return int(points)

def get_price(price_str):
    #This regex looks for a space followed by the dollar sign, but it is okay
    #if the dollar sign isn't there, then looks for a variable amount of numbers
    #followed by a period. There must be a period. Then after the
    #period there has to be either 1 or 2 zeros. There should be 2
    #but since it won't actually effect the parsing I'll accept if
    #there is a typo and only 1 is there
    price_str = price_str.strip('\xa0')
    price_str = price_str.replace('\xa0',' ')
    price = re.search(" \$?[0-9,]+\.[0-9]{1,2}",price_str).group()
    return clean_price(price)

def clean_price(price):
    price = price.strip(' $/\xa0')
    price = price.replace(',','')
    return int(float(price))

def clean_date(date):
    date = date.strip('\xa0')
    date = date.replace('\xa0',' ')
    parsed_date = re.search('(?:January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{1,2}, [0-9]{4}', date)
    return datetime.strptime(parsed_date.group(), "%B %d, %Y").date()

def clean_resort(resort):
    resort = resort.strip('\xa0')
    resort = resort.replace('\xa0',' ')
    resort = resort.replace('\u2019',"'")
    return resort

def clean_room(room):
    room = room.strip('\xa0')
    room = room.replace('\xa0',' ')
    return room

def get_id(element):
    element = element.replace('\xa0',' ')
    element_id = re.search("Special [A-Z0-9-]+",element).group()
    return element_id

def get_specials_page(): #Backoff with jitter - https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    retries = 0
    while(retries < 5):
        if retries > 0:
            time.sleep(random.uniform(0, 2**retries))
            print(f"Attempting Retry on Specials Request: {retries}")
        dvc_page = requests.get('https://dvcrentalstore.com/discounted-points-confirmed-reservations/', headers=headers)
        if dvc_page.status_code in (500, 502, 503, 504):
            retries+=1
        else:
            break
    return dvc_page.content

def get_local_specials_page():
    with open('DVC_local.html', 'rb') as f:
        return f.read()

def get_all_specials():
    specials_content = get_specials_page()
    #specials_content = get_local_specials_page()
    dvc_tree = html.fromstring(specials_content)
    specials = dvc_tree.xpath("//div[@class='su-box su-box-style-glass']")
    specials_dict = {}
    errors = []

    for special in specials:
        try:
            special_dict = process_element(special)
            if special_dict is not None:
                key = (special_dict[ID], special_dict[CHECK_OUT])
                specials_dict[key] = special_dict
        except SpecialError as err:
            errors.append(err)
        except Exception as e:
            errors.append(SpecialError(f"{type(e)} - {e}", special.text_content()))

    return (specials_dict, errors)
