import wtforms
import phonenumbers
import email_validator
from itertools import chain


class MultiCheckboxField(wtforms.SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.

    Source: https://wtforms.readthedocs.io/en/3.0.x/specific_problems/#specialty-field-tricks

    I've also added support for handling groups (choices submitted as a dict)
    """
    widget = wtforms.widgets.ListWidget(prefix_label=False)
    option_widget = wtforms.widgets.CheckboxInput()

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
        value, label, checked, render_kw = choice
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

class HiddenIntegerField(wtforms.IntegerField):
    """
    HiddenIntegerField is a convenience for an IntegerField with a HiddenInput widget.

    It will render as an ``<input type="hidden">`` but otherwise coerce to an integer.
    """

    widget = wtforms.widgets.HiddenInput()

class EmailField(wtforms.EmailField):
    @property
    def normalized_data(self):
        try:
            if self.data is None:
                raise email_validator.EmailNotValidError()
            return email_validator.validate_email(self.data, check_deliverability=False).email
        except email_validator.EmailNotValidError:
            return None

class TelField(wtforms.TelField):
    raw_phone_data = None

    def process_formdata(self, valuelist):
        if valuelist:
            self.raw_phone_data = valuelist[0]
            self.data = valuelist[1] if len(valuelist) > 1 else self.raw_phone_data

    @property
    def normalized_data(self):
        try:
            phone_number = phonenumbers.parse(self.data, "US")
            if not phonenumbers.is_valid_number(phone_number):
                raise ValueError()
            return phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.E164)
        except (phonenumbers.phonenumberutil.NumberParseException, ValueError) as e:
            return None
