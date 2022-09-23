from flask import Flask, redirect, url_for, json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from config import config
from .customjsonencoder import CustomJSONEncoder

# This is for alembic
convention = {   #https://docs.sqlalchemy.org/en/latest/core/constraints.html#configuring-constraint-naming-conventions
  "ix": "ix_%(column_0_label)s",
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata, engine_options={"json_serializer": json.dumps})

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    app.json_encoder = CustomJSONEncoder
    app.jinja_options['trim_blocks'] = True
    app.jinja_options['lstrip_blocks'] = True

    db.init_app(app)

    if app.config['SSL_REDIRECT']:
        from flask_talisman import Talisman
        static = f"{app.config['PREFERRED_URL_SCHEME']}://{app.config['STATIC_SERVER_NAME']}"
        csp = {
            'default-src': '\'self\'',
            'img-src': ['\'self\'', 'https://cdn.jsdelivr.net', static, 'data:'],
            'script-src': ['\'self\'', 'https://cdn.jsdelivr.net', static],
            'style-src': ['\'self\'', 'https://cdn.jsdelivr.net', static]
        }
        talisman = Talisman(app, content_security_policy=csp)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    @app.route('/')
    def index():
        return redirect(url_for('main.current_specials'))

    from .cli import cli
    for command in cli.commands.values():
        app.cli.add_command(command)

    return app
