from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config


db = SQLAlchemy()

env_label = {
    'development' : 'dev',
    'staging' : 'beta'
}

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    db.init_app(app)

    from .blueprint import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/specials')

    from .cli import update_specials_cli, reset_errors
    app.cli.add_command(update_specials_cli)
    app.cli.add_command(reset_errors)

    from .criteria import load_criteria
    load_criteria(app.config['DVC_CRITERIA'])

    return app
