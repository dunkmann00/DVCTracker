from flask import render_template, current_app, request, abort
from . import user
from ..forms import ContactListForm
from ..util import get_template_for_type
from ... import db
from ...auth import auth
from ...models import APN
from ...util import ContactTypes


@user.route('')
@auth.login_required
def current_user():
    user = auth.current_user()
    contact_list = ContactListForm(email_forms=user.emails, phone_forms=user.phones)
    contact_list.email_forms.append_entry()
    contact_list.phone_forms.append_entry()

    return render_template(
        'user/user_template.html',
        contact_list=contact_list,
        env_label=current_app.config.get("ENV_LABEL"),
    )

@user.route('/contact/apn', methods=['POST'])
@auth.login_required
def update_apn():
    user = auth.current_user()
    push_token_request = request.get_json()
    push_token_str = push_token_request.get('token', None)
    get_errors = push_token_request.get('getErrors', False)
    if push_token_str is not None:
        push_token = APN.query.filter_by(push_token=push_token_str).first()
        if push_token is None:
            push_token = APN(user=user)
        if push_token.user != user: # If a user signs out and into another account
            push_token.user = user
        push_token.push_token = push_token_str # This also updates last_updated attr
        push_token.get_errors = get_errors
        db.session.add(push_token) # commit happens in main.after_app_request
    return ''

@user.route('/contact/<type>', methods=['POST', 'DELETE'])
@auth.login_required
def update_contact(type):
    # Check for valid ContactTypes
    if type not in [ContactTypes.EMAIL.value, ContactTypes.PHONE.value]:
        abort(404)

    user = auth.current_user()
    contact_type = ContactTypes(type)

    # Create the form with the request data and extract the individual form
    # Determine if this is a new contact being added or an update/delete
    contact_list_form = ContactListForm(request.form)
    contact_form = contact_list_form.get_first_form(contact_type)
    contact_form.new_contact = (request.method == "POST") and contact_form.contact_id.data is None

    form_errors = None

    if contact_form.validate():
        # Validation succeeded so we can use the form data
        contact_model = user.get_contact(contact_form.contact_id.data, contact_type)
        if request.method == "POST":
            if contact_model: # Update
                contact_model.get_errors = contact_form.get_errors.data
            else: # Create
                model_cls = user.contact_class_for(contact_type)
                contact_model = model_cls(**contact_form.to_json())
                contact_model.user = user
                db.session.add(contact_model)
        else:
            # There is still a chanve this could be None (although it shouldn't)
            # so just make sure it isn't
            if contact_model:
                db.session.delete(contact_model)
        contact_form = None

        db.session.commit()
    else:
        # Store the errors in our own dict to be passed back into the template
        form_errors = {contact_form.contact_id.data: contact_form.flat_errors}
        if contact_form.contact_id.data is not None:
            # It didn't validate but there is a contact_id. This means it was either
            # an update or delete of an already created contact. The bottom form
            # should not be populated with this data.
            contact_form = None


    # Let's get the data that needs to be passed back. Including either an empty
    # bottom form (ready to add another contact) or with the erroneous data that
    # was submitted
    contact_list_data = list(user.get_contacts_for(contact_type))
    contact_list_data.append(contact_form and contact_form.to_json())

    contact_list = ContactListForm.new_with_type(contact_type, contact_list_data)

    return render_template(
        get_template_for_type(contact_type),
        contact_list=contact_list,
        form_errors=form_errors
    )
