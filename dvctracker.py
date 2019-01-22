import requests
from lxml import html
import re
from datetime import datetime
import sys

from flask import json

#import pdb

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



def process_element(element):
    item_dict = {}
    try:
        if 'Discounted Points' in element.xpath("div[1]")[0].text_content():
            discount_str = element.text_content()
            item_dict = parse_discount_points(discount_str)
            if ID in item_dict and CHECK_OUT in item_dict:
                key = (item_dict[ID], item_dict[CHECK_OUT])
            else:
                print("No ID for Discounted Points")
                key = None
        else:
            preconfirm_str = element.text_content()
            item_dict = parse_preconfirm(preconfirm_str)
            if ID in item_dict and CHECK_OUT in item_dict:
                key = (item_dict[ID], item_dict[CHECK_OUT])
            else:
                print("No ID for Preconfirm")
                key = None
    except:
        print(sys.exc_info()[0])
        raise Exception(element.text_content())
    return (key, item_dict)

def parse_preconfirm(special):
    item_dict = {}
    item_dict[SPECIAL_TYPE] = PRECONFIRM
    special_list = special.split("\n")
    for i, line in enumerate(special_list):
        if i == 0:
            continue
        if i == 1:
            item_dict[CHECK_IN] = clean_date(line)
        elif i == 2:
            item_dict[CHECK_OUT] = clean_date(line)
        elif i == 3:
            item_dict[RESORT] = clean_resort(line)
        elif i == 4:
            item_dict[ROOM] = clean_room(line)
            break

    price_search = False
    for line in reversed(special_list):
        if "Mention" in line:
            item_dict[ID] = get_id(line)
        elif price_search:
            price = re.search("\$*[0-9,.]+",line).group()
            item_dict[PRICE] = clean_price(price)
            break
        elif "Save" in line:
            price_search = True

    return item_dict


def parse_discount_points(special):
    item_dict = {}
    item_dict[SPECIAL_TYPE] = DISC_POINTS
    special_list = special.split("\n")

    if len(special_list) < 5:
        return {}

    for i, line in enumerate(special_list):
        if i == 0:
            continue
        if i == 1:
            item_dict[POINTS] = find_points(line)
        elif i == 2:
            item_dict[PRICE] = find_points_price(line)
        elif i == 3:
            item_dict[CHECK_OUT] = clean_date(line)
        elif i == 4:
            item_dict[ID] = get_id(line)
            break
    return item_dict




def find_price(prices_str):
    prices_list = prices_str.split("\n")
    price = None
    price_search = False
    for item in reversed(prices_list):
        if price_search:
            price = re.search("\$[0-9,.]+",item).group()
            break
        elif "Save" in item:
            price_search = True
    if not price:
        raise RuntimeError("No price found")
    return price

def find_points(points_str):
    points_str = points_str.strip('\xa0')
    points_str = points_str.replace('\xa0',' ')
    points = re.search("Points Available: ([0-9]+)", points_str).group(1)
    return int(points)

def find_points_price(price_str):
    price_str = price_str.strip('\xa0')
    price_str = price_str.replace('\xa0',' ')
    price = re.search("Price: \$*([0-9.]+)", price_str).group(1)
    return int(float(price))

def clean_price(price):
    price = price.strip('$/\xa0')
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

def get_resort(resort):
    resort = resort.strip('\xa0')
    resort = resort.replace('\xa0',' ')
    resort = resort.replace('\u2019',"'")
    resort = resort.replace('\n',' ')
    return resort


def get_id(element):
    element = element.replace('\xa0',' ')
    element_id = re.search("Special [A-Z0-9-]+",element).group()
    return element_id

def get_all_specials():
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    dvc_page = requests.get('http://dvcrentalstore.com/discounted-points-confirmed-reservations/', headers=headers)
    dvc_tree = html.fromstring(dvc_page.content)
    specials = dvc_tree.xpath("//div[@class='su-box su-box-style-glass']")
    specials_dict = {}
    #pdb.set_trace()
    try:
        for special in specials:
            key, special_dict = process_element(special)
            if key:
                specials_dict[key] = special_dict
    except Exception as e:
        raise Exception(e)

    return specials_dict

def get_all_specials_frozen():
    with open('special_dict.txt', 'r') as f:
        specials_dict = json.load(f)
    for special_key in specials_dict:
        special = specials_dict[special_key]
        special[CHECK_OUT] = datetime.strptime(special[CHECK_OUT], "%B %d, %Y").date()
        if CHECK_IN in special:
            special[CHECK_IN] = datetime.strptime(special[CHECK_IN], "%B %d, %Y").date()
    return specials_dict


def main():
    specials_dict = get_all_specials()

    for special_key in specials_dict:
        special = specials_dict[special_key]
        special[CHECK_OUT] = special[CHECK_OUT].strftime("%B %d, %Y")
        if CHECK_IN in special:
            special[CHECK_IN] = special[CHECK_IN].strftime("%B %d, %Y")
    with open('special_dict.txt', 'w') as f:
        json.dump(specials_dict,f, indent="    ")



if __name__ == '__main__':
    main()
