from flask_migrate import Migrate, upgrade
from app import create_app, db
from app.models import StoredSpecial, Status, Email, PhoneNumber, SpecialTypes
from app.parsers import DVCRentalPointParser, ParsedSpecial
from app.cli import update_specials
import os


app = create_app(os.getenv('FLASK_CONFIG', 'default'))
migrate = Migrate(app, db, compare_type=True)

@app.shell_context_processor
def make_shell_context():
    return dict(db=db, ParsedSpecial=ParsedSpecial, StoredSpecial=StoredSpecial,
                Status=Status, Email=Email, PhoneNumber=PhoneNumber, SpecialTypes=SpecialTypes,
                DVCRentalPointParser=DVCRentalPointParser)


@app.cli.command()
def deploy():
    """Run deployment tasks."""
    #migrate database to latest revision
    print('Upgrading db schema if any changes made...')
    upgrade()

    #run an update to the specials, if the db changed we may now track more
    #data and need to update to get it
    print('Upgrading stored specials with live data...')
    update_specials((), False, False)
