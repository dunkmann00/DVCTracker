import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    MAILGUN_DOMAIN_NAME = os.getenv('MAILGUN_DOMAIN_NAME')
    DVC_CRITERIA = os.getenv('DVC_CRITERIA', 'criteria.toml')
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    pass

class HerokuConfig(Config):
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_port=1)

config = {
    'development': DevelopmentConfig,
    'heroku': HerokuConfig,

    'default': DevelopmentConfig

}
