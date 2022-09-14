from flask_wtf import FlaskForm, Form
from wtforms import (
    SelectField,
    DateField,
    IntegerField,
    RadioField,
    BooleanField
)
from wtforms import FormField, FieldList
from wtforms.validators import (
    ValidationError,
    InputRequired,
    Optional,
    NumberRange,
    Email
)
from collections import namedtuple
from .fields import (
    MultiCheckboxField,
    HiddenIntegerField,
    EmailField,
    TelField
)
from .validators import (
    RequiredWhen,
    RequiredIf,
    Tel
)
from ...auth import auth
from ...criteria import ImportantCriteria
from ...util import SpecialTypes, ContactTypes


FieldTuple = namedtuple("FieldTuple", ["data"])

class ImportantCriteriaForm(Form):
    special_type = SelectField("Special Type", [InputRequired()], choices=[(SpecialTypes.PRECONFIRM, "Preconfirmed Reservation"), (SpecialTypes.DISC_POINTS, "Discounted Points")], coerce=SpecialTypes, default=SpecialTypes.PRECONFIRM)
    check_in_date = DateField("Check In", [RequiredWhen(lambda field, form: form.special_type.data == SpecialTypes.PRECONFIRM and bool(form.check_out_date.data), message="This field is required when setting a Check Out date for a Preconfirmed Reservation.")])
    check_out_date = DateField("Check Out", [RequiredIf("check_in_date", message="This field is required when setting a Check In date.")])
    length_of_stay = IntegerField("Length of Stay (Nights - Minimum)", [Optional(), NumberRange(min=1, max=30, message="Must be between 1 and 30.")])
    points = IntegerField("Points (Minimum)", [Optional(), NumberRange(min=1, message="Must be greater than 0.")])
    price = IntegerField("Price (Maximum)", [Optional(), NumberRange(min=1, message="Must be greater than 0.")])
    price_per_night = IntegerField("Price/Night (Maximum)", [Optional(), NumberRange(min=1, message="Must be greater than 0.")])
    price_per_point = IntegerField("Price/Point (Maximum)", [Optional(), NumberRange(min=1, message="Must be greater than 0.")])
    resorts = MultiCheckboxField('Resorts', [Optional()])
    rooms = MultiCheckboxField('Rooms', [Optional()])
    views = MultiCheckboxField('Views', [Optional()])

    @property
    def date(self):
        date = {}
        if self.check_out_date.data:
            date['end'] = self.check_out_date.data
            if self.check_in_date.data:
                date['start'] = self.check_in_date.data
        return FieldTuple(data=date)

    @staticmethod
    def fix_for_init_data(json, type):
        json_obj = json.copy()
        json_obj['special_type'] = type
        check_in_date = json_obj.get('date', {}).get('start')
        check_out_date = json_obj.get('date', {}).get('end')
        if check_in_date:
            json_obj['check_in_date'] = check_in_date
        if check_out_date:
            json_obj['check_out_date'] = check_out_date
        return json_obj

    def to_json(self):
        criteria = {}

        for key in ImportantCriteria.valid_criteria_for_type(self.special_type.data):
            value = getattr(self, key).data
            if value:
                criteria[key] = value
        return criteria

def coerce_bool(value):
    return value in ["True", "true", True]

class ImportantCriteriaListForm(FlaskForm):
    important_only = RadioField("Send Important Updates Only", [InputRequired()], choices=[(False, "No"), (True, "Yes")], coerce=coerce_bool)
    important_criteria = FieldList(FormField(ImportantCriteriaForm), min_entries=1)

    @classmethod
    def from_json(cls, json):
        criteria_list = []
        important_only = False
        if json:
            json_obj = json.copy()
            important_only = json_obj.pop("important_only", False)
            for key, value in sorted(json_obj.items(), key=lambda x: x[0].value):
                for criteria_json in value:
                    criteria_json_fix = ImportantCriteriaForm.fix_for_init_data(criteria_json, key)
                    criteria_list.append(criteria_json_fix)
        criteria_list_form = cls(data={"important_criteria": criteria_list, "important_only": important_only})
        return criteria_list_form

    def to_json(self):
        preconfirm = []
        disc_points = []
        for criteria in self.important_criteria:
            criteria_json = criteria.to_json()
            if criteria_json:
                if criteria.special_type.data == SpecialTypes.PRECONFIRM:
                    preconfirm.append(criteria_json)
                else:
                    disc_points.append(criteria_json)
        important_criteria_json = {}
        if preconfirm:
            important_criteria_json[SpecialTypes.PRECONFIRM] = preconfirm
        if disc_points:
            important_criteria_json[SpecialTypes.DISC_POINTS] = disc_points
        important_criteria_json["important_only"] = self.important_only.data
        return important_criteria_json

class ContactForm(FlaskForm):
    contact_id = HiddenIntegerField("Contact ID", [RequiredWhen(lambda _, form: not form.new_contact, message="Missing contact id.")])
    get_errors = BooleanField("Get Error Messages", default=False)

    contact_type = None
    new_contact = False

    def to_json(self):
        return {
            "contact_id": self.contact_id.data,
            "get_errors": self.get_errors.data
        }

    def validate_contact_id(self, field):
        if not self.new_contact:
            user = auth.current_user()
            if not user.is_valid_contact_id(field.data, self.contact_type):
                raise ValidationError("There was a problem removing this contact. Please try again later.")

    @property
    def flat_errors(self):
        errors = [error for errors in self.errors.values() for error in errors]
        return errors

class EmailForm(ContactForm):
    email_address = EmailField("Email", [InputRequired(message="Email address is required."), Email(message="The email address provided is not valid.")])

    contact_type = ContactTypes.EMAIL

    def to_json(self):
        json = super().to_json()
        json["email_address"] = self.email_address.normalized_data or self.email_address.data
        return json

    def validate_email_address(self, field):
        if self.new_contact:
            user = auth.current_user()
            if not user.is_new_contact(field.normalized_data, self.contact_type):
                raise ValidationError("Email address has already been added.")

class PhoneForm(ContactForm):
    phone_number = TelField("Phone Number", [InputRequired(), Tel(region="US", message="The phone number provided is not valid.", onlyRegions=["US"])])

    contact_type = ContactTypes.PHONE

    def to_json(self):
        json = super().to_json()
        json["phone_number"] = self.phone_number.normalized_data or self.phone_number.raw_phone_data
        return json

    def validate_phone_number(self, field):
        if self.new_contact:
            user = auth.current_user()
            if not user.is_new_contact(field.normalized_data, self.contact_type):
                raise ValidationError("Phone number has already been added.")

class ContactListForm(Form):
    email_forms = FieldList(FormField(EmailForm))
    phone_forms = FieldList(FormField(PhoneForm))

    @classmethod
    def new_with_type(cls, contact_type, form_data):
        if contact_type is ContactTypes.EMAIL:
            return cls(email_forms=form_data)
        elif contact_type is ContactTypes.PHONE:
            return cls(phone_forms=form_data)

    def get_first_form(self, contact_type):
        if contact_type is None:
            raise ValueError("'contact_type' must not be 'None'")
        contact_forms = self.email_forms if contact_type is ContactTypes.EMAIL else self.phone_forms
        if len(contact_forms) > 0:
            return contact_forms[0].form
        return EmailForm() if contact_type is ContactTypes.EMAIL else PhoneForm()
