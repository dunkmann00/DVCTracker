import os

from flask_migrate import Migrate, upgrade

from app import create_app, db
from app.cli import update_specials
from app.criteria import ImportantCriteria
from app.models import (
    Category,
    CategoryModelLoader,
    Characteristic,
    CharacteristicModelLoader,
    Email,
    Phone,
    Resort,
    ResortCategory,
    Room,
    RoomCategory,
    Status,
    StoredSpecial,
    User,
    View,
    ViewCategory,
)
from app.parsers import DVCRentalPointParser, ParsedSpecial
from app.util import ContactTypes, ProxyAttribute, SpecialTypes

app = create_app(os.getenv("FLASK_CONFIG", "default"))
migrate = Migrate(app, db, compare_type=True)


@app.shell_context_processor
def make_shell_context():
    return dict(
        db=db,
        ParsedSpecial=ParsedSpecial,
        StoredSpecial=StoredSpecial,
        Characteristic=Characteristic,
        Resort=Resort,
        Room=Room,
        View=View,
        Category=Category,
        ResortCategory=ResortCategory,
        RoomCategory=RoomCategory,
        ViewCategory=ViewCategory,
        Status=Status,
        Email=Email,
        Phone=Phone,
        User=User,
        CharacteristicModelLoader=CharacteristicModelLoader,
        CategoryModelLoader=CategoryModelLoader,
        SpecialTypes=SpecialTypes,
        ContactTypes=ContactTypes,
        ProxyAttribute=ProxyAttribute,
        DVCRentalPointParser=DVCRentalPointParser,
        ImportantCriteria=ImportantCriteria,
    )


@app.cli.command()
def deploy():
    """Run deployment tasks."""
    # migrate database to latest revision
    print("Upgrading db schema if any changes made...")
    upgrade()

    print("Loading static data into db...")
    ResortCategory.insert_data_from(app.config["STATIC_DATA_PATH"])
    RoomCategory.insert_data_from(app.config["STATIC_DATA_PATH"])
    ViewCategory.insert_data_from(app.config["STATIC_DATA_PATH"])
    Resort.insert_data_from(app.config["STATIC_DATA_PATH"])
    Room.insert_data_from(app.config["STATIC_DATA_PATH"])
    View.insert_data_from(app.config["STATIC_DATA_PATH"])

    # run an update to the specials, if the db changed we may now track more
    # data and need to update to get it
    print("Upgrading stored specials with live data...")
    update_specials((), app.config["SEND_EMAIL_ON_DEPLOY"], False)
