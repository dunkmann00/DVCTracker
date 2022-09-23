from flask import Blueprint, has_request_context, current_app, request
from werkzeug.urls import url_quote
from datetime import datetime
from dateutil import tz
from .specials import specials as specials_blueprint
from .user import user as user_blueprint
from ..models import Status
from ..util import SpecialTypes
from jinja2 import is_undefined
import locale, sys

main = Blueprint('main', __name__)
main.register_blueprint(specials_blueprint, url_prefix="/specials")
main.register_blueprint(user_blueprint, url_prefix="/user")

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
def convert_from_utc(value, tzinfo=None):
    utc_value = value.replace(tzinfo=tz.tzutc())
    return utc_value.astimezone(tz.gettz(tzinfo or current_app.config['TZ']))

@main.app_template_filter()
def currencyformat(value):
    return locale.currency(value, grouping=True) if value else value

@main.app_template_filter()
def nullable(value):
    return value if value is not None and not is_undefined(value) else '??'

def static_url(filename, _anchor=None, **kwargs):
    use_static_server = current_app.config['ALWAYS_STATIC_SERVER'] or not has_request_context()
    if use_static_server and not current_app.config['STATIC_SERVER_NAME']:
        raise RuntimeError("Building static url requires 'STATIC_SERVER_NAME' not be none.")
    server_name = current_app.config['STATIC_SERVER_NAME'] if use_static_server else request.host
    script_name = current_app.config['STATIC_DIRECTORY'] if use_static_server else '/'
    url_scheme = current_app.config['PREFERRED_URL_SCHEME'] if use_static_server else request.scheme
    urls = current_app.url_map.bind(server_name, script_name=script_name, url_scheme=url_scheme)
    kwargs['filename'] = filename
    url = urls.build('static', kwargs, force_external=use_static_server)
    if _anchor is not None:
        url = f"{url}#{url_quote(_anchor)}"
    return url

@main.app_context_processor
def my_utility_processor():
    return dict(status=Status.default, SpecialTypes=SpecialTypes, static_url=static_url)
