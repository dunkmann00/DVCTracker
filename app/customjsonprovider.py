from datetime import date
from typing import Any

from flask.json.provider import DefaultJSONProvider


class CustomJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o: Any) -> Any:  # noqa: ANN401
        if isinstance(o, date):
            return o.isoformat()
        return DefaultJSONProvider.default(o)
