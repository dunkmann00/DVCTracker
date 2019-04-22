from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

env_label = {
    'development' : 'dev',
    'staging' : 'beta'
}

def create_app():
    app = Flask(__name__)
    app.config.from_object(__name__)
    app.config.from_pyfile("../dvctracker_settings.cfg")
    app.config.from_envvar('DVC_SETTINGS', silent=True)

    db.init_app(app)

    from .blueprint import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/specials')

    from .cli import update_specials_cli, reset_errors
    app.cli.add_command(update_specials_cli)
    app.cli.add_command(reset_errors)

    from .criteria import load_criteria
    load_criteria(app.config['DVC_CRITERIA'])

    return app
