from flask import Flask, json, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from collections import namedtuple
import dvctracker
import locale
import requests
import os

#import pdb

app = Flask(__name__)
app.config.from_object(__name__)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/dvcspecials'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

locale.setlocale(locale.LC_ALL, '')
Range = namedtuple('Range', ['start', 'end'])

class Specials(db.Model):
    special_id = db.Column(db.String(80), primary_key=True)
    special_type = db.Column(db.String(20))
    points = db.Column(db.Integer)
    price = db.Column(db.Integer)
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date)
    resort = db.Column(db.String(100))



    def __init__(self, special_id, special_type, points, price, check_in, check_out, resort):
        self.special_id = special_id
        self.special_type = special_type
        self.points = points
        self.price = price
        self.check_in = check_in
        self.check_out = check_out
        self.resort = resort

    def __repr__(self):
        return '<Special: %r>' % self.special_id

class Status(db.Model):
    status_id = db.Column(db.Integer, primary_key=True)
    healthy = db.Column(db.Boolean)

    def __init__(self, status_id, healthy):
        self.status_id = status_id
        self.healthy = healthy

    def __repr__(self):
        return '<Healthy: ' + 'Yes' if self.healthy else 'No'

#@app.route('/')
def hello_world():
    new_specials = dvctracker.get_all_specials()
    return json.jsonify(new_specials)

def send_email(email_message):
    return requests.post(
        "https://api.mailgun.net/v3/dvctracker.yourdomain.com/messages",
        auth=("api", os.environ['MAILGUN_API_KEY']),
        data={"from": "DVCTracker <mailgun@dvctracker.yourdomain.com>",
              "to": ["han@gmail.com", "lando@gmail.com", "chewy@gmail.com", "leia@gmail.com"],
              "subject": "DVCTracker Updates",
              "html": email_message})

def send_error_email(email_message):
    return requests.post(
        "https://api.mailgun.net/v3/dvctracker.yourdomain.com/messages",
        auth=("api", os.environ['MAILGUN_API_KEY']),
        data={"from": "DVCTracker <mailgun@dvctracker.yourdomain.com>",
              "to": ["han@gmail.com", "lando@gmail.com"],
              "subject": "DVCTracker Error",
              "text": email_message})

def send_text_message():
    return requests.post(os.environ.get("TILL_URL"), json={
        "phone": ["***REMOVED***", "***REMOVED***"],
        "text": "Hey this is DVCTracker!\nA special you are interested in was either just added or updated. Check your emails for more info!"
    })

#@app.route('/show-specials')
@app.cli.command()
def update_specials():
    try:
        new_specials = dvctracker.get_all_specials()
        #new_specials = dvctracker.get_all_specials_frozen()
        all_special_entries = Specials.query.order_by(Specials.check_in, Specials.check_out)
        updated_specials = []
        removed_specials_models = []

        for special_entry in all_special_entries:
            if special_entry.special_id in new_specials:
                if special_entry.special_type == dvctracker.DISC_POINTS:
                    if special_entry.points != new_specials[special_entry.special_id][dvctracker.POINTS] or special_entry.price != new_specials[special_entry.special_id][dvctracker.PRICE]:
                        updated_specials.append((new_specials[special_entry.special_id], special_entry))
                else:
                    if special_entry.price != new_specials[special_entry.special_id][dvctracker.PRICE]:
                        updated_specials.append((new_specials[special_entry.special_id], special_entry))
                del new_specials[special_entry.special_id]
            else:
                removed_specials_models.append(special_entry)


        new_important_specials = False
        #Adding new Specials
        new_specials_list = []
        for new_special_key in new_specials:
            db_entry = add_special(new_specials[new_special_key])
            new_specials_list.append(db_entry)
            if not new_important_specials and db_entry.special_type == dvctracker.PRECONFIRM: #this will change to preconfirm when ready to use
                new_important_specials = important_special(db_entry.check_out, db_entry.check_in)

        if len(new_specials_list) > 1:
            new_specials_list = sorted(new_specials_list, key=lambda special: (special.check_in if special.check_in else date(2000,1,1), special.check_out))

        #Updating Old Specials
        updated_specials_tuple = []
        for special_tuple in updated_specials:
            old_price, old_points = update_special(special_tuple)
            updated_specials_tuple.append((special_tuple[1], old_price, old_points))
            if not new_important_specials and special_tuple[1].special_type == dvctracker.PRECONFIRM: #this will change to preconfirm when ready to use
                new_important_specials = important_special(special_tuple[1].check_out, special_tuple[1].check_in)

        #Deleting Removed Specials
        for special_entry in removed_specials_models:
            remove_special(special_entry)

        #I am putting this before the render_template call because if I put it after any changes will get rolled back upon the completion of
        #the with statement because once the app context closes Flask automatically removes the database session, thus rolling back any transactions
        db.session.commit()



        if request:
            email_message = render_template('email_template.html', added_specials=new_specials_list,updated_specials=updated_specials_tuple,removed_specials=removed_specials_models)
            return email_message
        elif len(new_specials_list) > 0 or len(updated_specials_tuple) > 0 or len(removed_specials_models) > 0:
            #This will get called when I'm using it to send emails
            with app.app_context():
                email_message = render_template('email_template.html', added_specials=new_specials_list,updated_specials=updated_specials_tuple,removed_specials=removed_specials_models)
                response = send_email(email_message)
                if response.status_code == requests.codes.ok:
                    print response.text
                else:
                    print str(response.status_code) + ' ' + response.reason
            if new_important_specials:
                send_text_message()
        else:
            print "No changes found. Nothing to update Cap'n. :-)"
        set_health(True)
    except Exception as e:
        status = Status.query.first()
        if status.healthy:
            status.healthy = False
            #send_error_email(e)
            print "Error Message Sent"
            db.session.commit()




