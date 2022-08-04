from flask import render_template, current_app, flash, request
from . import main
from .util import is_important_special, ResortChoices, RoomChoices, ViewChoices
from .forms import ImportantCriteriaListForm
from .. import db
from ..models import StoredSpecial as Special, CategoryModelLoader
from ..auth import auth
from itertools import chain

@main.after_app_request
def after_request(response):
    user = auth.current_user()
    if user is not None:
        user.ping()
        db.session.commit()
    return response

@main.route('')
@auth.login_required
def current_specials():
    query = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [(special, is_important_special(special)) for special in query]
    return render_template(
        'email_template.html',
        specials_group=(('All', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@main.route('/important')
@auth.login_required
def current_important_specials():
    query = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [(special, True) for special in query if is_important_special(special)]
    return render_template(
        'email_template.html',
        specials_group=(('Important', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@main.route('/criteria', methods=['GET', 'POST'])
@auth.login_required
def current_important_criteria():
    user = auth.current_user()
    form = ImportantCriteriaListForm.from_json(user.important_criteria)
    template_form = ImportantCriteriaListForm(formdata=None)
    categories = CategoryModelLoader()
    resort_choices = ResortChoices(categories.resorts)
    room_choices = RoomChoices(categories.rooms)
    view_choices = ViewChoices(categories.views)
    for criteria in chain(form.important_criteria, template_form.important_criteria):
        criteria.resorts.choices = resort_choices.choices
        criteria.rooms.choices = room_choices.choices
        criteria.views.choices = view_choices.choices
    if form.validate_on_submit():
        criteria = form.to_json()
        if criteria:
            user.important_criteria = criteria
        flash('Successfully Updated Important Criteria!', 'success')
    return render_template(
        'criteria/criteria_template.html',
        env_label=current_app.config.get("ENV_LABEL"),
        form=form,
        template_form=template_form
    )

@main.route('/errors')
@auth.login_required
def current_error_specials():
    all_stored_specials = Special.query.filter_by(error=True).order_by(Special.check_in, Special.check_out).all()
    return render_template('email_template.html',
                           specials_group=(('Errors', all_stored_specials),),
                           env_label=current_app.config.get("ENV_LABEL"))
