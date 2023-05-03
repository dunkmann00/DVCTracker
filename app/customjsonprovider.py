from flask.json.provider import DefaultJSONProvider
from datetime import date

class CustomJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)
