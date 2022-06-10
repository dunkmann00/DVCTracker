from flask import Flask, redirect, url_for
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

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint, url_prefix='/specials')

    from .notifications import notifications as notifications_blueprint
    app.register_blueprint(notifications_blueprint)

    @app.route('/')
    def index():
        return redirect(url_for('main.current_specials'))

    from .cli import (
        update_specials_cli,
        reset_errors,
        store_specials_data,
        encode_auth_key,
        make_new_user
    )
    app.cli.add_command(update_specials_cli)
    app.cli.add_command(reset_errors)
    app.cli.add_command(store_specials_data)
    app.cli.add_command(encode_auth_key)
    app.cli.add_command(make_new_user)

    from .criteria import load_criteria
    load_criteria(app.config['DVC_CRITERIA'])

    return app
