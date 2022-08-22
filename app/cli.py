from flask import current_app, g, render_template, json
from flask.cli import with_appcontext
from datetime import date
from . import db
from .models import StoredSpecial, Status, ParserStatus, User
from .criteria import ImportantCriteria
from .parsers import PARSERS
from .util import test_old_values
from . import notifications
from base64 import b64encode
import click, os, traceback
import sqlalchemy.exc

@click.command(help="Encode the AuthKey p8 file into base64 for storing as an environment variable.")
@click.argument('auth_key_path')
def encode_auth_key(auth_key_path):
    with open(auth_key_path, 'rb') as f:
        auth_key_base64 = b64encode(f.read()).decode()
    print("Base64 Encoded AuthKey:")
    print(auth_key_base64)

@click.command(help="Create a new User with the provided Username")
@click.option('-u', '--username', prompt=True)
@click.option(
    '-p', '--password',
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
)
@with_appcontext
def make_new_user(username, password):
    print(f"Making new user with username: {username}")
    user = User(username=username, password=password)
    db.session.add(user)
    try:
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        print("Making new user failed. The username already exists.")
    else:
        print("New user created successfully!")

@click.command(help="Reset all specials' error attributes to false & overall health to true.")
@with_appcontext
def reset_errors():
    for special in StoredSpecial.query:
        special.error = False
    set_health(True)
    db.session.commit()

@click.command(help="Store contents of website data from parser NAME to use with local_specials.")
@click.argument('name')
@click.option('-e', '--extension', default='html', help=("The extension you would like to use for "
                                                         "the file that will be created. The "
                                                         "default is 'html'."))
@with_appcontext
def store_specials_data(name, extension):
    for Parser in PARSERS:
        dvc_parser = Parser()
        if dvc_parser.source == name:
            mode = 'wb'
            specials_data = dvc_parser.get_specials_page()
            if (isinstance(specials_data, str) or
                isinstance(specials_data, list) or
                isinstance(specials_data, dict)):
                mode = 'w'
            elif not isinstance(specials_data, bytes):
                print(f'Unable to write parser data to file (Type: {type(specials_data)})')

            with open(f'{dvc_parser.source}.{extension}', mode) as f:
                if isinstance(specials_data, bytes) or isinstance(specials_data, str):
                    f.write(specials_data)
                else:
                    json.dump(specials_data, f)
            print(f"'{dvc_parser.source}' data has been stored!")
            return
    print(f"No parser with the name '{name}' was found.")

@click.command(help="Send a test email with a few specials and old values.")
def send_test_email():
    specials = StoredSpecial.query.limit(3).all()
    up_special = specials[1]
    down_special = specials[2]
    test_old_values(up_special, True)
    test_old_values(down_special, False)
    group = [(specials[0], False), (up_special, False), (down_special, True)]
    email = render_template(
        'specials/email_template.html',
        specials_group=(('All', group),
            ('Update', group),
            ('Removed', group)),
        env_label=current_app.config.get("ENV_LABEL")
    )
    notifications.send_update_email(email)

@click.command(name="update-specials", help='Update all DVC specials & send messages when changes are found.')
@click.option('--local', 'local_specials', multiple=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True),
                         envvar="LOCAL_SPECIALS",
                         help=('Load specials from the given files. The files must be named the name of '
                               'the parser they are being used for.'))
@click.option('--email/--no-email', 'send_email', default=True,
                         help='Specifies whether an email should be sent if changes to the current specials are found.')
@click.option('--error-report', 'send_error_report', is_flag=True,
                         help='Produce an error report via email of all of the current errors.')
@with_appcontext
def update_specials_cli(local_specials, send_email, send_error_report):
    update_specials(local_specials, send_email, send_error_report)

