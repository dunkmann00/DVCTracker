from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from collections import namedtuple
import dvctracker, locale, requests, os, sys, tomlkit


"""
TO-DO

Perhaps look at how errors are handled and try to improve that. Currently it is
deinitely lacking. Too many errors are not logged properly. Errors also cause
the whole thing to stop. It should skip the errored special and move on, but
send the message saying there is an error. It should also do the best it can to
provide the special's text.

I really like the way wtforms handle errors parsing form data. I would like to
emulate something similar to that with parsing specials

"""
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_pyfile("dvctracker_settings.cfg")
app.config.from_envvar('DVC_SETTINGS', silent=True)
db = SQLAlchemy(app)

locale.setlocale(locale.LC_ALL, '')
Range = namedtuple('Range', ['start', 'end'])

class Specials(db.Model):
    special_id = db.Column(db.String(80), primary_key=True)
    special_type = db.Column(db.String(20))
    points = db.Column(db.Integer)
    price = db.Column(db.Integer)
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date, primary_key=True)
    resort = db.Column(db.String(100))
    room = db.Column(db.String(100))


    def __repr__(self):
        return f'<Special: {self.special_id}>'

    def duration(self):
        delta = self.check_out - self.check_in
        days = delta.days
        return days

class Status(db.Model):
    status_id = db.Column(db.Integer, primary_key=True)
    healthy = db.Column(db.Boolean)

    def __repr__(self):
        return '<Healthy: ' + 'Yes' if self.healthy else 'No'

class Emails(db.Model):
    email = db.Column(db.String(80), primary_key=True)
    get_errors = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Email: {self.email}>'

class PhoneNumbers(db.Model):
    phone_number = db.Column(db.String(11), primary_key=True)

    def __repr__(self):
        return f'<Phone Number: {self.phone_number}>'

@app.route('/specials')
def current_specials():
    all_special_entries = Specials.query.order_by(Specials.check_in, Specials.check_out)
    return render_template('email_template.html', added_specials=all_special_entries)

@app.route('/specials/important')
def current_important_specials():
    all_special_entries = Specials.query.order_by(Specials.check_in, Specials.check_out)
    all_special_entries = [special for special in all_special_entries if important_special(special)]
    return render_template('email_template.html', added_specials=all_special_entries)

def send_email(email_message):
    if app.config['MAILGUN_API_KEY'] is None:
        print('No MAILGUN API Key, not sending email.')
        return
    email_addresses = [email_address.email for email_address in Emails.query.all()]
    return requests.post(
        "https://api.mailgun.net/v3/dvctracker.yourdomain.com/messages",
        auth=("api", app.config['MAILGUN_API_KEY']),
        data={"from": "DVCTracker <mailgun@dvctracker.yourdomain.com>",
              "to": email_addresses,
              "subject": "DVCTracker Updates",
              "html": email_message})

def send_error_email(email_message):
    if app.config['MAILGUN_API_KEY'] is None:
        print('No MAILGUN API Key, not sending email.')
        return
    email_addresses = [email_address.email for email_address in Emails.query.filter_by(get_errors=True).all()]
    return requests.post(
        "https://api.mailgun.net/v3/dvctracker.yourdomain.com/messages",
        auth=("api", app.config['MAILGUN_API_KEY']),
        data={"from": "DVCTracker <mailgun@dvctracker.yourdomain.com>",
              "to": email_addresses,
              "subject": "DVCTracker Error",
              "text": email_message})

