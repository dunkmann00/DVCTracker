from collections import namedtuple
from datetime import date
import tomlkit, os

Range = namedtuple('Range', ['start', 'end'])

important_criteria = None

def load_criteria(path):
    global important_criteria
    with open(path, encoding='utf-8') as f:
        content = f.read()
        important_criteria = tomlkit.loads(content)

def important_special(special):
    for criteria in important_criteria.get(special.type, []):
        important = False
        for criterion in criteria:
            important = check_criteria[criterion](special, criteria[criterion])
            if not important:
                break
        if important:
            return True
    return False

def important_date(special, imp_date):
    check_out = special.check_out
    if check_out is None:
        return False
    if special.type == 'preconfirm':
        check_in = special.check_in
        if check_in is None:
            return False
        r1 = Range(start=check_in, end=check_out)
        r2 = Range(start=imp_date['start'], end=imp_date['end'])
        latest_start = max(r1.start, r2.start)
        earliest_end = min(r1.end, r2.end)
        overlap = (earliest_end - latest_start).days + 1
        return overlap > 0
    else:
        return check_out >= imp_date['end']

def important_length_of_stay(special, value):
    if special.duration is None:
        return False
    return special.duration >= value

def important_price(special, value):
    if special.price is None:
        return False
    return special.price <= value

def important_price_per_night(special, value):
    if special.price_per_night is None:
        return False
    return special.price_per_night <= value

def important_points(special, value):
    if special.points is None:
        return False
    return special.points >= value

def important_resort(special, resorts):
    if special.resort is None:
        return False
    return special.resort in resorts

def important_room(special, rooms):
    if special.room is None:
        return False
    return special.room in rooms

def important_view(special, views):
    if special.view is None:
        return False
    return special.view in views

def important_only():
    return important_criteria.get('important_only', False)


check_criteria = {
    'date': important_date,
    'length_of_stay': important_length_of_stay,
    'price': important_price,
    'price_per_night': important_price_per_night,
    'points': important_points,
    'resorts': important_resort,
    'rooms': important_room,
    'views': important_view
}
