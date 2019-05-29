from ..errors import SpecialError, SpecialAttributesMissing
from functools import wraps
import requests, time, random, hashlib


class BaseParser(object):
    def __init__(self, name, source, site_url, data_url=None, headers=None, params=None):
        self.name = name
        self.source = source
        self.site_url = site_url
        self.data_url = data_url
        self.headers = headers
        self.params = params
        self.current_error = None

    def new_parsed_special(self, special_id_generator):
        """
        Creates a ParsedSpecial object with the source and url attributes set
        to the values of the parser.
        """
        return ParsedSpecial(special_id_generator, source=self.source, url=self.site_url)

    def get_all_specials(self, local_specials=None):
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

    def get_specials_page(self):
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
        print(f'Retrieving Specials from {self.name}')
        while(retries < 5):
            if retries > 0:
                time.sleep(random.uniform(0, 2**retries))
                print(f"Attempting Retry on Specials Request: {retries}")
            url = self.data_url if self.data_url is not None else self.site_url
            dvc_page = requests.get(url, headers=self.headers, params=self.params)
            if dvc_page.status_code in (500, 502, 503, 504):
                retries+=1
            else:
                break
        return dvc_page.content

    def get_local_specials_page(self,filename):
        """
        This retrieves the content from a file that is located on the filesystem.
        The data is returned as bytes.
        """
        print(f"Retrieving specials locally from file '{filename}'")
        with open(filename, 'rb') as f:
            return f.read()

    def pop_current_error(self):
        """
        Returns 'self.current_error' and sets it to None. This is useful so the
        error can be attached to the ParsedSpecial object that it occured on,
        while also clearing the current error to get ready for the parsing of
        another attribute.
        """
        current_error = self.current_error
        self.current_error = None
        return current_error

    def process_specials_content(self, specials_content):
        raise NotImplementedError('Subclasses must override process_specials_content()!')

class ParsedSpecial(object):
    """
    A ParsedSpecial object represents the data that is on the Parser's
    website. The attributes of this object mirror that of the StoredSpecial
    object, however there are a few differences:
        1) 'special_id_generator' - Only the ParsedSpecial needs to store this
                                    object, StoredSpecial will store the value
                                    that 'special_id_generator' generates for
                                    a ParsedSpecial
        2) 'raw_strings' - This is stored in the event of an error, so that the
                           original text from the website can be included in an
                           error email. This is also stored so it can be used
                           by the default function for the 'special_id_generator'.
        3) 'errors' - Stores all the SpecialError objects that were created
                      during the parsing of the html. This is used in the error
                      email. This is also used to determine the value of the
                      'error' attribute.
    """
    def __init__(self, special_id_generator, **kwargs):
        self.special_id_generator = special_id_generator
        self.mention_id = kwargs.pop('mention_id', None)
        self.source = kwargs.pop('source', None)
        self.url = kwargs.pop('url', None)
        self.type = kwargs.pop('type', None)
        self.points = kwargs.pop('points', None)
        self.price = kwargs.pop('price', None)
        self.check_in = kwargs.pop('check_in', None)
        self.check_out = kwargs.pop('check_out', None)
        self.resort = kwargs.pop('resort', None)
        self.room = kwargs.pop('room', None)
        self.raw_strings = kwargs.pop('raw_strings', None)
        self.errors = []
        self._special_id = None

        if len(kwargs) > 0:
            raise TypeError(f"__init__() got an unexpected keyword argument '{kwargs.popitem()[0]}'")

    @property
    def special_id(self):
        if self.special_id_generator is None:
            return None
        elif self._special_id is not None:
            return self._special_id

        for generator_function in self.special_id_generator.generator_functions:
            try:
                self._special_id = generator_function(self)
                return self._special_id
            except SpecialAttributesMissing:
                if generator_function.__name__ != 'default_special_id':
                    print(f"Creating special_id with '{generator_function.__name__}' failed, trying next method...")
                else:
                    print(f"Unable to generate special_id")

    @property
    def error(self):
        return len(self.errors) > 0


    def __repr__(self):
        return f'<Parsed Special: {self.special_id}>'


class SpecialIDGenerator(object):
    """
    Used to create a value for the special_id attribute of a ParsedSpecial.
    In a BaseParser subclass file, a SpecialIDGenerator should be created and
    functions that will create a 'special_id' using other fields, should be
    added to it using the decorator function 'generator_function'. Functions
    will be tried in the order that they are added in the file.
    SpecialIDGenerator already includes a default function that takes the
    'raw_strings' value, joins each string together with line endings, and
    returns the sha-256 hash. This function will be used if all of the other
    functions that are added fail.
    """
    def __init__(self):
        self.generator_functions = [self.default_special_id]

    def generator_function(self, callback):
        self.generator_functions.insert(-1, callback)
        return callback

    @staticmethod
    def default_special_id(parsed_special):
        m = hashlib.sha256()
        m.update('\n'.join(parsed_special.raw_strings).encode())
        return m.hexdigest()

def special_error(f):
    '''
    Decorator used when calling a BaseParser subclass method that tries to parse an
    attribute from raw text. Either returns the result successfully or None if there
    was an error. The error is caught and a resulting SpecialError object is stored
    as the current_error of the parser object
    '''
    @wraps(f)
    def decorated_function(parser, *args, **kwargs):
        try:
            return f(parser, *args, **kwargs)
        except SpecialError as e:
            parser.current_error = e
    return decorated_function
