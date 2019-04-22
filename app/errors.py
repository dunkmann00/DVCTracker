class SpecialError(Exception):
    """
    Exception raised when there is an error while parsing a special.
    """
    def __init__(self, attribute, content=None):
        self.attribute = attribute
        self.content = content

    def __str__(self):
        return (f"Unable to parse '{self.attribute}'\n"
                f"Content: '{self.content}'\n")

class SpecialAttributesMissing(Exception):
    """
    Exception raised in a 'special_id_generator' function when the function
    cannot succesfully create a 'special_id'.
    """
    pass
