import hashlib
import random
import time
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import requests

from app.util import ProxyAttribute, SpecialTypes

from ..errors import SpecialError


class BaseParser(object):
    def __init__(
        self,
        source: str,
        source_name: str,
        site_url: str,
        data_url: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> None:
        self.source = source
        self.source_name = source_name
        self.site_url = site_url
        self.data_url = data_url
        self.headers = headers
        self.params = params
        self.current_error: SpecialError | None = None

    def new_parsed_special(self) -> "ParsedSpecial":
        """
        Creates a ParsedSpecial object with the source and url attributes set
        to the values of the parser.
        """
        return ParsedSpecial(
            source=self.source, source_name=self.source_name, url=self.site_url
        )

    def get_all_specials(
        self, local_specials: Path | None = None
    ) -> dict[str, "ParsedSpecial"]:
        """
        Gets all current specials from either the 'self.url' or the file that
        is passed into 'local_specials'. Using a html file with specials can be
        useful for development and debugging.

        This is the entry point to the parser from the rest of the app.
        The 'update-specials' CLI command calls this method to retrieve the
        ParsedSpecial dictionary for all parsers.
        """
        if local_specials is not None:
            specials_content = self.get_local_specials_page(local_specials)
        else:
            specials_content = self.get_specials_page()

        if specials_content is None:
            return {}

        specials_dict = self.process_specials_content(specials_content)

        return specials_dict

    def get_specials_page(self) -> str | None:
        """
        This retrieves the content from the webpage located at 'self.url'. A
        User-Agent is set because some sites might not respond to 'requests'.
        If the request is successful the data is returned as bytes. In
        the event of a 500, 502, 503, or 504 response error, the request is
        retried with backoff and jitter, at most 5 times. For more information
        about why that is implemented visit:
        https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
        """
        retries = 0
        dvc_page = None
        print(f"Retrieving Specials from {self.source}")
        while retries < 5:
            if retries > 0:
                time.sleep(random.uniform(0, 2**retries))
                print(f"Attempting Retry on Specials Request: {retries}")
            url = self.data_url if self.data_url is not None else self.site_url
            dvc_page = requests.get(
                url, headers=self.headers, params=self.params
            )
            if dvc_page.status_code in (500, 502, 503, 504):
                retries += 1
            else:
                break
        return dvc_page.text if dvc_page is not None else None

    def get_local_specials_page(self, filename: Path) -> str:
        """
        This retrieves the content from a file that is located on the filesystem.
        The data is returned as a str.
        """
        print(f"Retrieving specials locally from file '{filename}'")
        with open(filename, "r") as f:
            return f.read()

    def pop_current_error(self) -> SpecialError | None:
        """
        Returns 'self.current_error' and sets it to None. This is useful so the
        error can be attached to the ParsedSpecial object that it occured on,
        while also clearing the current error to get ready for the parsing of
        another attribute.
        """
        current_error = self.current_error
        self.current_error = None
        return current_error

    def process_specials_content(
        self, specials_content: str
    ) -> dict[str, "ParsedSpecial"]:
        raise NotImplementedError(
            "Subclasses must override process_specials_content()!"
        )


class ParsedSpecial(object):
    """
    A ParsedSpecial object represents the data that is on the Parser's
    website. The attributes of this object mirror that of the StoredSpecial
    object, however there are a few differences:
        1) 'raw_string' - This is stored in the event of an error, so that the
                          original text from the website can be included in an
                          error email. This is also stored so it can be used
                          by the default function for the 'special_id_generator'.
        2) 'errors' - Stores all the SpecialError objects that were created
                      during the parsing of the html. This is used in the error
                      email. This is also used to determine the value of the
                      'error' attribute.
    """

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        self.reservation_id: str | None = kwargs.pop("reservation_id", None)
        self.source: str | None = kwargs.pop("source", None)
        self.source_name: str | None = kwargs.pop("source_name", None)
        self.url: str | None = kwargs.pop("url", None)
        self.type: SpecialTypes | None = kwargs.pop("type", None)
        self.points: int | None = kwargs.pop("points", None)
        self.price: int | None = kwargs.pop("price", None)
        self.check_in: date | None = kwargs.pop("check_in", None)
        self.check_out: date | None = kwargs.pop("check_out", None)
        self.resort: ProxyAttribute | None = kwargs.pop("resort", None)
        self.room: ProxyAttribute | None = kwargs.pop("room", None)
        self.view: ProxyAttribute | None = kwargs.pop("view", None)
        self.raw_string: str | None = kwargs.pop("raw_string", None)
        self.errors: list[SpecialError] = []
        self._special_id: str | None = None

        if len(kwargs) > 0:
            raise TypeError(
                f"__init__() got an unexpected keyword argument '{kwargs.popitem()[0]}'"
            )

    @property
    def special_id(self) -> str:
        if self._special_id is not None:
            return self._special_id
        if self.raw_string is None:
            raise RuntimeError(
                "Could not get 'special_id'. The special must have a value in "
                "'raw_string' to compute special_id."
            )
        m = hashlib.sha256()
        m.update(self.raw_string.encode())
        return m.hexdigest()

    @special_id.setter
    def special_id(self, value: str) -> None:
        self._special_id = value

    @property
    def error(self) -> bool:
        return len(self.errors) > 0

    def __repr__(self) -> str:
        return f"<Parsed Special: {self.special_id}>"


def special_error(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator used when calling a BaseParser subclass method that tries to parse an
    attribute from raw text. Either returns the result successfully or None if there
    was an error. The error is caught and a resulting SpecialError object is stored
    as the current_error of the parser object
    """

    @wraps(f)
    def decorated_function(
        parser: BaseParser,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        try:
            return f(parser, *args, **kwargs)
        except SpecialError as e:
            parser.current_error = e

    return decorated_function
