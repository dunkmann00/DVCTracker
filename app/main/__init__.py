from flask import Blueprint
from datetime import datetime
from ..util import SpecialTypes
from jinja2 import is_undefined
import locale, sys

main = Blueprint('main', __name__)

from . import views

locale.setlocale(locale.LC_ALL, '')

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
    return value if value is not None and not is_undefined(value) else '??'

@main.app_context_processor
def my_utility_processor():
    return dict(date=datetime.now, SpecialTypes=SpecialTypes)