def update_specials(local_specials, send_email, send_error_report):
    g.send_error_report = send_error_report
    try:
        #Get the current specials from either the Internet or a local file
        all_current_specials = get_current_specials(local_specials)
        all_new_specials = {}
        all_stored_specials = []
        all_updated_specials_tuple = []
        all_removed_specials_list = []

        for parser_source in all_current_specials:
            #Make a copy of all the specials, needed for when we check everything
            #for errors later
            new_specials = all_current_specials[parser_source].copy()

            if len(new_specials) == 0:
                if not empty_parser_error(parser_source):
                    continue

            # Since the parser has specials in it, set it to healthy
            parser_healthy(parser_source)

            #Get the stored specials from the db
            stored_specials = StoredSpecial.query.filter_by(source=parser_source).order_by(StoredSpecial.check_in, StoredSpecial.check_out).all()

            #Check for any changes to the specials
            updated_specials_tuple, removed_specials_list = check_for_changes(new_specials, stored_specials)

            all_new_specials.update(new_specials)
            all_stored_specials.extend(stored_specials)
            all_updated_specials_tuple.extend(updated_specials_tuple)
            all_removed_specials_list.extend(removed_specials_list)

        #Adding new Specials
        new_specials_list = store_new_specials(all_new_specials, all_stored_specials)

        #Updating Old Specials
        updated_specials_list = update_old_specials(all_updated_specials_tuple)

        #Deleting Removed Specials
        removed_specials_list = remove_old_specials(all_removed_specials_list)

        for user in User.query:
            important_criteria = ImportantCriteria(user.important_criteria)
            #Send an email if we need to.... i.e. if there were any kind of updates
            send_new_specials = get_send_specials_list(new_specials_list, important_criteria)
            send_updated_specials = get_send_specials_list(updated_specials_list, important_criteria)
            send_removed_specials = get_send_specials_list(removed_specials_list, important_criteria)

            changes = []
            if len(send_new_specials) > 0:
                changes.append(('Added', send_new_specials))
            if len(send_updated_specials) > 0:
                changes.append(('Updated', send_updated_specials))
            if len(send_removed_specials) > 0:
                changes.append(('Removed', send_removed_specials))
            if changes and send_email:
                email_message = render_template('specials/email_template.html',
                                                specials_group=changes,
                                                env_label=current_app.config.get("ENV_LABEL"))
                notifications.send_update_email(email_message)

                #Send a text/push notification if any of the changes were considered important
                if contains_important(send_new_specials) or contains_important(send_updated_specials):
                    notifications.send_update_text_message()
                    notifications.send_update_push_notification()


        changes_made = (len(new_specials_list) + len(updated_specials_list) + len(removed_specials_list)) > 0
        if changes_made and send_email:
            print("Changes found, sending emails complete!")
        elif changes_made and not send_email:
            print("Changes found, not sending email. Bada-bing, bada-BOOM!")
        else:
            print("No changes found. Nothing to update Cap'n. :-)")

        #Handle any errors that were generated during the parsing of the specials
        handle_errors(all_current_specials, all_stored_specials)
        set_health(True)
    except Exception as e:
        unhandled_error(e)

    db.session.commit()

def get_current_specials(local_specials):
    all_new_specials = {}
    for Parser in PARSERS:
        dvc_parser = Parser()
        local_special = local_special_for_parser(dvc_parser, local_specials)
        dvc_parser_specials = dvc_parser.get_all_specials(local_special)
        all_new_specials[dvc_parser.source] = dvc_parser_specials
    return all_new_specials

def get_send_specials_list(specials, important_criteria):
    is_important_special = important_criteria # Doing this just so the name makes more sense given that it is called
    if important_criteria.important_only:
        return [(special, True) for special in specials if is_important_special(special)]
    else:
        return [(special, is_important_special(special)) for special in specials]

def contains_important(send_tuple):
    importants = [element[1] for element in send_tuple] # Tested this a few different ways and for small lists this is fastest (and simplest)
    return True in importants

def store_new_specials(new_specials, stored_specials):
    new_specials_list = []
    for new_special_key in new_specials:
        special_entry = add_special(new_specials[new_special_key])
        stored_specials.append(special_entry)
        new_specials_list.append(special_entry)

    if len(new_specials_list) > 1:
        new_specials_list = sorted(new_specials_list, key=lambda special: (special.check_in if special.check_in else date(2000,1,1),
                                                                           special.check_out if special.check_out else date(2000,1,1)))

    return new_specials_list

def update_old_specials(updated_specials_tuple):
    updated_specials_list = []
    for special_tuple in updated_specials_tuple:
        parsed_special, stored_special = special_tuple
        stored_special.update_with_special(parsed_special)
        updated_specials_list.append(stored_special)

    return updated_specials_list

def remove_old_specials(removed_specials):
    removed_specials_list = []
    for stored_special in removed_specials:
        remove_special(stored_special)
        removed_specials_list.append(stored_special)

    return removed_specials_list

