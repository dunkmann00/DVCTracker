import phonenumbers
from wtforms.validators import StopValidation, ValidationError


class RequiredWhen:
    # a validator which makes a field required when
    # a supplied function returns True

    def __init__(self, check_func, strip_whitespace=True, message=None):
        self.check_func = check_func
        self.message = message
        if strip_whitespace:
            self.string_check = lambda s: s.strip()
        else:
            self.string_check = lambda s: s

        self.field_flags = {"optional": True}

    def __call__(self, form, field):
        if self.check_func(field, form):
            setattr(field.flags, "required", True)

            # This is from InputRequired
            if field.raw_data and field.raw_data[0]:
                return

            if self.message is None:
                message = field.gettext("This field is required.")
            else:
                message = self.message

            field.errors[:] = []
            raise StopValidation(message)
        else:
            # This is from Optional
            if (
                not field.raw_data
                or isinstance(field.raw_data[0], str)
                and not self.string_check(field.raw_data[0])
            ):
                field.errors[:] = []
                raise StopValidation()


class RequiredIf(RequiredWhen):
    # a validator which makes a field required if
    # another field is set and has a truthy value

    def __init__(self, other_field_name, *args, **kwargs):
        self.other_field_name = other_field_name
        super(RequiredIf, self).__init__(self.check_func, *args, **kwargs)

    def check_func(self, field, form):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception(
                'no field named "%s" in form' % self.other_field_name
            )
        return bool(other_field.data)


class Tel:
    """
    Validates a phone number. Requires phonenumbers package to be
    installed. For ex: pip install wtforms[phonenumbers].

    :param region:
        The region that we are expecting the number to be from. This
        is only used if the number being submitted is not written in
        international format. The country_code for the number in
        this case would be stored as that of the default region
        supplied. If the number is guaranteed to start with a '+'
        followed by the country calling code, then None or
        UNKNOWN_REGION can be supplied.

        The list of the codes can be found here:
        http://www.iso.org/iso/country_codes/iso_3166_code_lists/country_names_and_code_elements.htm
    :param message:
        Error message to raise in case of a validation error.
    :param granular_message:
        Use validation failed message from phonenumbers library
        (Default False).
    :param allow_local:
        Allow a local number (i.e. a number without an area code like 555-1234).
    """

    def __init__(
        self,
        region=None,
        message=None,
        granular_message=False,
        allow_local=False,
        onlyRegions=[],
        excludeRegions=[],
    ):
        if phonenumbers is None:  # pragma: no cover
            raise Exception(
                "Install 'phonenumbers' for telephone number validation support."
            )
        self.region = region
        self.message = message
        self.granular_message = granular_message
        self.allow_local = allow_local
        self.onlyRegions = set(onlyRegions)
        self.excludeRegions = set(excludeRegions)

    def __call__(self, form, field):
        try:
            phone_number = phonenumbers.parse(field.data, self.region)
            if self.allow_local:
                is_valid = phonenumbers.is_possible_number(phone_number)
            else:
                is_valid = phonenumbers.is_valid_number(phone_number)

            if is_valid:
                if (
                    self.onlyRegions
                    and phonenumbers.region_code_for_number(phone_number)
                    not in self.onlyRegions
                ):
                    is_valid = False
                elif (
                    self.excludeRegions
                    and phonenumbers.region_code_for_number(phone_number)
                    in self.excludeRegions
                ):
                    is_valid = False

            if not is_valid:
                raise ValueError("Invalid phone number.")
        except (
            phonenumbers.phonenumberutil.NumberParseException,
            ValueError,
        ) as e:
            message = self.message
            if message is None:
                if self.granular_message:
                    message = field.gettext(str(e))
                else:
                    message = field.gettext("Invalid phone number.")
            raise ValidationError(message) from e
