from flask import render_template, current_app, flash, request
from . import main
from .forms import ImportantCriteriaForm, ImportantCriteriaListForm
from .. import env_label, db
from ..models import StoredSpecial as Special
from ..criteria import important_special
from ..auth import auth

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
    all_stored_specials = Special.query.order_by(Special.check_in, Special.check_out).all()
    return render_template('email_template.html',
                           specials_group=(('All', all_stored_specials),),
                           env_label=env_label.get(current_app.env))

@main.route('/important')
@auth.login_required
def current_important_specials():
    all_stored_specials = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [special for special in all_stored_specials if important_special(special)]
    return render_template('email_template.html',
                           specials_group=(('Important', all_stored_specials),),
                           env_label=env_label.get(current_app.env))

@main.route('/criteria', methods=['GET', 'POST'])
@auth.login_required
def current_important_criteria():
    user = auth.current_user()
    form = ImportantCriteriaListForm.from_json(user.important_criteria)
    # import pdb; pdb.set_trace()
    template_form = ImportantCriteriaListForm(formdata=None)
    for criteria in form.important_criteria:
        resorts = [resort[0] for resort in Special.query.with_entities(Special.resort).order_by(Special.resort).distinct()]
        criteria.resorts.choices = resorts
    if form.validate_on_submit():
        criteria = form.to_json()
        if criteria:
            user.important_criteria = criteria
        flash('Successfully Updated Important Criteria!', 'success')
    return render_template(
        'criteria_template.html',
        env_label=env_label.get(current_app.env),
        form=form,
        template_form=template_form
    )

@main.route('/errors')
@auth.login_required
def current_error_specials():
    all_stored_specials = Special.query.filter_by(error=True).order_by(Special.check_in, Special.check_out).all()
    return render_template('email_template.html',
                           specials_group=(('Errors', all_stored_specials),),
                           env_label=env_label.get(current_app.env))
