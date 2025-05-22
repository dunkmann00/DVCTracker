from itertools import chain

from flask import current_app, flash, render_template

from .. import db
from ..auth import auth
from ..models import CategoryModelLoader
from . import main
from .forms import ImportantCriteriaListForm
from .util import ResortChoices, RoomChoices, ViewChoices


@main.after_app_request
def after_request(response):
    user = auth.current_user()
    if user is not None:
        user.ping()
        db.session.commit()
    return response


@main.route("/criteria", methods=["GET", "POST"])
@auth.login_required
def current_important_criteria():
    user = auth.current_user()
    form = ImportantCriteriaListForm.from_json(user.important_criteria)
    template_form = ImportantCriteriaListForm(formdata=None)
    categories = CategoryModelLoader()
    resort_choices = ResortChoices(categories.resorts)
    room_choices = RoomChoices(categories.rooms)
    view_choices = ViewChoices(categories.views)
    for criteria in chain(
        form.important_criteria, template_form.important_criteria
    ):
        criteria.resorts.choices = resort_choices.choices
        criteria.rooms.choices = room_choices.choices
        criteria.views.choices = view_choices.choices
    if form.validate_on_submit():
        criteria = form.to_json()
        if criteria:
            user.important_criteria = criteria
        flash("Successfully Updated Important Criteria!", "success")
    return render_template(
        "criteria/criteria_template.html",
        env_label=current_app.config.get("ENV_LABEL"),
        form=form,
        template_form=template_form,
    )