def add_special(special_dict):
    special_entry = Specials(special_dict.get(dvctracker.ID), special_dict.get(dvctracker.SPECIAL_TYPE), special_dict.get(dvctracker.POINTS), special_dict.get(dvctracker.PRICE), special_dict.get(dvctracker.CHECK_IN), special_dict.get(dvctracker.CHECK_OUT), special_dict.get(dvctracker.RESORT))
    db.session.add(special_entry)
    return special_entry

def update_special(special_tuple):
    special_entry, db_entry = special_tuple
    old_price = None
    old_points = None
    if db_entry.price != special_entry[dvctracker.PRICE]:
        old_price = db_entry.price
        db_entry.price = special_entry[dvctracker.PRICE]
    if db_entry.special_type == dvctracker.DISC_POINTS and db_entry.points != special_entry[dvctracker.POINTS]:
        old_points = db_entry.points
        db_entry.points = special_entry[dvctracker.POINTS]
    return (old_price, old_points)

def remove_special(db_entry):
    db.session.delete(db_entry)

@app.template_filter()
def datetimeformat(value, format="%B %-d, %Y"):
    return value.strftime(format)

@app.template_filter()
def currencyformat(value):
    return locale.currency(value, grouping=True)

@app.template_filter()
def idformat(value):
    return value[:-7]

@app.context_processor
def my_utility_processor():
    def important_special_format(check_out, check_in=None):
        return important_special(check_out, check_in)
    return dict(date=datetime.now, important_special_format=important_special_format)

def important_special(check_out, check_in=None):
    important = False
    if check_in:
        r1 = Range(start=check_in, end=check_out)
        r2 = Range(start=date(2017, 12, 7), end=date(2017, 12, 13))
        latest_start = max(r1.start, r2.start)
        earliest_end = min(r1.end, r2.end)
        overlap = (earliest_end - latest_start).days + 1
        important = True if overlap > 0 else False
    else:
        important = True if check_out > date(2017, 12, 13) else False
    return important


def set_health(healthy):
    status = Status.query.first()
    if not status:
        status = Status(0,healthy)
        db.session.add(status)
    else:
        status.healthy = healthy
    db.session.commit()


#No longer necessary because I am using HTML with templating
"""
def render_disc_point_message(db_entry):
    return "Points Available: {0}\nPrice: {1}/Point\nCheck-Out no later than: {2}\nMention ID: {3}\n".format(db_entry.points, locale.currency(db_entry.price, grouping=True), db_entry.check_out.strftime("%B %d, %Y"), db_entry.special_id[:-7])

def render_preconfirm_message(db_entry):
    return "Check-In: {0}\nCheck-Out: {1}\nResort: {2}\nPrice: {3}\nMention ID: {4}\n".format(db_entry.check_in.strftime("%B %d, %Y"), db_entry.check_out.strftime("%B %d, %Y"),db_entry.resort, locale.currency(db_entry.price, grouping=True), db_entry.special_id[:-7])
"""

#This function was more for just getting it setup initially. Now I should always use update_specials()
"""
def load_all_specials():
    #new_specials = dvctracker.get_all_specials()
    new_specials = dvctracker.get_all_specials_frozen()
    for special_key in new_specials:
        special = new_specials[special_key]
        db_entry = Specials.query.get(special_key)
        if db_entry is not None:
            db_entry.price = special.get(dvctracker.PRICE)
        else:
            special_entry = Specials(special.get(dvctracker.ID), special.get(dvctracker.SPECIAL_TYPE), special.get(dvctracker.POINTS), special.get(dvctracker.PRICE), special.get(dvctracker.CHECK_IN), special.get(dvctracker.CHECK_OUT), special.get(dvctracker.RESORT))
            db.session.add(special_entry)

    db.session.commit()
"""
