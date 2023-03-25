from flask import render_template, current_app
from . import specials
from ..util import is_important_special
from ...auth import auth
from ...util import test_old_values
from ...models import StoredSpecial as Special, db

@specials.route('')
@auth.login_required
def current_specials():
    specials = db.session.scalars(db.select(Special).order_by(Special.check_in, Special.check_out))
    all_stored_specials = [(special, is_important_special(special)) for special in specials]
    return render_template(
        'specials/email_template.html',
        specials_group=(('All', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/important')
@auth.login_required
def current_important_specials():
    specials = db.session.scalars(db.select(Special).order_by(Special.check_in, Special.check_out))
    all_stored_specials = [(special, True) for special in specials if is_important_special(special)]
    return render_template(
        'specials/email_template.html',
        specials_group=(('Important', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/errors')
@auth.login_required
def current_error_specials():
    specials = db.session.scalars(db.select(Special).filter_by(error=True).order_by(Special.check_in, Special.check_out))
    all_stored_specials = [(special, is_important_special(special)) for special in specials]
    return render_template(
        'specials/email_template.html',
        specials_group=(('Errors', all_stored_specials),),
        env_label=current_app.config.get("ENV_LABEL")
    )

@specials.route('/test')
@auth.login_required
def test_specials():
    specials = db.session.scalars(db.select(Special).limit(3)).all()
    up_special = specials[1]
    down_special = specials[2]
    up_special = test_old_values(up_special, True)
    down_special = test_old_values(down_special, False)
    group = [(specials[0], False), (up_special, False), (down_special, True)]
    with db.session.no_autoflush:
        html = render_template(
            'specials/email_template.html',
            specials_group=(('All', group),
                ('Update', group),
                ('Removed', group)),
            env_label=current_app.config.get("ENV_LABEL")
        )
    db.session.rollback()
    return html
