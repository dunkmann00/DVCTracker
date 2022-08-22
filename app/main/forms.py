from flask_wtf import FlaskForm, Form
from wtforms import SelectField, DateField, IntegerField, StringField, SelectMultipleField, RadioField
from wtforms import FormField, FieldList
from wtforms import widgets
from wtforms.validators import InputRequired, Optional, StopValidation
from collections import namedtuple
from datetime import date
from ..util import SpecialTypes
from ..criteria import ImportantCriteria
from itertools import chain

FieldTuple = namedtuple("FieldTuple", ["data"])

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
        # import pdb; pdb.set_trace()
        if self.check_func(field, form):
            setattr(field.flags, "required", True)
            if field.raw_data and field.raw_data[0]:
                return

            if self.message is None:
                message = field.gettext("This field is required.")
            else:
                message = self.message

            field.errors[:] = []
            raise StopValidation(message)
        else:
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
        # import pdb; pdb.set_trace()
        self.other_field_name = other_field_name
        super(RequiredIf, self).__init__(self.check_func, *args, **kwargs)

    def check_func(self, field, form):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception('no field named "%s" in form' % self.other_field_name)
        return bool(other_field.data)


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.

    Source: https://wtforms.readthedocs.io/en/3.0.x/specific_problems/#specialty-field-tricks

    I've also added support for handling groups (choices submitted as a dict)
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

    def __iter__(self):
        if self.has_groups():
            counter = self._make_counter()
            for group, choices in self.iter_groups():
                yield group, self._make_options(choices, counter)
        else:
            yield from self._make_options(self.iter_choices())

    def has_groups(self):
        return self.choices is not None and len(self.choices) > 0 and isinstance(self.choices[0], dict)

    def iter_groups(self):
        for choices_dict in self.choices:
            group = choices_dict.get("group")
            choices = choices_dict.get("options")
            yield (group, self._choices_generator(choices))

    def iter_choices(self):
        if self.has_groups():
            choices = list(chain.from_iterable(map(lambda x: x.get("options"), self.choices)))
            return self._choices_generator(choices)
        return super().iter_choices()

    def _make_option(self, choice, index, opts):
        value, label, checked = choice
        opt = self._Option(label=label, id="%s-%d" % (self.id, index), **opts)
        opt.process(None, value)
        opt.checked = checked
        return opt

    def _make_options(self, choices, counter=None):
        if counter is None:
            counter = self._make_counter()
        opts = dict(
            widget=self.option_widget,
            validators=self.validators,
            name=self.name,
            render_kw=self.render_kw,
            _form=None,
            _meta=self.meta,
        )

        for choice, i in zip(choices, counter):
            yield self._make_option(choice, i, opts)

    @staticmethod
    def _make_counter():
        i = 0
        while True:
            yield i
            i+=1

class ImportantCriteriaForm(Form):
    special_type = SelectField("Special Type", [InputRequired()], choices=[(SpecialTypes.PRECONFIRM, "Preconfirmed Reservation"), (SpecialTypes.DISC_POINTS, "Discounted Points")], coerce=SpecialTypes, default=SpecialTypes.PRECONFIRM)
    check_in_date = DateField("Check In", [RequiredWhen(lambda field, form: form.special_type.data == SpecialTypes.PRECONFIRM and bool(form.check_out_date.data), message="This field is required when setting a Check Out date for a Preconfirmed Reservation.")])
    check_out_date = DateField("Check Out", [RequiredIf("check_in_date", message="This field is required when setting a Check In date.")])
    length_of_stay = IntegerField("Length of Stay (Nights - Minimum)", [Optional()], render_kw={"min": 1, "max": 30})
    points = IntegerField("Points (Minimum)", [Optional()])
    price = IntegerField("Price (Maximum)", [Optional()])
    price_per_night = IntegerField("Price/Night (Maximum)", [Optional()])
    price_per_point = IntegerField("Price/Point (Maximum)", [Optional()])
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



#
