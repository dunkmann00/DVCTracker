import requests
from lxml import html
import re
from datetime import datetime

import simplejson as json

#import pdb

SPECIAL_TYPE = u"special_type"
DISC_POINTS = u"disc_points"
PRECONFIRM = u"preconfirm"

POINTS = u"points"
PRICE = u"price"
CHECK_IN = u"check_in"
CHECK_OUT = u"check_out"
RESORT = u"resort"
ID = u"id"


def process_element(element):
    item_dict = {}
    if element.xpath("div[1]")[0].text:
        item_dict[SPECIAL_TYPE] = DISC_POINTS
        item_dict[POINTS] = int(element.xpath("div[2]/p/strong[1]/span[2]")[0].text)
        item_dict[PRICE] = clean_price(element.xpath("div[2]/p/strong[2]/span")[0].text)
        item_dict[CHECK_OUT] = clean_date(element.xpath("div[2]/p/strong[3]/span")[0].text)
        key = get_id(element.xpath("div[2]/p/strong[4]/span[2]")[0], item_dict[CHECK_OUT])
        item_dict[ID] = key
    else:
        item_dict[SPECIAL_TYPE] = PRECONFIRM
        item_dict[CHECK_IN] = clean_date(element.xpath("div[2]/p[1]/strong[1]")[0].text)
        item_dict[CHECK_OUT] = clean_date(element.xpath("div[2]/p[1]/strong[2]")[0].text)
        item_dict[RESORT] = get_resort(element.xpath("div[2]/p[2]")[0])
        item_dict[PRICE] = clean_price(element.xpath("div[2]/p[3]/strong[2]/span")[0].text)
        key = get_id(element.xpath("div[2]/p[4]/strong[2]/span/b")[0], item_dict[CHECK_OUT])
        item_dict[ID] = key

    return (key, item_dict)

def clean_price(price):
    price = price.strip('$/')
    price = price.replace(',','')
    return int(float(price))

def clean_date(date):
    date = date.replace(u'\xa0',u' ')
    parsed_date = re.search('(?:January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{1,2}, [0-9]{4}', date)
    return datetime.strptime(parsed_date.group(), "%B %d, %Y").date()

def get_resort(element):
    resort = element.xpath("strong[1]")[0].text + u" " + element.xpath("strong[2]")[0].text
    resort = resort.replace(u'\xa0',u' ')
    resort = resort.replace(u'\u2019',"'")
    return resort

def get_id(element, date):
    if(len(element.getchildren()) > 0):
        element_id = element.text + element[0].text
    else:
        element_id = element.text
    element_id = element_id.replace(u'\xa0',u' ')
    element_id = element_id.strip(u'\u201c\u201d') + u' ' + date.strftime("%m%d%y")
    return element_id

def get_all_specials():
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    dvc_page = requests.get('http://dvcrentalstore.com/discounted-points-confirmed-reservations/', headers=headers)
    dvc_tree = html.fromstring(dvc_page.content)
    #specials = dvc_tree.xpath("//*[@id='main-content']/div[1]/div/article/div[2]/div[2]/div[@class='su-box su-box-style-glass]")
    specials = dvc_tree.xpath("//div[@class='su-box su-box-style-glass']")
    specials_dict = {}
    #pdb.set_trace()
    for special in specials:
        key, special_dict = process_element(special)
        specials_dict[key] = special_dict

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
