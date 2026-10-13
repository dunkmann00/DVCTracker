from itertools import chain

from flask import Response, current_app, flash, render_template

from .. import db
from ..auth import auth
from ..models import CategoryModelLoader
from . import main
from .forms import ImportantCriteriaListForm
from .util import ResortChoices, RoomChoices, ViewChoices


@main.after_app_request
def after_request(response: Response) -> Response:
    user = auth.current_user()
    if user is not None:
        user.ping()
        db.session.commit()
    return response


@main.route("/criteria", methods=["GET", "POST"])
@auth.login_required
def current_important_criteria() -> str:
    user = auth.current_user()
    form = ImportantCriteriaListForm.from_json(user.important_criteria)  # pyright: ignore[reportOptionalMemberAccess]
    template_form = ImportantCriteriaListForm(formdata=None)
    categories = CategoryModelLoader()
    resort_choices = ResortChoices(categories.resorts)  # pyright: ignore[reportAttributeAccessIssue]
    room_choices = RoomChoices(categories.rooms)  # pyright: ignore[reportAttributeAccessIssue]
    view_choices = ViewChoices(categories.views)  # pyright: ignore[reportAttributeAccessIssue]
    for criteria in chain(
        form.important_criteria, template_form.important_criteria
    ):
        criteria.resorts.choices = resort_choices.choices  # pyright: ignore[reportAttributeAccessIssue]
        criteria.rooms.choices = room_choices.choices  # pyright: ignore[reportAttributeAccessIssue]
        criteria.views.choices = view_choices.choices  # pyright: ignore[reportAttributeAccessIssue]
    if form.validate_on_submit():
        criteria = form.to_json()
        if criteria:
            user.important_criteria = criteria  # pyright: ignore[reportOptionalMemberAccess]
        flash("Successfully Updated Important Criteria!", "success")
    return render_template(
        "criteria/criteria_template.html",
        env_label=current_app.config.get("ENV_LABEL"),
        form=form,
        template_form=template_form,
    )