def check_for_changes(new_specials, stored_specials):
    updated_specials_tuple = []
    removed_specials_list = []
    for stored_special in stored_specials:
        if stored_special.special_id in new_specials:
            new_special = new_specials[stored_special.special_id]
            if stored_special != new_special:
                updated_specials_tuple.append((new_special, stored_special))
            del new_specials[stored_special.special_id]
        else:
            removed_specials_list.append(stored_special)

    return updated_specials_tuple, removed_specials_list

def add_special(parsed_special):
    special_entry = StoredSpecial.from_parsed_special(parsed_special)
    db.session.add(special_entry)
    return special_entry

def remove_special(stored_special):
    db.session.delete(stored_special)

def handle_errors(new_specials, stored_specials):
    new_specials_flat = {}
    for key in new_specials:
        new_specials_flat.update(new_specials[key])
    new_specials_errors = [new_specials_flat[stored_special.special_id] for stored_special in stored_specials if stored_special.new_error]
    if len(new_specials_errors) > 0:
        error_msg = render_template('specials/error_template.html', specials=new_specials_errors,
                                    env_label=current_app.config.get("ENV_LABEL"))
        print('Uhh-ohh, Houston, we have a problem. There appears to be an error.')
        notifications.send_error_email(error_msg)
        notifications.send_error_text_messsage()
        notifications.send_error_push_notification()

    if g.send_error_report:
        all_specials_errors = [new_specials_flat[stored_special.special_id] for stored_special in stored_specials if stored_special.error]
        all_empty_parsers = ParserStatus.query.filter_by(healthy=False).all()
        if len(all_specials_errors) > 0 or len(all_empty_parsers) > 0:
            error_msg = render_template('specials/error_template.html', specials=all_specials_errors,
                                        empty_parsers=all_empty_parsers,
                                        env_label=current_app.config.get("ENV_LABEL"), error_report=True)
            print('So, about that bug...when are you going to catch it? Producing Error Report.')
            notifications.send_error_report_email(error_msg)

def empty_parser_error(parser_source):
    parser_status = get_parser_status(parser_source)
    if parser_status.healthy and not parser_status.empty_okay:
        parser_status.healthy = False
        print('Umm hello?...Anyone Home?')
        error_msg = render_template('specials/empty_parser_template.html', parser_source=parser_source,
                                    env_label=current_app.config.get("ENV_LABEL"))
        notifications.send_error_email(error_msg)
        notifications.send_error_text_messsage()
        notifications.send_error_push_notification()
    elif not parser_status.healthy and parser_status.empty_okay:
        parser_status.healthy = True
    return parser_status.empty_okay

def parser_healthy(parser_source):
    parser_status = get_parser_status(parser_source)
    parser_status.healthy = True

def get_parser_status(parser_source):
    parser_status = ParserStatus.query.filter_by(parser_source=parser_source).first()
    if parser_status is None:
        parser_status = ParserStatus(parser_source=parser_source,
                                     healthy=True)
        db.session.add(parser_status)
    return parser_status


def unhandled_error(error):
    traceback.print_exc()
    db.session.rollback()
    healthy = check_health()
    if healthy or g.send_error_report:
        error_msg = f'Unhandled Exception: {error_type(error)}\n\n{error}\n\n{traceback.format_exc()}'
        send_error_func = notifications.send_error_report_email if g.send_error_report else notifications.send_error_email
        send_error_func(error_msg, html_message=False)
        if healthy:
            notifications.send_error_text_messsage()
            notifications.send_error_push_notification()
        set_health(False)

# From traceback.py in CPython Line #563
def error_type(error):
    err_type = type(error).__qualname__
    err_mod = type(error).__module__
    if err_mod not in ("__main__", "builtins"):
        err_type = err_mod + '.' + err_type
    return err_type

def get_status():
    status = Status.query.first()
    if not status:
        status = Status(healthy=True)
        db.session.add(status)
    return status

def check_health():
    return get_status().healthy

def set_health(healthy):
    status = get_status()
    if status.healthy != healthy:
        status.healthy = healthy

def local_special_for_parser(parser, local_specials):
    for local_special in local_specials:
        if parser.source == os.path.splitext(os.path.basename(local_special))[0]:
            return local_special
