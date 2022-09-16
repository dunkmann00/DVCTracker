from flask import render_template, current_app
from . import specials
from ..util import is_important_special
from ...auth import auth
from ...util import test_old_values
from ...models import StoredSpecial as Special

@specials.route('')
@auth.login_required
def current_specials():
    query = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [(special, is_important_special(special)) for special in query]
    return render_template(
        'specials/email_template.html',
        specials_group=(('All', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/important')
@auth.login_required
def current_important_specials():
    query = Special.query.order_by(Special.check_in, Special.check_out)
    all_stored_specials = [(special, True) for special in query if is_important_special(special)]
    return render_template(
        'specials/email_template.html',
        specials_group=(('Important', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/errors')
@auth.login_required
def current_error_specials():
    query = Special.query.filter_by(error=True).order_by(Special.check_in, Special.check_out)
    all_stored_specials = [(special, is_important_special(special)) for special in query]
    return render_template(
        'specials/email_template.html',
        specials_group=(('Errors', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/test')
@auth.login_required
def test_specials():
    specials = Special.query.limit(3).all()
    up_special = specials[1]
    down_special = specials[2]
    up_special = test_old_values(up_special, True)
    down_special = test_old_values(down_special, False)
    group = [(specials[0], False), (up_special, False), (down_special, True)]
    return render_template(
        'specials/email_template.html',
        specials_group=(('All', group),
            ('Update', group),
            ('Removed', group)),
        env_label=current_app.config.get("ENV_LABEL")
    )
