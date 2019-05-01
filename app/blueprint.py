from flask import Blueprint, render_template, current_app, g
from datetime import datetime
from . import env_label
from .models import StoredSpecial as Special
from .criteria import important_special
import locale, sys

main = Blueprint('main', __name__)
locale.setlocale(locale.LC_ALL, '')

@main.route('/')
def current_specials():
    all_stored_specials = Special.query.order_by(Special.check_in, Special.check_out).all()
    return render_template('email_template.html',
                           specials_group=(('All', all_stored_specials),),
                           env_label=env_label.get(current_app.env))

@main.route('/important')
def current_important_specials():
    all_stored_specials = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [special for special in all_stored_specials if important_special(special)]
    return render_template('email_template.html',
                           specials_group=(('Important', all_stored_specials),),
                           env_label=env_label.get(current_app.env))

@main.route('/errors')
def current_error_specials():
    all_stored_specials = Special.query.filter_by(error=True).order_by(Special.check_in, Special.check_out).all()
    return render_template('email_template.html',
                           specials_group=(('Errors', all_stored_specials),),
                           env_label=env_label.get(current_app.env))


@main.app_template_filter()
def datetimeformat(value, format="%B %-d, %Y"):
    if not value:    #using 'not' rather than 'is None' so that when a Jinja2
        return value  #Undefined value is passed in we will also exit
    if sys.platform == 'win32':
        format = format.replace('%-', '%#')
    return value.strftime(format)

@main.app_template_filter()
def currencyformat(value):
    return locale.currency(value, grouping=True) if value else value

@main.app_template_filter()
def nullable(value):
    return value if value is not None else '??'

@main.app_context_processor
def my_utility_processor():
    return dict(date=datetime.now, important_special_format=important_special)
