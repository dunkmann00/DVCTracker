class SpecialError(Exception):
    """
    Exception raised when there is an error while parsing a special.
    """

    def __init__(self, attribute, content=None):
        self.attribute = attribute
        self.content = content

    def __str__(self):
        return (
            f"Unable to parse '{self.attribute}'\nContent: '{self.content}'\n"
        )
