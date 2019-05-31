from .dvcrentalstore_points import DVCRentalPointParser
from .dvcrentalstore_preconfirms import DVCRentalPreconfirmParser
from .base_parser import ParsedSpecial, SpecialIDGenerator

PARSERS = [DVCRentalPointParser, DVCRentalPreconfirmParser]
