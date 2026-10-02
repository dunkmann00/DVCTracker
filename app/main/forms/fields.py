from collections.abc import Generator
from itertools import chain
from typing import Any, Iterable

import email_validator
import phonenumbers
import wtforms


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

    def __iter__(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> (
        Generator[tuple[str, wtforms.SelectFieldBase._Option], None, None]
        | Generator[wtforms.SelectFieldBase._Option, None, None]
    ):
        if self.has_groups():
            counter = self._make_counter()
            for group, choices in self.iter_groups():
                yield group, self._make_options(choices, counter)  # pyright: ignore[reportReturnType]
        else:
            yield from self._make_options(self.iter_choices())

    def has_groups(self) -> bool:
        return (
            self.choices is not None
            and len(self.choices) > 0
            and isinstance(self.choices[0], dict)  # pyright: ignore[reportArgumentType]
        )

    def iter_groups(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
    ) -> Generator[
        tuple[str, list[tuple[str, str, bool, dict[str, Any]]]], None, None
    ]:
        if self.choices is None:
            return

        for choices_dict in self.choices:
            group: str = choices_dict.get("group")  # pyright: ignore[reportAttributeAccessIssue]
            choices: list[tuple[str, str]] = choices_dict.get("options")  # pyright: ignore[reportAttributeAccessIssue]
            yield (group, self._choices_generator(choices))  # pyright: ignore[reportAttributeAccessIssue]

    def iter_choices(
        self,
    ) -> Generator[tuple[str, str, bool, dict[str, Any]], None, None]:
        if self.has_groups():
            choices: list[tuple[str, str]] = list(
                chain.from_iterable(
                    map(lambda x: x.get("options"), self.choices)  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
                )
            )
            return self._choices_generator(choices)  # pyright: ignore[reportAttributeAccessIssue]
        return super().iter_choices()  # pyright: ignore[reportReturnType]

    def _make_option(
        self,
        choice: tuple[str, str, bool, dict[str, Any]],
        index: int,
        opts: dict[str, Any],
    ) -> wtforms.SelectFieldBase._Option:
        value, label, checked, _ = choice
        opt = self._Option(label=label, id="%s-%d" % (self.id, index), **opts)
        opt.process(None, value)
        opt.checked = checked
        return opt

    def _make_options(
        self,
        choices: Iterable[tuple[str, str, bool, dict[str, Any]]],
        counter: Generator[int, None, None] | None = None,
    ) -> Generator[wtforms.SelectFieldBase._Option, None, None]:
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
    def _make_counter() -> Generator[int, None, None]:
        i = 0
        while True:
            yield i
            i += 1


class HiddenIntegerField(wtforms.IntegerField):
    """
    HiddenIntegerField is a convenience for an IntegerField with a HiddenInput widget.

    It will render as an ``<input type="hidden">`` but otherwise coerce to an integer.
    """

    widget = wtforms.widgets.HiddenInput()


class EmailField(wtforms.EmailField):
    @property
    def normalized_data(self) -> str | None:
        try:
            if self.data is None:
                raise email_validator.EmailNotValidError()
            return email_validator.validate_email(
                self.data, check_deliverability=False
            ).email
        except email_validator.EmailNotValidError:
            return None


class TelField(wtforms.TelField):
    raw_phone_data = None

    def process_formdata(self, valuelist: list[Any]) -> None:
        if valuelist:
            self.raw_phone_data = valuelist[0]
            self.data = (
                valuelist[1] if len(valuelist) > 1 else self.raw_phone_data
            )

    @property
    def normalized_data(self) -> str | None:
        try:
            phone_number = phonenumbers.parse(self.data, "US")  # pyright: ignore[reportArgumentType]
            if not phonenumbers.is_valid_number(phone_number):
                raise ValueError()
            return phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164
            )
        except (
            phonenumbers.phonenumberutil.NumberParseException,
            ValueError,
        ) as e:
            return None
