from datetime import date

from flask.json.provider import DefaultJSONProvider


class CustomJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)
