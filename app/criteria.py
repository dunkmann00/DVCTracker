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
        return check_out >= imp_date

def important_resort(special, resorts):
    if special.resort is None:
        return False
    for resort in resorts:
        if resort in special.resort:
            return True
    return False

def important_room(special, rooms):
    if special.room is None:
        return False
    for room in rooms:
        if room in special.room:
            return True
    return False

def important_only():
    return important_criteria.get('important_only', False)


check_criteria = {
    'date': important_date,
    'length_of_stay': lambda special, value: special.duration >= value if special.duration is not None else False,
    'price': lambda special, value: special.price <= value if special.price is not None else False,
    'price_per_night': lambda special, value: special.price_per_night <= value if special.price_per_night is not None else False,
    'points': lambda special, value: special.points >= value if special.points is not None else False,
    'resorts': important_resort,
    'rooms': important_room
}
