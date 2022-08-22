from flask import Blueprint, has_request_context, current_app, request
from datetime import datetime
from .specials import specials as specials_blueprint
from ..util import SpecialTypes
from jinja2 import is_undefined
import locale, sys

main = Blueprint('main', __name__)
main.register_blueprint(specials_blueprint, url_prefix="/specials")

from . import views

locale.setlocale(locale.LC_ALL, '')

@main.app_template_filter()
def datetimeformat(value, format="%-m/%-d/%Y"):
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

def static_url(filename):
    server_name = request.host if has_request_context() else current_app.config['EMAIL_SERVER_NAME']
    url_scheme = request.scheme if has_request_context() else current_app.config['PREFERRED_URL_SCHEME']
    urls = current_app.url_map.bind(server_name, '/', url_scheme=url_scheme)
    url = urls.build('static', {'filename': filename}, force_external=not has_request_context())
    return url

@main.app_context_processor
def my_utility_processor():
    return dict(date=datetime.now, SpecialTypes=SpecialTypes, static_url=static_url)
