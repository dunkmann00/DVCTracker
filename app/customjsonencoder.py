from flask.json import JSONEncoder
from datetime import date

class CustomJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, date):
            return o.isoformat()
        return JSONEncoder.default(self,o)
