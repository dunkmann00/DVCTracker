from flask import Blueprint

specials = Blueprint("specials", __name__)

from . import views
