import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SEND_FILE_MAX_AGE_DEFAULT = int(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', 31536000))
    ALWAYS_STATIC_SERVER = os.getenv('ALWAYS_STATIC_SERVER', 'True') == 'True'
    STATIC_SERVER_NAME = os.getenv('STATIC_SERVER_NAME')
    STATIC_DIRECTORY = os.getenv('STATIC_DIRECTORY')
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'https')
    STATIC_DATA_PATH = os.getenv('STATIC_DATA_PATH', "static_data.toml")
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    MAILGUN_DOMAIN_NAME = os.getenv('MAILGUN_DOMAIN_NAME')
    TILL_URL = os.getenv('TILL_URL')
    TWILIO_SID = os.getenv('TWILIO_SID')
    TWILIO_TOKEN = os.getenv('TWILIO_TOKEN')
    TWILIO_MSG_SRVC = os.getenv('TWILIO_MSG_SRVC')
    DVC_CRITERIA = os.getenv('DVC_CRITERIA', 'criteria.toml')
    DVCRENTALSTORE_PRECONFIRM_RPP = int(os.getenv('DVCRENTALSTORE_PRECONFIRM_RPP', 100))
    APNS_KEY_ID = os.getenv('APNS_KEY_ID')
    APNS_TEAM_ID = os.getenv('APNS_TEAM_ID')
    APNS_AUTH_KEY = os.getenv('APNS_AUTH_KEY')
    APNS_TOPIC = os.getenv('APNS_TOPIC')
    SEND_EMAIL_ON_DEPLOY = os.getenv('SEND_EMAIL_ON_DEPLOY', 'False') == 'True'
    SSL_REDIRECT = False
    TZ = os.getenv('TZ', 'America/New_York')
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    ENV_LABEL = "dev"
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'True') == 'True'

class HerokuConfig(Config):
    SSL_REDIRECT = True if os.getenv('DYNO') else False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_port=1)

class HerokuStagingConfig(HerokuConfig):
    ENV_LABEL = "beta"

config = {
    'development': DevelopmentConfig,
    'heroku': HerokuConfig,
    'staging': HerokuStagingConfig,
    'default': DevelopmentConfig

}