def send_text_message():
    if os.environ.get("TILL_URL") is None:
        print('No TILL URL, not sending txt.')
        return
    phone_numbers = [phone_number.phone_number for phone_number in PhoneNumbers.query.all()]
    return requests.post(os.environ.get("TILL_URL"), json={
        "phone": phone_numbers,
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

        send_important_only = important_criteria.get('important_only', False)

        for special_entry in all_special_entries:
            special_entry_key = (special_entry.special_id, special_entry.check_out)
            if special_entry_key in new_specials:
                if special_entry.special_type == dvctracker.DISC_POINTS:
                    if special_entry.points != new_specials[special_entry_key][dvctracker.POINTS] or special_entry.price != new_specials[special_entry_key][dvctracker.PRICE]:
                        updated_specials.append((new_specials[special_entry_key], special_entry))
                else:
                    if special_entry.price != new_specials[special_entry_key][dvctracker.PRICE]:
                        updated_specials.append((new_specials[special_entry_key], special_entry))
                del new_specials[special_entry_key]
            else:
                removed_specials_models.append(special_entry)


        new_important_specials = False
        #Adding new Specials
        new_specials_list = []
        for new_special_key in new_specials:
            db_entry = add_special(new_specials[new_special_key])
            important = important_special(db_entry)
            if not (not important and send_important_only): #The only time it isn't added is when the special is not important and we only want to send important specials
                new_specials_list.append(db_entry)
            new_important_specials = new_important_specials or important


        if len(new_specials_list) > 1:
            new_specials_list = sorted(new_specials_list, key=lambda special: (special.check_in if special.check_in else date(2000,1,1), special.check_out))

        #Updating Old Specials
        updated_specials_tuple = []
        for special_tuple in updated_specials:
            old_price, old_points = update_special(special_tuple)
            important = important_special(special_tuple[1])
            if not (not important and send_important_only):
                updated_specials_tuple.append((special_tuple[1], old_price, old_points))
            new_important_specials = new_important_specials or important


        #Deleting Removed Specials
        for special_entry in removed_specials_models:
            remove_special(special_entry)

        #I am putting this before the render_template call because if I put it after any changes will get rolled back upon the completion of
        #the with statement because once the app context closes Flask automatically removes the database session, thus rolling back any transactions
        db.session.commit()



        if request:
            #web_message = render_template('email_template.html', added_specials=new_specials_list,updated_specials=updated_specials_tuple,removed_specials=removed_specials_models)
            web_message = render_template('email_template.html', added_specials=all_special_entries)
            return web_message
        elif len(new_specials_list) > 0 or len(updated_specials_tuple) > 0 or len(removed_specials_models) > 0:
            #This will get called when I'm using it to send emails
            with app.app_context():
                email_message = render_template('email_template.html', added_specials=new_specials_list,updated_specials=updated_specials_tuple,removed_specials=removed_specials_models)
                response = send_email(email_message)
                if response and response.status_code == requests.codes.ok:
                    print(response.text)
                else:
                    print(f'Mailgun: {response.status_code} {response.reason}')
            if new_important_specials:
                response = send_text_message()
                if response and response.status_code == requests.codes.ok:
                    print(response.text)
                else:
                    print(f'Till: {response.status_code} {response.reason}')
        else:
            print("No changes found. Nothing to update Cap'n. :-)")
        set_health(True)
    except Exception as e:
        status = Status.query.first()
        if status.healthy:
            status.healthy = False
            send_error_email(e)
            print("Error Message Sent")
            db.session.commit()




def add_special(special_dict):
    special_entry = Specials(special_id=special_dict.get(dvctracker.ID),
                             special_type=special_dict.get(dvctracker.SPECIAL_TYPE),
                             points=special_dict.get(dvctracker.POINTS),
                             price=special_dict.get(dvctracker.PRICE),
                             check_in=special_dict.get(dvctracker.CHECK_IN),
                             check_out=special_dict.get(dvctracker.CHECK_OUT),
                             resort=special_dict.get(dvctracker.RESORT),
                             room=special_dict.get(dvctracker.ROOM))
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
    if sys.platform == 'win32':
        format = format.replace('%-', '%#')
    return value.strftime(format)

@app.template_filter()
def currencyformat(value):
    return locale.currency(value, grouping=True)

@app.template_filter()
def idformat(value):
  return value[:-7]

@app.context_processor
def my_utility_processor():
    def important_special_format(special):
        return important_special(special)
    return dict(date=datetime.now, important_special_format=important_special_format)

def load_criteria(path='criteria.toml'):
    with open(path, encoding='utf-8') as f:
        content = f.read()
        return tomlkit.loads(content)

def important_special(special):
    for criteria in important_criteria.get(special.special_type, []):
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
    if special.special_type == 'preconfirm':
        check_in = special.check_in
        r1 = Range(start=check_in, end=check_out)
        r2 = Range(start=date.fromisoformat(imp_date['start'].as_string()), end=date.fromisoformat(imp_date['end'].as_string()))
        #Need to do that with the dates from the toml file because tomlkit thinks the return value of these should be a date and tries to make it
        #a toml date, which results in an error. I will look into submitting a pull request.
        #Tomlkit error info:
        #Only applies to subtracting (__sub__) Date or DateTime, the resulting object from a subtract is not the same type of object, but is a timedelta.
        #In the situation where it is a timedelta object the object should be returned as is and not passed into _new
        latest_start = max(r1.start, r2.start)
        earliest_end = min(r1.end, r2.end)
        overlap = (earliest_end - latest_start).days + 1
        return overlap > 0
    else:
        return check_out >= imp_date

def important_resort(special, resorts):
    for resort in resorts:
        if resort in special.resort:
            return True
    return False

def important_room(special, rooms):
    for room in rooms:
        if room in special.room:
            return True
    return False

important_criteria = load_criteria()

check_criteria = {
    'date': important_date,
    'length_of_stay': lambda special, value: special.duration() >= value,
    'price': lambda special, value: special.price <= value,
    'price_per_night': lambda special, value: special.price/special.duration() <= value,
    'points': lambda special, value: special.points >= value,
    'resorts': important_resort,
    'rooms': important_room
}

def set_health(healthy):
    status = Status.query.first()
    if not status:
        status = Status(0,healthy)
        db.session.add(status)
    else:
        status.healthy = healthy
    db.session.commit()

#Since I made the check-out column a primary key as well I no longer need to
#add the date on as part of the special_id. This utility function will go
#through all of the specials and remove the 6 character date that was added
#onto the end
def update_primary_keys():
    specials = Specials.query.all()
    for special in specials:
        special.special_id = idformat(special.special_id)
    db.session.commit()
