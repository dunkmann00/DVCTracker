from flask import g
from werkzeug.local import LocalProxy

from ..auth import auth
from ..criteria import ImportantCriteria
from ..models import Category
from ..util import ContactTypes


def get_important_special():
    if "is_important_special" not in g:
        user = auth.current_user()
        important_criteria = (
            user.important_criteria if user is not None else None
        )
        g.is_important_special = ImportantCriteria(important_criteria)

    return g.is_important_special


is_important_special = LocalProxy(get_important_special)


class CategoryChoices:
    none_id = None
    sort_key = staticmethod(lambda x: x.name)
    reverse_sort = False

    def __init__(
        self, categories, none_id=None, sort_key=None, reverse_sort=None
    ):
        self.categories = categories

        if none_id is not None:
            self.none_id = none_id

        if sort_key is not None:
            self.sort_key = sort_key

        if reverse_sort is not None:
            self.reverse_sort = reverse_sort

        self.choices = self._get_choices(self.categories)

    def _get_characteristics(self, category):
        raise NotImplementedError

    # """
    # I'm not using this function but I'm keeping it in just so that if I forget
    # what the heck the nested generator comprehension that I'm using does I can
    # just look at this to quickly understand it.
    #
    # This function is equivalent to this (well, equivalent output):
    # category_list = (item for category in categories for item in self._get_list_items(category))
    # category_list = sorted(category_list, key=self.sort_key, reverse=self.reverse_sort)
    # """
    # def _get_category_list(self, categories):
    #     category_list = []
    #     for category in categories:
    #         if category.category_id == self.none_id:
    #             category_list += self._get_characteristics(category)
    #         else:
    #             category_list.append(category)
    #
    #     category_list = sorted(category_list, key=self.sort_key, reverse=self.reverse_sort)
    #     return category_list

    def _get_list_items(self, category):
        return (
            self._get_characteristics(category)
            if category.category_id == self.none_id
            else [category]
        )

    def _get_choice_dict(self, choice):
        if isinstance(choice, Category):
            return {
                "group": choice.name,
                "options": tuple(
                    (characteristic.characteristic_id, characteristic.name)
                    for characteristic in self._get_characteristics(choice)
                ),
            }
        else:
            return {"options": ((choice.characteristic_id, choice.name),)}

    def _get_choices(self, categories):
        # The following two lines are equivalent to _get_category_list
        category_list = (
            item
            for category in categories
            for item in self._get_list_items(category)
        )
        category_list = sorted(
            category_list, key=self.sort_key, reverse=self.reverse_sort
        )
        return tuple(self._get_choice_dict(item) for item in category_list)


class ResortChoices(CategoryChoices):
    reverse_sort = True

    def _get_characteristics(self, category):
        return category.resorts


class RoomChoices(CategoryChoices):
    none_id = "category_room_none"
    sort_key = staticmethod(lambda x: x.room_index)

    def _get_characteristics(self, category):
        return category.rooms


class ViewChoices(CategoryChoices):
    none_id = "category_view_none"

    def _get_characteristics(self, category):
        return category.views


def get_template_for_type(contact_type):
    if contact_type is ContactTypes.EMAIL:
        return "user/user_email_list.html"
    elif contact_type is ContactTypes.PHONE:
        return "user/user_phone_list.html"
