from .dvcrentalstore_points import DVCRentalPointParser
from .dvcrentalstore_preconfirms import DVCRentalPreconfirmParser
from .dvcrentalstore_confirmed_2021 import DVCRentalStoreConfirmed2021
from .base_parser import ParsedSpecial

PARSERS = [DVCRentalStoreConfirmed2021]
